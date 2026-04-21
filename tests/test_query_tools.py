from __future__ import annotations

import sys
import types
from collections.abc import Iterator
from datetime import date, datetime

import pytest

from tests.conftest import FakeDiary, FakeRating, FakeWatchlistItem, film

from echo.core.registry import Registry
from echo.core.types import Event, Period


class MockMCP:
    """Minimal FastMCP stand-in that captures tool-decorated callables by name."""

    def __init__(self) -> None:
        self.tools: dict[str, callable] = {}

    def tool(self, *args, **kwargs):  # noqa: ARG002
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorator


class StubFilmsProvider:
    name = "films"

    def __init__(
        self,
        events: list[Event],
        ratings: list[FakeRating] | None = None,
        watchlist: list[FakeWatchlistItem] | None = None,
    ) -> None:
        self._events = events
        self._ratings = ratings or []
        self._watchlist = watchlist or []

    def is_available(self) -> bool:
        return True

    def events(self, period: Period) -> Iterator[Event]:
        for e in self._events:
            if period.contains(e.timestamp):
                yield e

    def ratings(self) -> list[FakeRating]:
        return list(self._ratings)

    def watchlist(self) -> list[FakeWatchlistItem]:
        return list(self._watchlist)

    def register_tools(self, mcp) -> None:  # noqa: ARG002
        pass


class StubMusicProvider:
    name = "music"

    def __init__(self, events: list[Event]) -> None:
        self._events = events

    def is_available(self) -> bool:
        return True

    def events(self, period: Period) -> Iterator[Event]:
        for e in self._events:
            if period.contains(e.timestamp):
                yield e

    def register_tools(self, mcp) -> None:  # noqa: ARG002
        pass


def _diary_event(
    day: date,
    name: str,
    rating: float | None = None,
    rewatch: bool = False,
    review: str | None = None,
    tags: list[str] | None = None,
) -> Event:
    return Event(
        timestamp=datetime.combine(day, datetime.min.time()),
        source="films",
        kind="diary",
        title=name,
        payload={
            "film": name,
            "year": 2020,
            "rating": rating,
            "rewatch": rewatch,
            "uri": f"/film/{name}/",
            "review": review,
            "tags": tags or [],
        },
    )


def _watchlist_event(day: date, name: str) -> Event:
    return Event(
        timestamp=datetime.combine(day, datetime.min.time()),
        source="films",
        kind="watchlist_add",
        title=f"+ watchlist: {name}",
        payload={"film": name, "year": 2020, "uri": f"/film/{name}/"},
    )


def _scrobble(ts: datetime, artist: str, track: str) -> Event:
    return Event(
        timestamp=ts,
        source="music",
        kind="scrobble",
        title=f"{artist} — {track}",
        payload={"artist": artist, "track": track, "album": None},
    )


@pytest.fixture()
def mcp_with_registry() -> tuple[MockMCP, Registry]:
    from echo.tools import query_tools

    mcp = MockMCP()
    reg = Registry()
    query_tools.register(mcp, reg)
    return mcp, reg


def test_query_diary_respects_inclusive_upper_bound(mcp_with_registry) -> None:
    mcp, reg = mcp_with_registry
    reg.register(StubFilmsProvider([
        _diary_event(date(2026, 2, 28), "Last"),
        _diary_event(date(2026, 3, 1), "NextMonth"),
    ]))
    out = mcp.tools["query_diary"](from_date="2026-02-01", to_date="2026-02-28")
    assert [r["film"] for r in out["results"]] == ["Last"]


def test_query_diary_caps_limit_at_100(mcp_with_registry) -> None:
    mcp, reg = mcp_with_registry
    # 150 diary events spread across 2026 — the cap applies regardless of span.
    entries = []
    for i in range(150):
        month = (i % 12) + 1
        day = (i % 28) + 1
        entries.append(_diary_event(date(2026, month, day), f"F{i}"))
    reg.register(StubFilmsProvider(entries))
    out = mcp.tools["query_diary"](from_date="2026-01-01", to_date="2026-12-31", limit=500)
    assert out["limit"] == 100
    assert len(out["results"]) == 100
    assert out["truncated"] is True


