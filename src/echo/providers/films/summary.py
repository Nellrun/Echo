"""Pure aggregations for ``films.watched_summary``."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from echo.core.aggregations import (
    average,
    daily_distribution,
    rating_distribution,
    top_n,
)

if TYPE_CHECKING:
    from my.letterboxd.common import Diary

    from echo.core.types import Period


def _watch_date(entry: Diary):
    return entry.watched_date or entry.logged_date


def build(entries: Iterable[Diary], *, period: Period) -> dict[str, Any]:
    """
    Aggregate a pre-filtered iterable of ``Diary`` entries into a summary dict.

    ``entries`` must already be restricted to ``period`` — filtering happens
    upstream in the provider so this function stays dependency-free and
    trivially testable.
    """
    entries = list(entries)
    rated = [e for e in entries if e.rating is not None]

    # Cheap string representations — the provider shouldn't leak `Film`
    # dataclasses through a JSON boundary.
    def _film_label(e: Diary) -> str:
        return (
            f"{e.film.name} ({e.film.year})"
            if e.film.year is not None
            else e.film.name
        )

    top_rated = sorted(
        rated, key=lambda e: (e.rating or 0.0, _watch_date(e)), reverse=True
    )[:10]

    return {
        "period": period.label or "custom",
        "count": len(entries),
        "rewatches_count": sum(1 for e in entries if e.rewatch),
        "avg_rating": average(float(e.rating) for e in rated) if rated else None,
        "rating_distribution": rating_distribution(e.rating for e in entries),
        "top_rated": [
            {
                "film": _film_label(e),
                "rating": e.rating,
                "date": _watch_date(e).isoformat(),
                "rewatch": e.rewatch,
            }
            for e in top_rated
        ],
        "most_watched_films": top_n(
            (_film_label(e) for e in entries), n=5, key="watches"
        ),
        "daily_distribution": daily_distribution(_watch_date(e) for e in entries),
    }


__all__ = ["build"]
