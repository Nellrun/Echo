"""
Query escape hatch — point lookups with mandatory filters and hard caps.

These tools exist for the rare cases where an LLM genuinely needs to see
raw records (verifying a specific date, pulling one film's full review).
They are deliberately narrow: every call requires a bounded window or a
direct identity lookup, and every list endpoint has a capped ``limit``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from echo.core.registry import Registry
from echo.core.types import Period

if TYPE_CHECKING:
    from fastmcp import FastMCP

SCROBBLE_LIMIT_MAX = 200
DIARY_LIMIT_MAX = 100
WATCHLIST_LIMIT_MAX = 200
FILM_SEARCH_LIMIT_MAX = 50
ARTIST_SEARCH_TOP_TRACKS = 10
ALBUM_SEARCH_TOP_TRACKS = 10
TRAKT_HISTORY_LIMIT_MAX = 200
TRAKT_WATCHLIST_LIMIT_MAX = 200


def _day_bounds(from_: str, to: str) -> Period:
    start = datetime.combine(date.fromisoformat(from_), datetime.min.time())
    end_exclusive = datetime.combine(
        date.fromisoformat(to), datetime.max.time()
    ).replace(microsecond=0)
    if end_exclusive < start:
        raise ValueError(f"`to` precedes `from`: {from_}..{to}")
    # Normalise the upper bound to midnight of the next day so every event
    # logged on ``to`` is included under the half-open [start, end) rule.
    from datetime import timedelta as _td

    return Period(
        start=start,
        end=datetime.combine(date.fromisoformat(to), datetime.min.time()) + _td(days=1),
        label=f"{from_}..{to}",
    )


def register(mcp: FastMCP, registry: Registry) -> None:
    @mcp.tool()
    def query_scrobbles(
        from_date: str,
        to_date: str,
        artist: str | None = None,
        track: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """
        Raw scrobbles in ``[from_date, to_date]`` (both YYYY-MM-DD, inclusive).

        Optional case-insensitive ``artist`` / ``track`` filters. Hard cap:
        200. If you need more, call again with a narrower window — we will
        not paginate.
        """
        limit = max(1, min(limit, SCROBBLE_LIMIT_MAX))
        period = _day_bounds(from_date, to_date)
        music = registry.get("music")
        if music is None or not music.is_available():
            return {"results": [], "truncated": False, "note": "music provider unavailable"}

        results: list[dict[str, Any]] = []
        truncated = False
        artist_lc = artist.lower() if artist else None
        track_lc = track.lower() if track else None

        for event in music.events(period):
            if event.kind != "scrobble":
                continue
            payload = event.payload
            if artist_lc and payload.get("artist", "").lower() != artist_lc:
                continue
            if track_lc and payload.get("track", "").lower() != track_lc:
                continue
            if len(results) >= limit:
                truncated = True
                break
            results.append(
                {
                    "when": event.timestamp.isoformat(),
                    "artist": payload.get("artist"),
                    "track": payload.get("track"),
                    "album": payload.get("album"),
                }
            )
        return {"results": results, "truncated": truncated, "limit": limit}

    @mcp.tool()
    def query_diary(
        from_date: str,
        to_date: str,
        min_rating: float | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """
        Raw diary entries in ``[from_date, to_date]`` (inclusive).

        Optional ``min_rating`` drops entries rated below the threshold
        (unrated entries are kept only when ``min_rating`` is not set).
        Hard cap: 100.
        """
        limit = max(1, min(limit, DIARY_LIMIT_MAX))
        period = _day_bounds(from_date, to_date)
        films = registry.get("films")
        if films is None or not films.is_available():
            return {"results": [], "truncated": False, "note": "films provider unavailable"}

        results: list[dict[str, Any]] = []
        truncated = False
        for event in films.events(period):
            if event.kind != "diary":
                continue
            payload = event.payload
            if min_rating is not None:
                rating = payload.get("rating")
                if rating is None or rating < min_rating:
                    continue
            if len(results) >= limit:
                truncated = True
                break
            results.append(
                {
                    "date": event.timestamp.date().isoformat(),
                    "film": payload.get("film"),
                    "year": payload.get("year"),
                    "rating": payload.get("rating"),
                    "rewatch": payload.get("rewatch"),
                    "uri": payload.get("uri"),
                    "review": payload.get("review"),
                    "tags": payload.get("tags") or [],
                }
            )
        return {"results": results, "truncated": truncated, "limit": limit}

    @mcp.tool()
    def query_film(
        title: str | None = None, letterboxd_uri: str | None = None
    ) -> dict[str, Any]:
        """
        Look up a single film across diary, ratings, and watchlist.

        Pass either ``title`` (case-insensitive exact match) or
        ``letterboxd_uri``. Returns:

        * ``film`` — name / year / uri
        * ``current_rating`` — latest overall rating for the film (not per watch)
        * ``on_watchlist`` — is the film still queued on the watchlist
        * ``watches`` — every logged diary entry with its per-watch rating,
          rewatch flag, review text, and tags
        """
        if not title and not letterboxd_uri:
            raise ValueError("provide either `title` or `letterboxd_uri`")

        films = registry.get("films")
        if films is None or not films.is_available():
            return {"found": False, "note": "films provider unavailable"}

        all_period = Period(start=None, end=None, label="all")
        title_lc = title.lower() if title else None
        uri = letterboxd_uri.strip() if letterboxd_uri else None

        def _match_payload(payload: dict[str, Any]) -> bool:
            if uri is not None and payload.get("uri") != uri:
                return False
            if title_lc is not None and payload.get("film", "").lower() != title_lc:
                return False
            return True

        watches: list[dict[str, Any]] = []
        film_info: dict[str, Any] | None = None
        for event in films.events(all_period):
            if event.kind != "diary":
                continue
            payload = event.payload
            if not _match_payload(payload):
                continue
            if film_info is None:
                film_info = {
                    "film": payload.get("film"),
                    "year": payload.get("year"),
                    "uri": payload.get("uri"),
                }
            watches.append(
                {
                    "date": event.timestamp.date().isoformat(),
                    "rating": payload.get("rating"),
                    "rewatch": payload.get("rewatch"),
                    "review": payload.get("review"),
                    "tags": payload.get("tags") or [],
                }
            )

        if film_info is None:
            return {"found": False, "film": None, "watches": []}

        # Enrich with data not stored on diary events.
        current_rating: float | None = None
        for r in films.ratings():
            if r.film.uri == film_info["uri"]:
                current_rating = r.rating
                break

        on_watchlist = any(w.film.uri == film_info["uri"] for w in films.watchlist())

        return {
            "found": True,
            "film": film_info,
            "current_rating": current_rating,
            "on_watchlist": on_watchlist,
            "watches": sorted(watches, key=lambda w: w["date"]),
        }

    @mcp.tool()
    def query_film_search(query: str, limit: int = 25) -> dict[str, Any]:
        """
        Fuzzy "have I seen this?" lookup for films.

        Case-insensitive substring match over every film the user has
        logged, rated, or watchlisted. Returns, for each match:

        * ``film`` / ``year`` / ``uri``
        * ``watched`` — has it ever appeared in the diary
        * ``watches_count`` — how many diary entries (includes rewatches)
        * ``last_watched`` — date of the most recent diary entry, if any
        * ``user_rating`` — latest persisted rating (not per-watch)
        * ``on_watchlist`` — is it still queued

        Use this **before recommending** a film to check whether the user
        has already watched or queued it. Hard cap: 50 results.
        """
        q = (query or "").strip().lower()
        if not q:
            raise ValueError("`query` must be a non-empty substring")
        limit = max(1, min(limit, FILM_SEARCH_LIMIT_MAX))

        films = registry.get("films")
        if films is None or not films.is_available():
            return {"results": [], "truncated": False, "note": "films provider unavailable"}

        all_period = Period(start=None, end=None, label="all")

        # Index by uri so diary / rating / watchlist rows merge cleanly.
        # Falls back to (name, year) when uri is missing.
        def _key(uri: str | None, name: str, year: Any) -> tuple[str, Any]:
            return (uri, None) if uri else (name.lower(), year)

        agg: dict[tuple[str, Any], dict[str, Any]] = {}

        def _ensure(
            name: str, year: Any, uri: str | None
        ) -> dict[str, Any]:
            key = _key(uri, name, year)
            row = agg.get(key)
            if row is None:
                row = {
                    "film": name,
                    "year": year,
                    "uri": uri,
                    "watched": False,
                    "watches_count": 0,
                    "last_watched": None,
                    "user_rating": None,
                    "on_watchlist": False,
                }
                agg[key] = row
            return row

        for event in films.events(all_period):
            if event.kind != "diary":
                continue
            p = event.payload
            name = p.get("film") or ""
            if q not in name.lower():
                continue
            row = _ensure(name, p.get("year"), p.get("uri"))
            row["watched"] = True
            row["watches_count"] += 1
            d = event.timestamp.date().isoformat()
            if row["last_watched"] is None or d > row["last_watched"]:
                row["last_watched"] = d

        # Ratings may reference films not in the diary (rated but not logged).
        for r in films.ratings():
            name = r.film.name
            if q not in name.lower():
                continue
            row = _ensure(name, r.film.year, r.film.uri)
            row["user_rating"] = r.rating

        for w in films.watchlist():
            name = w.film.name
            if q not in name.lower():
                continue
            row = _ensure(name, w.film.year, w.film.uri)
            row["on_watchlist"] = True

        # Rank: watched first (newest watch first), then rated-but-unseen,
        # then pure watchlist entries. Alphabetical tiebreak within each
        # bucket for determinism.
        watched = sorted(
            (r for r in agg.values() if r["watched"]),
            key=lambda r: (r["last_watched"] or "", r["film"].lower()),
            reverse=True,
        )
        # ``reverse=True`` above flips the alpha tiebreak too, so resort alpha
        # on ties — group by date, sort each group.
        rated_only = sorted(
            (r for r in agg.values() if not r["watched"] and r["user_rating"] is not None),
            key=lambda r: r["film"].lower(),
        )
        queued_only = sorted(
            (r for r in agg.values() if not r["watched"] and r["user_rating"] is None),
            key=lambda r: r["film"].lower(),
        )
        ordered = watched + rated_only + queued_only

        truncated = len(ordered) > limit
        return {
            "results": ordered[:limit],
            "truncated": truncated,
            "total_matching": len(ordered),
            "limit": limit,
        }

    @mcp.tool()
    def query_artist(name: str, top_tracks: int = 10) -> dict[str, Any]:
        """
        "Have I listened to this artist?" lookup over Last.fm scrobbles.

        Case-insensitive substring match on the artist field. If multiple
        artists match (``"beat"`` → "Beat Happening", "The Beatles"), each
        appears as its own entry.

        Per matching artist returns: ``total_scrobbles``, ``first_played``,
        ``last_played``, ``distinct_tracks``, ``distinct_albums``, and
        ``top_tracks`` (up to 10, by play count).

        Use this to verify whether the user has any history with an artist
        before recommending them.
        """
        q = (name or "").strip().lower()
        if not q:
            raise ValueError("`name` must be a non-empty substring")
        top_tracks = max(0, min(top_tracks, ARTIST_SEARCH_TOP_TRACKS))

        music = registry.get("music")
        if music is None or not music.is_available():
            return {"results": [], "note": "music provider unavailable"}

        all_period = Period(start=None, end=None, label="all")
        from collections import Counter

        # Group by canonical (case-sensitive) artist string.
        grouped: dict[str, dict[str, Any]] = {}

        for event in music.events(all_period):
            if event.kind != "scrobble":
                continue
            p = event.payload
            artist = p.get("artist") or ""
            if q not in artist.lower():
                continue
            row = grouped.get(artist)
            if row is None:
                row = {
                    "artist": artist,
                    "total_scrobbles": 0,
                    "first_played": None,
                    "last_played": None,
                    "tracks": Counter(),
                    "albums": set(),
                }
                grouped[artist] = row
            row["total_scrobbles"] += 1
            row["tracks"][p.get("track") or ""] += 1
            album = p.get("album")
            if album:
                row["albums"].add(album)
            ts = event.timestamp.isoformat()
            if row["first_played"] is None or ts < row["first_played"]:
                row["first_played"] = ts
            if row["last_played"] is None or ts > row["last_played"]:
                row["last_played"] = ts

        results: list[dict[str, Any]] = []
        for row in grouped.values():
            tracks: Counter = row["tracks"]
            results.append(
                {
                    "artist": row["artist"],
                    "total_scrobbles": row["total_scrobbles"],
                    "first_played": row["first_played"],
                    "last_played": row["last_played"],
                    "distinct_tracks": len(tracks),
                    "distinct_albums": len(row["albums"]),
                    "top_tracks": [
                        {"track": t, "plays": c}
                        for t, c in tracks.most_common(top_tracks)
                    ],
                }
            )
        results.sort(key=lambda r: r["total_scrobbles"], reverse=True)
        return {"results": results, "total_matching": len(results)}

    @mcp.tool()
    def query_album(
        album: str,
        artist: str | None = None,
        top_tracks: int = 10,
    ) -> dict[str, Any]:
        """
        "Have I listened to this album?" lookup over Last.fm scrobbles.

        Case-insensitive substring match on ``album``. Optional exact
        (case-insensitive) ``artist`` filter disambiguates common album
        titles. Per matching ``(artist, album)`` pair returns
        ``total_scrobbles``, ``first_played``, ``last_played``,
        ``distinct_tracks``, and ``top_tracks``.
        """
        q = (album or "").strip().lower()
        if not q:
            raise ValueError("`album` must be a non-empty substring")
        top_tracks = max(0, min(top_tracks, ALBUM_SEARCH_TOP_TRACKS))
        artist_lc = artist.strip().lower() if artist else None

        music = registry.get("music")
        if music is None or not music.is_available():
            return {"results": [], "note": "music provider unavailable"}

        all_period = Period(start=None, end=None, label="all")
        from collections import Counter

        grouped: dict[tuple[str, str], dict[str, Any]] = {}

        for event in music.events(all_period):
            if event.kind != "scrobble":
                continue
            p = event.payload
            alb = p.get("album") or ""
            if not alb or q not in alb.lower():
                continue
            art = p.get("artist") or ""
            if artist_lc and art.lower() != artist_lc:
                continue
            key = (art, alb)
            row = grouped.get(key)
            if row is None:
                row = {
                    "artist": art,
                    "album": alb,
                    "total_scrobbles": 0,
                    "first_played": None,
                    "last_played": None,
                    "tracks": Counter(),
                }
                grouped[key] = row
            row["total_scrobbles"] += 1
            row["tracks"][p.get("track") or ""] += 1
            ts = event.timestamp.isoformat()
            if row["first_played"] is None or ts < row["first_played"]:
                row["first_played"] = ts
            if row["last_played"] is None or ts > row["last_played"]:
                row["last_played"] = ts

        results: list[dict[str, Any]] = []
        for row in grouped.values():
            tracks: Counter = row["tracks"]
            results.append(
                {
                    "artist": row["artist"],
                    "album": row["album"],
                    "total_scrobbles": row["total_scrobbles"],
                    "first_played": row["first_played"],
                    "last_played": row["last_played"],
                    "distinct_tracks": len(tracks),
                    "top_tracks": [
                        {"track": t, "plays": c}
                        for t, c in tracks.most_common(top_tracks)
                    ],
                }
            )
        results.sort(key=lambda r: r["total_scrobbles"], reverse=True)
        return {"results": results, "total_matching": len(results)}

    @mcp.tool()
    def query_watchlist(
        limit: int = 50,
        added_after: str | None = None,
    ) -> dict[str, Any]:
        """
        Raw watchlist entries, newest first.

        ``added_after`` (``YYYY-MM-DD``) trims to items added on or after
        that date — useful for "what have I queued up lately". Hard cap: 200.
        """
        limit = max(1, min(limit, WATCHLIST_LIMIT_MAX))
        films = registry.get("films")
        if films is None or not films.is_available():
            return {"results": [], "truncated": False, "note": "films provider unavailable"}

        cutoff = date.fromisoformat(added_after) if added_after else None

        items = [
            w
            for w in films.watchlist()
            if cutoff is None or w.date >= cutoff
        ]
        items.sort(key=lambda w: w.date, reverse=True)

        truncated = len(items) > limit
        trimmed = items[:limit]

        return {
            "results": [
                {
                    "film": w.film.name,
                    "year": w.film.year,
                    "added": w.date.isoformat(),
                    "uri": w.film.uri,
                }
                for w in trimmed
            ],
            "truncated": truncated,
            "total_matching": len(items),
            "limit": limit,
        }

    @mcp.tool()
    def query_trakt_history(
        from_date: str | None = None,
        to_date: str | None = None,
        media_type: str | None = None,
        show: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """
        Raw Trakt watch history, newest first.

        All filters are optional — if none are set, you get the ``limit``
        most recent plays across all media types. Use this for questions
        like "what did I watch last?" or "what was the last episode of X".

        * ``from_date`` / ``to_date`` — ``YYYY-MM-DD`` inclusive day bounds;
          if only one is given the other is left open.
        * ``media_type`` — ``"episode"`` or ``"movie"`` to narrow the stream.
        * ``show`` — case-insensitive exact show title (``"Breaking Bad"``).
        * ``limit`` — hard cap, max 200.
        """
        limit = max(1, min(limit, TRAKT_HISTORY_LIMIT_MAX))
        shows = registry.get("shows")
        if shows is None or not shows.is_available():
            return {"results": [], "truncated": False, "note": "shows provider unavailable"}

        if media_type is not None and media_type not in ("episode", "movie"):
            raise ValueError("media_type must be 'episode', 'movie', or omitted")

        from datetime import timedelta as _td

        start_dt: datetime | None = (
            datetime.combine(date.fromisoformat(from_date), datetime.min.time())
            if from_date
            else None
        )
        end_dt: datetime | None = (
            datetime.combine(date.fromisoformat(to_date), datetime.min.time()) + _td(days=1)
            if to_date
            else None
        )
        if start_dt is not None and end_dt is not None and end_dt <= start_dt:
            raise ValueError(f"`to_date` precedes `from_date`: {from_date}..{to_date}")
        label = (
            f"{from_date or ''}..{to_date or ''}"
            if (from_date or to_date)
            else "all"
        )
        period = Period(start=start_dt, end=end_dt, label=label)

        show_lc = show.lower() if show else None

        events_iter = shows.events(period)
        # Sort desc by timestamp — history is most-recent-first by user
        # expectation but the provider iterates insertion order.
        collected: list[Any] = []
        for event in events_iter:
            if event.kind not in ("episode_watch", "movie_watch"):
                continue
            payload = event.payload
            if media_type is not None and payload.get("media_type") != media_type:
                continue
            if show_lc is not None and (payload.get("show") or "").lower() != show_lc:
                continue
            collected.append(event)

        collected.sort(key=lambda e: e.timestamp, reverse=True)
        truncated = len(collected) > limit
        trimmed = collected[:limit]

        return {
            "results": [
                {
                    "when": e.timestamp.isoformat(),
                    **e.payload,
                    "title": e.title,
                }
                for e in trimmed
            ],
            "truncated": truncated,
            "total_matching": len(collected),
            "limit": limit,
        }

    @mcp.tool()
    def query_show(title: str) -> dict[str, Any]:  # noqa: PLR0912
        """
        Look up a single show across Trakt history, ratings, and watchlist.

        ``title`` is a case-insensitive exact match on the show title
        (movies aren't addressable through this tool — use ``query_film``
        for those, or ``query_trakt_history`` with ``media_type=movie``).

        Returns:

        * ``show`` — title / year / trakt_id / imdb_id
        * ``plays`` — total episode plays
        * ``distinct_episodes`` — unique ``(season, number)`` pairs seen
        * ``first_watched`` / ``last_watched`` — ISO dates
        * ``recent_episodes`` — last 10 episodes watched, newest first
        * ``show_rating`` — overall show-level rating if any
        * ``episode_ratings`` — per-episode ratings (up to 25)
        * ``on_watchlist`` — is the show currently queued
        """
        q = (title or "").strip().lower()
        if not q:
            raise ValueError("`title` must be non-empty")

        shows = registry.get("shows")
        if shows is None or not shows.is_available():
            return {"found": False, "note": "shows provider unavailable"}

        # Late import keeps the module importable without hpi-modules installed.
        from my.trakt.common import Episode, Show

        show_info: dict[str, Any] | None = None
        plays = 0
        distinct_eps: set[tuple[int, int]] = set()
        first_watched: str | None = None
        last_watched: str | None = None
        recent: list[dict[str, Any]] = []

        for entry in shows.history():
            if not isinstance(entry.media_data, Episode):
                continue
            ep = entry.media_data
            if ep.show.title.lower() != q:
                continue
            if show_info is None:
                show_info = {
                    "title": ep.show.title,
                    "year": ep.show.year,
                    "trakt_id": ep.show.ids.trakt_id,
                    "imdb_id": ep.show.ids.imdb_id,
                }
            plays += 1
            distinct_eps.add((ep.season, ep.episode))
            ts = entry.watched_at.isoformat()
            if first_watched is None or ts < first_watched:
                first_watched = ts
            if last_watched is None or ts > last_watched:
                last_watched = ts
            recent.append(
                {
                    "when": ts,
                    "season": ep.season,
                    "episode": ep.episode,
                    "episode_title": ep.title,
                    "action": entry.action,
                }
            )

        show_rating: int | None = None
        episode_ratings: list[dict[str, Any]] = []
        for r in shows.ratings():
            data = r.media_data
            if isinstance(data, Show) and data.title.lower() == q:
                show_rating = r.rating
                if show_info is None:
                    show_info = {
                        "title": data.title,
                        "year": data.year,
                        "trakt_id": data.ids.trakt_id,
                        "imdb_id": data.ids.imdb_id,
                    }
            elif isinstance(data, Episode) and data.show.title.lower() == q:
                episode_ratings.append(
                    {
                        "season": data.season,
                        "episode": data.episode,
                        "episode_title": data.title,
                        "rating": r.rating,
                        "rated_at": r.rated_at.isoformat(),
                    }
                )
                if show_info is None:
                    show_info = {
                        "title": data.show.title,
                        "year": data.show.year,
                        "trakt_id": data.show.ids.trakt_id,
                        "imdb_id": data.show.ids.imdb_id,
                    }

        on_watchlist = False
        for w in shows.watchlist():
            if w.media_type == "show" and w.media_data.title.lower() == q:
                on_watchlist = True
                if show_info is None:
                    show_info = {
                        "title": w.media_data.title,
                        "year": w.media_data.year,
                        "trakt_id": w.media_data.ids.trakt_id,
                        "imdb_id": w.media_data.ids.imdb_id,
                    }
                break

        if show_info is None:
            return {"found": False, "show": None}

        recent.sort(key=lambda r: r["when"], reverse=True)
        episode_ratings.sort(key=lambda r: (r["season"], r["episode"]))

        return {
            "found": True,
            "show": show_info,
            "plays": plays,
            "distinct_episodes": len(distinct_eps),
            "first_watched": first_watched,
            "last_watched": last_watched,
            "recent_episodes": recent[:10],
            "show_rating": show_rating,
            "episode_ratings": episode_ratings[:25],
            "on_watchlist": on_watchlist,
        }

    @mcp.tool()
    def query_trakt_watchlist(
        media_type: str | None = None,
        added_after: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """
        Raw Trakt watchlist entries, newest first.

        Unlike ``query_watchlist`` (which covers Letterboxd films), this
        endpoint returns both shows and films queued on Trakt.

        * ``media_type`` — ``"show"`` or ``"movie"`` to narrow the list.
        * ``added_after`` — ``YYYY-MM-DD``; trims to items added on or after.
        * ``limit`` — hard cap, max 200.
        """
        limit = max(1, min(limit, TRAKT_WATCHLIST_LIMIT_MAX))
        shows = registry.get("shows")
        if shows is None or not shows.is_available():
            return {"results": [], "truncated": False, "note": "shows provider unavailable"}

        if media_type is not None and media_type not in ("show", "movie"):
            raise ValueError("media_type must be 'show', 'movie', or omitted")

        cutoff = date.fromisoformat(added_after) if added_after else None

        items = shows.watchlist()
        if media_type is not None:
            items = [w for w in items if w.media_type == media_type]
        if cutoff is not None:
            items = [w for w in items if w.listed_at.date() >= cutoff]

        items = sorted(items, key=lambda w: w.listed_at, reverse=True)
        truncated = len(items) > limit
        trimmed = items[:limit]

        return {
            "results": [
                {
                    "title": w.media_data.title,
                    "year": w.media_data.year,
                    "media_type": w.media_type,
                    "added": w.listed_at.date().isoformat(),
                    "trakt_id": w.media_data.ids.trakt_id,
                    "imdb_id": w.media_data.ids.imdb_id,
                }
                for w in trimmed
            ],
            "truncated": truncated,
            "total_matching": len(items),
            "limit": limit,
        }


__all__ = ["register"]
