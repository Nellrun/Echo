"""
Small, generic aggregation helpers reused by providers.

Everything here is deliberately boring: ``top_n``, bucketing by day, rating
distribution. The interesting semantics live inside each provider (what
to count, which date field to use, how to normalise rating scales).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import date, datetime
from typing import TypeVar

T = TypeVar("T")


def top_n(items: Iterable[T], n: int, *, key: str = "count") -> list[dict]:
    """
    Count ``items`` and return the ``n`` most common as a list of dicts.

    The shape ``[{"value": ..., "<key>": ...}, ...]`` is LLM-friendly:
    predictable keys, no tuples, safe to serialise with JSON.
    """
    counter = Counter(items)
    return [{"value": v, key: c} for v, c in counter.most_common(n)]


def daily_distribution(moments: Iterable[datetime | date]) -> dict[str, int]:
    """
    Map each day (``YYYY-MM-DD``) to the number of events on it.

    Days with zero events are omitted — callers can fill them in if they
    need a fully dense range (we don't know the window here).
    """
    counter: Counter[str] = Counter()
    for m in moments:
        d = m.date() if isinstance(m, datetime) else m
        counter[d.isoformat()] += 1
    return dict(sorted(counter.items()))


def rating_distribution(
    ratings: Iterable[float | None], *, step: float = 0.5
) -> dict[str, int]:
    """
    Bucket ratings by ``step``. ``None`` values are counted under ``"unrated"``.

    The rating is formatted with one decimal so ``3.0`` stays ``"3.0"``,
    which keeps keys stable regardless of how the source stored integers.
    """
    buckets: dict[str, int] = defaultdict(int)
    for r in ratings:
        if r is None:
            buckets["unrated"] += 1
            continue
        # Snap to the nearest multiple of ``step`` — guards against noisy
        # floats that would otherwise scatter into unique bucket keys.
        snapped = round(r / step) * step
        buckets[f"{snapped:.1f}"] += 1
    return dict(sorted(buckets.items()))


def average(values: Iterable[float]) -> float | None:
    """Arithmetic mean; returns ``None`` for an empty iterable."""
    total = 0.0
    count = 0
    for v in values:
        total += v
        count += 1
    return total / count if count else None


__all__ = ["average", "daily_distribution", "rating_distribution", "top_n"]
