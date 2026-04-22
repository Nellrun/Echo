"""
Pure aggregations for ``shows.taste_profile``.

Long-term signals derivable from the Trakt export alone:

* most-watched shows (all time, by episode plays)
* most-rewatched movies (plays > 1)
* rating distribution across everything rated on Trakt
* favourite decades by release year — weighted by plays

What we deliberately *don't* expose:

* genres — the export doesn't carry them. A future enrichment layer could
  fetch Trakt's show metadata or join TMDB, but shipping a half-real signal
  would mislead downstream LLMs.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from echo.core.aggregations import average, rating_distribution

if TYPE_CHECKING:
    from my.trakt.common import HistoryEntry, Rating

MIN_PLAYS_PER_DECADE = 5


def _decade(year: int) -> str:
    return f"{(year // 10) * 10}s"


def _history_year(entry: HistoryEntry) -> int | None:
    """Pick the release year relevant for the watched entity."""
    from my.trakt.common import Episode, Movie

    if isinstance(entry.media_data, Movie):
        return entry.media_data.year
    if isinstance(entry.media_data, Episode):
        return entry.media_data.show.year
    return None


def _rating_year(rating: Rating) -> int | None:
    from my.trakt.common import Episode, Movie, Season, Show

    data = rating.media_data
    if isinstance(data, (Movie, Show)):
        return data.year
    if isinstance(data, (Episode, Season)):
        return data.show.year
    return None


def build(
    history: Iterable[HistoryEntry], ratings: Iterable[Rating]
) -> dict[str, Any]:
    from my.trakt.common import Episode, Movie

    history = list(history)
    ratings = list(ratings)

    # Per-show play counts (by episodes).
    show_labels: dict[int, str] = {}
    show_plays: Counter[int] = Counter()
    for e in history:
        if isinstance(e.media_data, Episode):
            key = e.media_data.show.ids.trakt_id
            show_labels[key] = (
                f"{e.media_data.show.title} ({e.media_data.show.year})"
                if e.media_data.show.year is not None
                else e.media_data.show.title
            )
            show_plays[key] += 1

    most_watched_shows = [
        {"show": show_labels[trakt_id], "episodes": n}
        for trakt_id, n in show_plays.most_common(10)
    ]

    # Movie rewatches — only films with >1 play surface.
    movie_labels: dict[int, str] = {}
    movie_plays: Counter[int] = Counter()
    for e in history:
        if isinstance(e.media_data, Movie):
            key = e.media_data.ids.trakt_id
            movie_labels[key] = (
                f"{e.media_data.title} ({e.media_data.year})"
                if e.media_data.year is not None
                else e.media_data.title
            )
            movie_plays[key] += 1

    most_rewatched_movies = [
        {"movie": movie_labels[trakt_id], "plays": n}
        for trakt_id, n in movie_plays.most_common(10)
        if n > 1
    ]

    # Favourite decades by total plays (episodes + movies), only if the
    # sample is large enough to be interesting.
    decade_plays: Counter[str] = Counter()
    decade_rating_samples: dict[str, list[int]] = {}
    for e in history:
        year = _history_year(e)
        if year is None:
            continue
        decade_plays[_decade(year)] += 1
    for r in ratings:
        year = _rating_year(r)
        if year is None:
            continue
        decade_rating_samples.setdefault(_decade(year), []).append(r.rating)

    favourite_decades: list[dict[str, Any]] = []
    for dec, count in sorted(
        decade_plays.items(), key=lambda kv: (kv[1], kv[0]), reverse=True
    ):
        if count < MIN_PLAYS_PER_DECADE:
            continue
        samples = decade_rating_samples.get(dec, [])
        favourite_decades.append(
            {
                "decade": dec,
                "plays": count,
                "avg_rating": average(samples) if samples else None,
            }
        )

    return {
        "total_plays": len(history),
        "total_rated": len(ratings),
        "avg_rating": average(r.rating for r in ratings) if ratings else None,
        "rating_distribution": rating_distribution(
            (r.rating for r in ratings), step=1.0
        ),
        "most_watched_shows": most_watched_shows,
        "most_rewatched_movies": most_rewatched_movies,
        "favourite_decades": favourite_decades[:5],
        "coverage_note": (
            "Genres and Trakt-wide averages are not in the export. To unlock "
            "them, add a provider on top of the Trakt API."
        ),
    }


__all__ = ["build"]
