"""
Pure aggregation for ``playtime.trophy_summary``.

Trophies are the distinctive payload of the gwm-stats aggregator (the
older ps-timetracker source has none). This module turns a pre-filtered
iterable of normalised trophy rows into a compact, LLM-scannable digest:
counts by type and source, the games contributing the most, the rarest
earned, and the most recent.

A "trophy" here is any object exposing ``when`` (naive datetime or
``None``), ``game``, ``name``, ``type``, ``rarity`` and ``source`` — the
shape produced by :func:`echo.providers.playtime._normalise_trophy`.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from echo.core.types import Period

# PSN ranks trophies platinum > gold > silver > bronze. Fixed order keeps the
# ``by_type`` mapping stable regardless of which types happen to be present.
_TYPE_ORDER = {"platinum": 0, "gold": 1, "silver": 2, "bronze": 3}


def _row(t: Any) -> dict[str, Any]:
    return {
        "game": t.game or None,
        "trophy": t.name or None,
        "type": t.type,
        "rarity": t.rarity,
        "source": t.source,
        "earned_at": t.when.isoformat() if t.when is not None else None,
    }


def build(trophies: Iterable, *, period: Period) -> dict[str, Any]:
    total = 0
    by_type: Counter[str] = Counter()
    by_source: Counter[str] = Counter()
    by_game: dict[str, int] = defaultdict(int)
    rows: list[Any] = []

    for t in trophies:
        total += 1
        if t.type:
            by_type[t.type] += 1
        if t.source:
            by_source[t.source] += 1
        if t.game:
            by_game[t.game] += 1
        rows.append(t)

    by_type_sorted = {
        ttype: by_type[ttype]
        for ttype in sorted(by_type, key=lambda k: _TYPE_ORDER.get(k, 99))
    }

    top_games = [
        {"game": g, "count": c}
        for g, c in sorted(by_game.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    ]

    # Rarest = lowest rarity percentage. Rows without a rarity sort last.
    rarest = sorted(
        (t for t in rows if t.rarity is not None),
        key=lambda t: t.rarity,
    )[:5]

    # Most recent = latest earned_at. Rows without a timestamp sort last.
    recent = sorted(
        (t for t in rows if t.when is not None),
        key=lambda t: t.when,
        reverse=True,
    )[:10]

    return {
        "period": period.label or "custom",
        "total_trophies": total,
        "by_type": by_type_sorted,
        "by_source": dict(by_source.most_common()),
        "top_games": top_games,
        "rarest": [_row(t) for t in rarest],
        "recent": [_row(t) for t in recent],
    }


__all__ = ["build"]