def test_query_diary_min_rating_excludes_unrated(mcp_with_registry) -> None:
    mcp, reg = mcp_with_registry
    reg.register(StubFilmsProvider([
        _diary_event(date(2026, 2, 1), "Rated", rating=4.0),
        _diary_event(date(2026, 2, 2), "Unrated", rating=None),
    ]))
    out = mcp.tools["query_diary"](
        from_date="2026-02-01", to_date="2026-02-28", min_rating=3.5
    )
    assert [r["film"] for r in out["results"]] == ["Rated"]


def test_query_diary_returns_note_when_provider_absent(mcp_with_registry) -> None:
    mcp, _ = mcp_with_registry
    out = mcp.tools["query_diary"](from_date="2026-02-01", to_date="2026-02-28")
    assert out["results"] == []
    assert "unavailable" in out["note"]


def test_query_scrobbles_artist_filter_case_insensitive(mcp_with_registry) -> None:
    mcp, reg = mcp_with_registry
    reg.register(StubMusicProvider([
        _scrobble(datetime(2026, 2, 10, 10), "Radiohead", "Idioteque"),
        _scrobble(datetime(2026, 2, 10, 11), "Björk", "Hyperballad"),
    ]))
    out = mcp.tools["query_scrobbles"](
        from_date="2026-02-01", to_date="2026-02-28", artist="radiohead"
    )
    assert [r["artist"] for r in out["results"]] == ["Radiohead"]


def test_query_scrobbles_caps_limit_at_200(mcp_with_registry) -> None:
    mcp, reg = mcp_with_registry
    # 300 scrobbles spread across Feb so we don't run out of hours.
    scrobs = [
        _scrobble(
            datetime(2026, 2, (i % 28) + 1, i % 24, (i * 7) % 60),
            "A",
            f"t{i}",
        )
        for i in range(300)
    ]
    reg.register(StubMusicProvider(scrobs))
    out = mcp.tools["query_scrobbles"](
        from_date="2026-02-01", to_date="2026-02-28", limit=1000
    )
    assert out["limit"] == 200
    assert len(out["results"]) == 200
    assert out["truncated"] is True


def test_query_film_requires_one_arg(mcp_with_registry) -> None:
    mcp, _ = mcp_with_registry
    with pytest.raises(ValueError, match="title"):
        mcp.tools["query_film"]()


def test_query_film_by_title_returns_all_watches(mcp_with_registry) -> None:
    mcp, reg = mcp_with_registry
    reg.register(StubFilmsProvider([
        _diary_event(date(2024, 1, 1), "Amélie", rating=5.0),
        _diary_event(date(2026, 2, 10), "Amélie", rating=5.0, rewatch=True),
        _diary_event(date(2025, 6, 1), "Other"),
    ]))
    out = mcp.tools["query_film"](title="amélie")
    assert out["found"] is True
    assert [w["date"] for w in out["watches"]] == ["2024-01-01", "2026-02-10"]


def test_query_film_includes_review_and_tags_per_watch(mcp_with_registry) -> None:
    mcp, reg = mcp_with_registry
    reg.register(StubFilmsProvider([
        _diary_event(
            date(2026, 2, 1),
            "Memento",
            rating=4.5,
            review="dense on rewatch",
            tags=["noir"],
        ),
    ]))
    out = mcp.tools["query_film"](title="memento")
    assert out["found"] is True
    w = out["watches"][0]
    assert w["review"] == "dense on rewatch"
    assert w["tags"] == ["noir"]
    assert w["rating"] == 4.5


def test_query_film_current_rating_from_ratings_provider(mcp_with_registry) -> None:
    """``current_rating`` is enriched via ``films.ratings()``, matched by uri."""
    mcp, reg = mcp_with_registry
    shared_uri = "https://letterboxd.com/film/amélie/"
    diary_evt = Event(
        timestamp=datetime(2024, 1, 1),
        source="films",
        kind="diary",
        title="Amélie",
        payload={
            "film": "Amélie",
            "year": 2001,
            "rating": 4.5,
            "rewatch": False,
            "uri": shared_uri,
            "review": None,
            "tags": [],
        },
    )
    amelie = film("Amélie", year=2001, slug="amélie")
    reg.register(StubFilmsProvider(
        [diary_evt],
        ratings=[FakeRating(film=amelie, rating=5.0, date=date(2026, 1, 1))],
    ))
    out = mcp.tools["query_film"](letterboxd_uri=shared_uri)
    assert out["found"] is True
    assert out["current_rating"] == 5.0


