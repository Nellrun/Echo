"""Pure aggregation for ``films.watchlist_overview``."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from my.letterboxd.common import WatchlistItem


def _label(film) -> str:
    return f"{film.name} ({film.year})" if film.year is not None else film.name


def _decade(year: int) -> str:
    return f"{(year // 10) * 10}s"


def build_overview(items: Iterable[WatchlistItem]) -> dict[str, Any]:
    """
    Summarise the watchlist: total, release-decade distribution, most
    recent additions, and the longest-waiting entries.

    We use *release decade* (``film.year``) rather than the date the
    item was added, because the typical question is "what kind of films
    am I queuing up" rather than "when did I add things" — the latter is
    covered by recent/oldest lists below.
    """
    items = sorted(items, key=lambda w: w.date)

    by_release_decade: Counter[str] = Counter()
    for item in items:
        if item.film.year is not None:
            by_release_decade[_decade(item.film.year)] += 1

    def _row(item: WatchlistItem) -> dict[str, Any]:
        return {
            "film": _label(item.film),
            "year": item.film.year,
            "added": item.date.isoformat(),
            "uri": item.film.uri,
        }

    return {
        "total": len(items),
        "by_release_decade": dict(sorted(by_release_decade.items())),
        "recent_additions": [_row(i) for i in reversed(items[-10:])],
        "oldest_pending": [_row(i) for i in items[:5]],
    }


__all__ = ["build_overview"]
