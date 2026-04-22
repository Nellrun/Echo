"""Pure aggregation for ``shows.watchlist_overview``."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from my.trakt.common import WatchListEntry


def _label(item: WatchListEntry) -> str:
    data = item.media_data
    return f"{data.title} ({data.year})" if data.year is not None else data.title


def _decade(year: int) -> str:
    return f"{(year // 10) * 10}s"


def build_overview(items: Iterable[WatchListEntry]) -> dict[str, Any]:
    """
    Summarise the Trakt watchlist: total, split by type, release-decade
    distribution, most recent additions, and longest-waiting entries.
    """
    items = sorted(items, key=lambda w: w.listed_at)

    by_type: Counter[str] = Counter(w.media_type for w in items)
    by_release_decade: Counter[str] = Counter()
    for item in items:
        if item.media_data.year is not None:
            by_release_decade[_decade(item.media_data.year)] += 1

    def _row(item: WatchListEntry) -> dict[str, Any]:
        return {
            "title": _label(item),
            "year": item.media_data.year,
            "media_type": item.media_type,
            "added": item.listed_at.date().isoformat(),
            "trakt_id": item.media_data.ids.trakt_id,
            "imdb_id": item.media_data.ids.imdb_id,
        }

    return {
        "total": len(items),
        "by_media_type": dict(by_type),
        "by_release_decade": dict(sorted(by_release_decade.items())),
        "recent_additions": [_row(i) for i in reversed(items[-10:])],
        "oldest_pending": [_row(i) for i in items[:5]],
    }


__all__ = ["build_overview"]
