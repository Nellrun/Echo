"""Pure aggregations for ``gaming.play_summary``."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from echo.core.aggregations import daily_distribution

if TYPE_CHECKING:
    from echo.core.types import Period


def build(sessions: Iterable, *, period: Period) -> dict[str, Any]:
    """
    Aggregate a pre-filtered iterable of sessions into a summary dict.

    A "session" here is any object exposing ``when``, ``game``, ``platform``,
    ``duration_seconds`` and ``duration_hours``. That matches the
    :func:`echo.providers.gaming._normalise` output while letting tests
    inject simple dataclasses.

    Ranks top games by **total hours played** rather than session count —
    a burst of short sessions shouldn't outweigh genuine time-on-game. Same
    choice underpins the taste classification in :mod:`.taste`.
    """
    total_sessions = 0
    total_seconds = 0
    hours_by_game: dict[str, float] = defaultdict(float)
    sessions_by_game: dict[str, int] = defaultdict(int)
    hours_by_platform: dict[str, float] = defaultdict(float)
    moments: list = []

    for s in sessions:
        total_sessions += 1
        total_seconds += s.duration_seconds
        game = s.game or "(unknown)"
        platform = s.platform or "(unknown)"
        hours_by_game[game] += s.duration_hours
        sessions_by_game[game] += 1
        hours_by_platform[platform] += s.duration_hours
        moments.append(s.when)

    # Sort top_games by hours desc; include session count so callers don't
    # need to make a second pass for that signal.
    top_games_raw = sorted(
        hours_by_game.items(), key=lambda kv: kv[1], reverse=True
    )[:10]
    top_games = [
        {
            "value": game,
            "hours": round(hours, 2),
            "sessions": sessions_by_game[game],
        }
        for game, hours in top_games_raw
    ]

    by_platform = {
        platform: round(hours, 2)
        for platform, hours in sorted(
            hours_by_platform.items(), key=lambda kv: kv[1], reverse=True
        )
    }

    return {
        "period": period.label or "custom",
        "total_sessions": total_sessions,
        "total_hours": round(total_seconds / 3600, 2),
        "unique_games": len(hours_by_game),
        "top_games": top_games,
        "hours_by_platform": by_platform,
        "daily_distribution": daily_distribution(moments),
    }


__all__ = ["build"]