def test_query_film_on_watchlist_flag(mcp_with_registry) -> None:
    mcp, reg = mcp_with_registry
    shared_uri = "https://letterboxd.com/film/dune/"
    diary_evt = Event(
        timestamp=datetime(2026, 2, 1),
        source="films",
        kind="diary",
        title="Dune",
        payload={
            "film": "Dune",
            "year": 2021,
            "rating": None,
            "rewatch": False,
            "uri": shared_uri,
            "review": None,
            "tags": [],
        },
    )
    reg.register(StubFilmsProvider(
        [diary_evt],
        watchlist=[FakeWatchlistItem(
            film=film("Dune", year=2021, slug="dune"),
            date=date(2026, 1, 1),
        )],
    ))
    out = mcp.tools["query_film"](letterboxd_uri=shared_uri)
    assert out["on_watchlist"] is True


def test_query_film_ignores_watchlist_add_events(mcp_with_registry) -> None:
    """``query_film`` should only consider ``kind='diary'`` events as watches."""
    mcp, reg = mcp_with_registry
    reg.register(StubFilmsProvider([
        _watchlist_event(date(2026, 1, 1), "Dune"),
    ]))
    out = mcp.tools["query_film"](title="dune")
    assert out["found"] is False
    assert out["watches"] == []


def test_query_film_returns_not_found_when_no_match(mcp_with_registry) -> None:
    mcp, reg = mcp_with_registry
    reg.register(StubFilmsProvider([_diary_event(date(2026, 1, 1), "Other")]))
    out = mcp.tools["query_film"](title="missing")
    assert out["found"] is False


def test_query_diary_ignores_watchlist_add_events(mcp_with_registry) -> None:
    mcp, reg = mcp_with_registry
    reg.register(StubFilmsProvider([
        _diary_event(date(2026, 2, 5), "Watched"),
        _watchlist_event(date(2026, 2, 6), "Queued"),
    ]))
    out = mcp.tools["query_diary"](from_date="2026-02-01", to_date="2026-02-28")
    assert [r["film"] for r in out["results"]] == ["Watched"]


def test_query_watchlist_returns_items_newest_first(mcp_with_registry) -> None:
    mcp, reg = mcp_with_registry
    reg.register(StubFilmsProvider(
        [],
        watchlist=[
            FakeWatchlistItem(film=film("Old"), date=date(2026, 1, 1)),
            FakeWatchlistItem(film=film("New"), date=date(2026, 3, 1)),
            FakeWatchlistItem(film=film("Mid"), date=date(2026, 2, 1)),
        ],
    ))
    out = mcp.tools["query_watchlist"]()
    assert [r["film"] for r in out["results"]] == ["New", "Mid", "Old"]
    assert out["total_matching"] == 3
    assert out["truncated"] is False


def test_query_watchlist_filters_by_added_after(mcp_with_registry) -> None:
    mcp, reg = mcp_with_registry
    reg.register(StubFilmsProvider(
        [],
        watchlist=[
            FakeWatchlistItem(film=film("Old"), date=date(2026, 1, 1)),
            FakeWatchlistItem(film=film("Kept"), date=date(2026, 3, 15)),
        ],
    ))
    out = mcp.tools["query_watchlist"](added_after="2026-02-01")
    assert [r["film"] for r in out["results"]] == ["Kept"]


def test_query_watchlist_caps_limit_at_200(mcp_with_registry) -> None:
    mcp, reg = mcp_with_registry
    items = [
        FakeWatchlistItem(
            film=film(f"F{i}"),
            date=date(2026, (i % 12) + 1, (i % 28) + 1),
        )
        for i in range(300)
    ]
    reg.register(StubFilmsProvider([], watchlist=items))
    out = mcp.tools["query_watchlist"](limit=1000)
    assert out["limit"] == 200
    assert len(out["results"]) == 200
    assert out["truncated"] is True
    assert out["total_matching"] == 300


def test_query_watchlist_returns_note_when_provider_absent(mcp_with_registry) -> None:
    mcp, _ = mcp_with_registry
    out = mcp.tools["query_watchlist"]()
    assert out["results"] == []
    assert "unavailable" in out["note"]


# -- query_film_search -----------------------------------------------------


def test_query_film_search_rejects_empty_query(mcp_with_registry) -> None:
    mcp, _ = mcp_with_registry
    with pytest.raises(ValueError, match="non-empty"):
        mcp.tools["query_film_search"](query="   ")


