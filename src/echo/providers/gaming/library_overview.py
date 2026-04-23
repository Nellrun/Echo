"""Pure aggregation for ``gaming.library_overview``."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from my.ps_timetracker.common import Library, LibraryGame


def _hours(game: LibraryGame) -> float | None:
    d = game.total_duration
    return d.total_seconds() / 3600 if d is not None else None


def _row(game: LibraryGame) -> dict[str, Any]:
    return {
        "game": game.title,
        "platform": game.platform,
        "hours": round(h, 2) if (h := _hours(game)) is not None else None,
        "sessions": game.sessions_count,
        "last_played": (
            game.last_played_local.isoformat() if game.last_played_local else None
        ),
    }


def build_overview(snapshot: Library) -> dict[str, Any]:
    """
    Summarise the ps-timetracker library snapshot: counts, platform mix,
    top-by-hours, and the most-recently-played titles.

    Unlike films' watchlist, there is no "added" timestamp for library
    entries — ps-timetracker only exposes aggregate stats and last-played,
    so the snapshot answers "what have I played (ever / recently / most)"
    rather than "what's queued up".
    """
    games = list(snapshot.games)
    total = len(games)

    by_platform: Counter[str] = Counter()
    total_seconds = 0.0
    for g in games:
        if g.platform:
            by_platform[g.platform] += 1
        if g.total_duration is not None:
            total_seconds += g.total_duration.total_seconds()

    # Top by total hours. ``total_duration is None`` goes last (effectively 0).
    def _sort_hours(g: LibraryGame) -> float:
        return g.total_duration.total_seconds() if g.total_duration else 0.0

    top_by_hours = sorted(games, key=_sort_hours, reverse=True)[:10]

    # Recently played. ``None`` last_played falls to the back.
    def _sort_last(g: LibraryGame) -> tuple[int, float]:
        if g.last_played_local is None:
            return (1, 0.0)
        return (0, -g.last_played_local.timestamp())

    recently_played = sorted(games, key=_sort_last)[:10]

    return {
        "total_games": total,
        "total_hours": round(total_seconds / 3600, 2),
        "by_platform": dict(sorted(by_platform.items())),
        "top_by_hours": [_row(g) for g in top_by_hours],
        "recently_played": [_row(g) for g in recently_played],
        "profile": snapshot.profile,
        "fetched_at_utc": (
            snapshot.fetched_at_utc.isoformat()
            if snapshot.fetched_at_utc is not None
            else None
        ),
    }


__all__ = ["build_overview"]
