"""
Pure aggregation for ``playtime.play_summary``.

Like :mod:`echo.providers.gaming.summary` but cross-platform: gwm-stats
spans PSN, Steam and Nintendo, so the summary carries an extra
``hours_by_source`` dimension alongside ``hours_by_platform``. Top games
are ranked by **total hours played**, mirroring the gaming/music
convention — a burst of short sessions shouldn't outrank genuine
time-on-game.
"""

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

    A "session" is any object exposing ``when``, ``game``, ``platform``,
    ``source``, ``duration_seconds`` and ``duration_hours`` — the shape
    produced by :func:`echo.providers.playtime._normalise_session`, which
    tests can also build directly.
    """
    total_sessions = 0
    total_seconds = 0
    hours_by_game: dict[str, float] = defaultdict(float)
    sessions_by_game: dict[str, int] = defaultdict(int)
    source_by_game: dict[str, str] = {}
    hours_by_platform: dict[str, float] = defaultdict(float)
    hours_by_source: dict[str, float] = defaultdict(float)
    moments: list = []

    for s in sessions:
        total_sessions += 1
        total_seconds += s.duration_seconds
        game = s.game or "(unknown)"
        platform = s.platform or "(unknown)"
        source = s.source or "(unknown)"
        hours_by_game[game] += s.duration_hours
        sessions_by_game[game] += 1
        # First source wins — a title belongs to one backend in practice.
        source_by_game.setdefault(game, source)
        hours_by_platform[platform] += s.duration_hours
        hours_by_source[source] += s.duration_hours
        moments.append(s.when)

    top_games_raw = sorted(
        hours_by_game.items(), key=lambda kv: kv[1], reverse=True
    )[:10]
    top_games = [
        {
            "value": game,
            "hours": round(hours, 2),
            "sessions": sessions_by_game[game],
            "source": source_by_game.get(game),
        }
        for game, hours in top_games_raw
    ]

    def _by(mapping: dict[str, float]) -> dict[str, float]:
        return {
            k: round(v, 2)
            for k, v in sorted(mapping.items(), key=lambda kv: kv[1], reverse=True)
        }

    return {
        "period": period.label or "custom",
        "total_sessions": total_sessions,
        "total_hours": round(total_seconds / 3600, 2),
        "unique_games": len(hours_by_game),
        "top_games": top_games,
        "hours_by_platform": _by(hours_by_platform),
        "hours_by_source": _by(hours_by_source),
        "daily_distribution": daily_distribution(moments),
    }


__all__ = ["build"]