def test_query_film_search_matches_substring_case_insensitive(mcp_with_registry) -> None:
    mcp, reg = mcp_with_registry
    reg.register(StubFilmsProvider([
        _diary_event(date(2026, 2, 1), "Amélie", rating=5.0),
        _diary_event(date(2026, 2, 2), "Amadeus", rating=4.0),
        _diary_event(date(2026, 2, 3), "Unrelated"),
    ]))
    out = mcp.tools["query_film_search"](query="ama")
    films = [r["film"] for r in out["results"]]
    assert films == ["Amadeus"]


def test_query_film_search_reports_watched_counts_and_last_watched(mcp_with_registry) -> None:
    mcp, reg = mcp_with_registry
    reg.register(StubFilmsProvider([
        _diary_event(date(2024, 5, 1), "Memento", rating=4.5),
        _diary_event(date(2026, 1, 15), "Memento", rating=4.5, rewatch=True),
    ]))
    out = mcp.tools["query_film_search"](query="memento")
    row = out["results"][0]
    assert row["watched"] is True
    assert row["watches_count"] == 2
    assert row["last_watched"] == "2026-01-15"


def test_query_film_search_surfaces_ratings_and_watchlist_for_unseen(
    mcp_with_registry,
) -> None:
    mcp, reg = mcp_with_registry
    dune = film("Dune", year=2021)
    arrival = film("Arrival", year=2016)
    reg.register(StubFilmsProvider(
        [],
        ratings=[FakeRating(film=dune, rating=4.0, date=date(2026, 1, 1))],
        watchlist=[FakeWatchlistItem(film=arrival, date=date(2026, 2, 1))],
    ))
    dune_out = mcp.tools["query_film_search"](query="dune")
    dune_row = dune_out["results"][0]
    assert dune_row["watched"] is False
    assert dune_row["user_rating"] == 4.0
    assert dune_row["on_watchlist"] is False

    arrival_out = mcp.tools["query_film_search"](query="arrival")
    arrival_row = arrival_out["results"][0]
    assert arrival_row["watched"] is False
    assert arrival_row["on_watchlist"] is True
    assert arrival_row["user_rating"] is None


def test_query_film_search_orders_watched_then_rated_then_queued(
    mcp_with_registry,
) -> None:
    mcp, reg = mcp_with_registry
    # "x" matches all three films below.
    seen = film("X-seen")
    rated = film("X-rated")
    queued = film("X-queued")
    diary_evt = Event(
        timestamp=datetime(2026, 1, 1),
        source="films",
        kind="diary",
        title="X-seen",
        payload={
            "film": "X-seen", "year": 2020, "rating": None, "rewatch": False,
            "uri": seen.uri, "review": None, "tags": [],
        },
    )
    reg.register(StubFilmsProvider(
        [diary_evt],
        ratings=[FakeRating(film=rated, rating=4.0, date=date(2026, 1, 1))],
        watchlist=[FakeWatchlistItem(film=queued, date=date(2026, 1, 1))],
    ))
    out = mcp.tools["query_film_search"](query="x-")
    assert [r["film"] for r in out["results"]] == ["X-seen", "X-rated", "X-queued"]


def test_query_film_search_caps_limit(mcp_with_registry) -> None:
    mcp, reg = mcp_with_registry
    entries = [
        _diary_event(date(2026, (i % 12) + 1, (i % 28) + 1), f"X-{i}")
        for i in range(80)
    ]
    reg.register(StubFilmsProvider(entries))
    out = mcp.tools["query_film_search"](query="x-", limit=200)
    assert out["limit"] == 50
    assert len(out["results"]) == 50
    assert out["truncated"] is True
    assert out["total_matching"] == 80


def test_query_film_search_note_when_provider_absent(mcp_with_registry) -> None:
    mcp, _ = mcp_with_registry
    out = mcp.tools["query_film_search"](query="anything")
    assert out["results"] == []
    assert "unavailable" in out["note"]


# -- query_artist ----------------------------------------------------------


def _scrobble_with_album(
    ts: datetime, artist: str, track: str, album: str | None = None
) -> Event:
    return Event(
        timestamp=ts,
        source="music",
        kind="scrobble",
        title=f"{artist} — {track}",
        payload={"artist": artist, "track": track, "album": album},
    )


def test_query_artist_rejects_empty_name(mcp_with_registry) -> None:
    mcp, _ = mcp_with_registry
    with pytest.raises(ValueError, match="non-empty"):
        mcp.tools["query_artist"](name="")


