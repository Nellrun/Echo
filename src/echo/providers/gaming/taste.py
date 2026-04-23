"""
Pure aggregations for ``gaming.taste_profile`` — long-term signals.

Mirrors :mod:`echo.providers.music.taste` both in window shape and
rationale — see that module's docstring for the "why disjoint windows"
argument. The only domain-specific change is ranking by **hours played**
rather than session count: 20 h spread over three sessions is a much
stronger signal than 20 quick hops into a game-of-the-week.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

TOP_K = 20
"""Games each window contributes. Larger = more forgiving classification."""


def _top_games_by_hours(
    sessions: Iterable,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    k: int = TOP_K,
) -> list[tuple[str, float]]:
    hours: dict[str, float] = defaultdict(float)
    for s in sessions:
        ts: datetime = s.when
        if since is not None and ts < since:
            continue
        if until is not None and ts >= until:
            continue
        game = s.game or ""
        if game:
            hours[game] += s.duration_hours
    ranked = sorted(hours.items(), key=lambda kv: kv[1], reverse=True)
    return ranked[:k]


def build(sessions: Iterable, *, now: datetime | None = None) -> dict[str, Any]:
    anchor = now or datetime.now()
    month_cutoff = anchor - timedelta(days=30)

    # Materialise once — we need two passes over the same data.
    everything = list(sessions)

    long_term_top = _top_games_by_hours(everything, until=month_cutoff)
    last_month_top = _top_games_by_hours(everything, since=month_cutoff)

    long_term_set = {g for g, _ in long_term_top}
    last_month_set = {g for g, _ in last_month_top}

    core_games = sorted(long_term_set & last_month_set)
    fling_games = sorted(last_month_set - long_term_set)

    return {
        "top_long_term": [
            {"game": g, "hours": round(h, 2)} for g, h in long_term_top[:10]
        ],
        "top_last_month": [
            {"game": g, "hours": round(h, 2)} for g, h in last_month_top[:10]
        ],
        "core_games": core_games,
        "fling_games": fling_games,
        "notes": (
            "Core = present in both last_month and long_term top-20 by hours. "
            "Flings = in last_month top-20 but absent from long-term. "
            "long_term covers everything older than 30 days. "
            "Ranked by total hours, not session count."
        ),
    }


__all__ = ["build"]
