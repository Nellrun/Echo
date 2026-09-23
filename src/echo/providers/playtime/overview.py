"""
Pure aggregation for ``playtime.overview``.

Unlike :mod:`.summary` (which we compute ourselves from the raw session
stream), this view surfaces the aggregator's **own** precomputed totals
from the latest snapshot — ``totals``, ``topGames`` and
``platformBreakdown`` as gwm-stats already rolled them up server-side.
It answers "what's my all-time cross-platform picture" in one call without
re-scanning every session.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from my.gwm_stats.common import PlatformStats, Summary, TopGame


def _hours(d: timedelta | None) -> float | None:
    return round(d.total_seconds() / 3600, 2) if d is not None else None


def _iso(dt: Any) -> str | None:
    return dt.isoformat() if dt is not None else None


def _game_row(g: TopGame) -> dict[str, Any]:
    return {
        "game": g.title_name,
        "platform": g.platform,
        "source": g.source,
        "hours": _hours(g.total_duration),
        "sessions": g.sessions_count,
        "title_id": g.title_id,
    }


def _platform_row(p: PlatformStats) -> dict[str, Any]:
    return {
        "source": p.source,
        "hours": _hours(p.total_duration),
        "sessions": p.sessions_count,
        "games": p.games_count,
    }


def build_overview(summary: Summary, *, trophy_count: int | None = None) -> dict[str, Any]:
    """Summarise the latest gwm-stats snapshot into an LLM-friendly dict."""
    t = summary.totals
    return {
        "player": summary.player_name or summary.name,
        "total_hours": _hours(t.total_duration),
        "total_sessions": t.sessions_count,
        "total_games": t.games_count,
        "avg_session_hours": _hours(t.avg_session),
        "longest_session_hours": _hours(t.longest_session),
        "first_played": _iso(t.first_started_at),
        "last_played": _iso(t.last_ended_at),
        "trophies_earned": trophy_count,
        "top_games": [_game_row(g) for g in summary.top_games[:10]],
        "platform_breakdown": [_platform_row(p) for p in summary.platform_breakdown],
        "fetched_at_utc": _iso(summary.fetched_at_utc),
    }


__all__ = ["build_overview"]
