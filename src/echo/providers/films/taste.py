"""
Pure aggregations for ``films.taste_profile``.

Long-term taste signals derivable from the Letterboxd export alone:

* favourite decades (with a minimum sample size to avoid noise)
* most-rewatched films
* distribution of ratings across the whole catalogue

What we deliberately *don't* expose yet:

* favourite directors — the export carries no director field. Would need
  a TMDB or Letterboxd scraper provider on top of ``my.letterboxd``.
* overrated/underrated vs Letterboxd avg — same reason; not in the export.

The point of shipping the MVP without these fields is to avoid hallucinating
signals we can't actually compute.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from echo.core.aggregations import average, rating_distribution

if TYPE_CHECKING:
    from my.letterboxd.common import Diary, Rating

MIN_FILMS_PER_DECADE = 5


def _decade(year: int) -> str:
    return f"{(year // 10) * 10}s"


def build(
    diary_entries: Iterable[Diary], ratings: Iterable[Rating]
) -> dict[str, Any]:
    diary_entries = list(diary_entries)
    ratings = list(ratings)

    decade_counts: Counter[str] = Counter()
    decade_ratings: dict[str, list[float]] = {}
    for r in ratings:
        if r.film.year is None:
            continue
        dec = _decade(r.film.year)
        decade_counts[dec] += 1
        decade_ratings.setdefault(dec, []).append(r.rating)

    favourite_decades: list[dict[str, Any]] = []
    for dec, count in sorted(
        decade_counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True
    ):
        if count < MIN_FILMS_PER_DECADE:
            continue
        favourite_decades.append(
            {
                "decade": dec,
                "films": count,
                "avg_rating": average(decade_ratings[dec]),
            }
        )

    rewatch_counts: Counter[str] = Counter()
    rewatch_labels: dict[str, str] = {}
    for e in diary_entries:
        key = e.film.uri
        rewatch_counts[key] += 1
        rewatch_labels[key] = (
            f"{e.film.name} ({e.film.year})"
            if e.film.year is not None
            else e.film.name
        )

    most_rewatched = [
        {"film": rewatch_labels[uri], "watches": n}
        for uri, n in rewatch_counts.most_common(10)
        if n > 1
    ]

    return {
        "total_rated_films": len(ratings),
        "avg_rating": average(r.rating for r in ratings) if ratings else None,
        "rating_distribution": rating_distribution(
            r.rating for r in ratings
        ),
        "favourite_decades": favourite_decades[:5],
        "most_rewatched": most_rewatched,
        "coverage_note": (
            "Director and Letterboxd-average comparisons are not available "
            "from the export — add a scraper/TMDB provider to unlock."
        ),
    }


__all__ = ["build"]