def test_query_artist_substring_match_returns_stats(mcp_with_registry) -> None:
    mcp, reg = mcp_with_registry
    reg.register(StubMusicProvider([
        _scrobble_with_album(datetime(2024, 1, 1, 10), "Radiohead", "Idioteque", "Kid A"),
        _scrobble_with_album(datetime(2026, 2, 1, 11), "Radiohead", "Idioteque", "Kid A"),
        _scrobble_with_album(datetime(2026, 2, 1, 12), "Radiohead", "Kid A", "Kid A"),
        _scrobble_with_album(datetime(2026, 2, 2, 12), "Björk", "Hyperballad", "Post"),
    ]))
    out = mcp.tools["query_artist"](name="radio")
    assert len(out["results"]) == 1
    r = out["results"][0]
    assert r["artist"] == "Radiohead"
    assert r["total_scrobbles"] == 3
    assert r["first_played"].startswith("2024-01-01")
    assert r["last_played"].startswith("2026-02-01")
    assert r["distinct_tracks"] == 2
    assert r["distinct_albums"] == 1
    top = {t["track"]: t["plays"] for t in r["top_tracks"]}
    assert top["Idioteque"] == 2
    assert top["Kid A"] == 1


def test_query_artist_returns_empty_for_no_match(mcp_with_registry) -> None:
    mcp, reg = mcp_with_registry
    reg.register(StubMusicProvider([
        _scrobble_with_album(datetime(2026, 2, 1, 10), "Radiohead", "Idioteque"),
    ]))
    out = mcp.tools["query_artist"](name="beatles")
    assert out["results"] == []
    assert out["total_matching"] == 0


def test_query_artist_note_when_provider_absent(mcp_with_registry) -> None:
    mcp, _ = mcp_with_registry
    out = mcp.tools["query_artist"](name="anyone")
    assert out["results"] == []
    assert "unavailable" in out["note"]


# -- query_album -----------------------------------------------------------


def test_query_album_rejects_empty(mcp_with_registry) -> None:
    mcp, _ = mcp_with_registry
    with pytest.raises(ValueError, match="non-empty"):
        mcp.tools["query_album"](album="")


def test_query_album_groups_by_artist_album(mcp_with_registry) -> None:
    mcp, reg = mcp_with_registry
    reg.register(StubMusicProvider([
        _scrobble_with_album(datetime(2026, 2, 1, 10), "Radiohead", "Everything In Its Right Place", "Kid A"),
        _scrobble_with_album(datetime(2026, 2, 1, 11), "Radiohead", "Idioteque", "Kid A"),
        _scrobble_with_album(datetime(2026, 2, 2, 10), "Björk", "Kid", "Kid A tribute"),
    ]))
    out = mcp.tools["query_album"](album="kid a")
    # Both albums contain "kid a" substring.
    pairs = {(r["artist"], r["album"]) for r in out["results"]}
    assert ("Radiohead", "Kid A") in pairs
    assert ("Björk", "Kid A tribute") in pairs
    rhead = next(r for r in out["results"] if r["artist"] == "Radiohead")
    assert rhead["total_scrobbles"] == 2
    assert rhead["distinct_tracks"] == 2


def test_query_album_artist_filter_is_exact(mcp_with_registry) -> None:
    mcp, reg = mcp_with_registry
    reg.register(StubMusicProvider([
        _scrobble_with_album(datetime(2026, 2, 1, 10), "Radiohead", "Idioteque", "Kid A"),
        _scrobble_with_album(datetime(2026, 2, 1, 11), "Björk", "Kid", "Kid A tribute"),
    ]))
    out = mcp.tools["query_album"](album="kid a", artist="radiohead")
    assert [(r["artist"], r["album"]) for r in out["results"]] == [("Radiohead", "Kid A")]


def test_query_album_skips_empty_album_field(mcp_with_registry) -> None:
    """Scrobbles without album info should never match — otherwise every
    bare query would return the whole library."""
    mcp, reg = mcp_with_registry
    reg.register(StubMusicProvider([
        _scrobble_with_album(datetime(2026, 2, 1, 10), "Radiohead", "Idioteque", None),
    ]))
    out = mcp.tools["query_album"](album="anything")
    assert out["results"] == []


def test_query_album_note_when_provider_absent(mcp_with_registry) -> None:
    mcp, _ = mcp_with_registry
    out = mcp.tools["query_album"](album="anything")
    assert out["results"] == []
    assert "unavailable" in out["note"]
