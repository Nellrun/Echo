"""
Shared fixtures. A thin in-test re-declaration of the Letterboxd domain
classes lets us exercise the aggregation functions without importing
``my.letterboxd`` (which requires the upstream HPI and user config).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime


@dataclass(frozen=True, slots=True)
class FakeFilm:
    name: str
    year: int | None
    uri: str


@dataclass(frozen=True, slots=True)
class FakeDiary:
    film: FakeFilm
    logged_date: date
    watched_date: date | None = None
    rating: float | None = None
    rewatch: bool = False
    tags: tuple[str, ...] = field(default_factory=tuple)
    review: str | None = None


@dataclass(frozen=True, slots=True)
class FakeRating:
    film: FakeFilm
    rating: float
    date: date


@dataclass(frozen=True, slots=True)
class FakeWatchlistItem:
    film: FakeFilm
    date: date


def film(name: str, year: int | None = 2020, slug: str | None = None) -> FakeFilm:
    slug = slug or name.lower().replace(" ", "-")
    return FakeFilm(name=name, year=year, uri=f"https://letterboxd.com/film/{slug}/")


# ---------------------------------------------------------------------------
# Trakt (``my.trakt.common``) builder helpers. The real dataclasses live
# outside the repo; we import them so provider tests exercise the exact
# shapes the Trakt dump produces. No monkeypatching of ``my.trakt`` here —
# each test file wires its own stub module.
# ---------------------------------------------------------------------------


def trakt_site_ids(trakt_id: int, *, imdb: str | None = None, slug: str | None = None):
    from my.trakt.common import SiteIds

    return SiteIds(trakt_id=trakt_id, imdb_id=imdb, trakt_slug=slug)


def trakt_movie(title: str, year: int | None = 2020, *, trakt_id: int = 1):
    from my.trakt.common import Movie

    return Movie(title=title, year=year, ids=trakt_site_ids(trakt_id))


def trakt_show(title: str, year: int | None = 2015, *, trakt_id: int = 100):
    from my.trakt.common import Show

    return Show(title=title, year=year, ids=trakt_site_ids(trakt_id))


def trakt_episode(
    show,
    season: int,
    episode: int,
    *,
    title: str | None = "Pilot",
    trakt_id: int = 9000,
):
    from my.trakt.common import Episode

    return Episode(
        title=title,
        season=season,
        episode=episode,
        ids=trakt_site_ids(trakt_id),
        show=show,
    )


def trakt_history(
    watched_at: datetime,
    media_data,
    *,
    history_id: int = 1,
    action: str = "watch",
):
    from my.trakt.common import HistoryEntry

    media_type = "episode" if getattr(media_data, "season", None) is not None else "movie"
    if watched_at.tzinfo is None:
        watched_at = watched_at.replace(tzinfo=UTC)
    return HistoryEntry(
        history_id=history_id,
        watched_at=watched_at,
        action=action,
        media_type=media_type,  # type: ignore[arg-type]
        media_data=media_data,
    )


def trakt_rating(media_data, rating: int, *, rated_at: datetime | None = None):
    from my.trakt.common import Episode, Movie, Season, Show
    from my.trakt.common import Rating as _R

    if isinstance(media_data, Movie):
        media_type = "movie"
    elif isinstance(media_data, Show):
        media_type = "show"
    elif isinstance(media_data, Season):
        media_type = "season"
    elif isinstance(media_data, Episode):
        media_type = "episode"
    else:
        raise TypeError(f"unsupported rating media_data: {type(media_data).__name__}")
    when = rated_at or datetime(2024, 1, 1, tzinfo=UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return _R(rated_at=when, rating=rating, media_type=media_type, media_data=media_data)  # type: ignore[arg-type]


def trakt_watchlist(
    media_data,
    listed_at: datetime,
    *,
    listed_id: int = 1,
):
    from my.trakt.common import Show
    from my.trakt.common import WatchListEntry as _W

    media_type = "show" if isinstance(media_data, Show) else "movie"
    if listed_at.tzinfo is None:
        listed_at = listed_at.replace(tzinfo=UTC)
    return _W(
        listed_at=listed_at,
        listed_at_id=listed_id,
        media_type=media_type,  # type: ignore[arg-type]
        media_data=media_data,
    )
