"""
Pure aggregations for ``music.taste_profile`` — long-term signals.

Two windows:

* ``last_month``   — last 30 days, the "what's on repeat right now" slice
* ``long_term``    — everything *before* the last month, i.e. the user's
  established listening habits

"Core" artists are top-ranked in both windows — steady habits, not just a
recent binge. "Flings" rank high in the last month but aren't present at
all (or barely) in the long-term window — a current phase that hasn't
translated into durable preference yet.

The windows are disjoint on purpose. If we instead compared ``last_month``
against ``last_year`` (which *includes* the last month), every fresh
obsession would still qualify as long-term just by virtue of last month's
scrobbles, and the classification would collapse.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

TOP_K = 20
"""Artists each window contributes. Larger = more forgiving classification."""


def _naive(ts: datetime) -> datetime:
    return ts.replace(tzinfo=None) if ts.tzinfo is not None else ts


def _top_artists(
    scrobbles: Iterable,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    k: int = TOP_K,
) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for s in scrobbles:
        ts = _naive(s.when)
        if since is not None and ts < since:
            continue
        if until is not None and ts >= until:
            continue
        a = getattr(s, "artist", "") or ""
        if a:
            counter[a] += 1
    return counter.most_common(k)


def build(scrobbles: Iterable, *, now: datetime | None = None) -> dict[str, Any]:
    anchor = now or datetime.now()
    month_cutoff = anchor - timedelta(days=30)

    # Materialise once — we need two passes over the same data.
    everything = list(scrobbles)

    long_term_top = _top_artists(everything, until=month_cutoff)
    last_month_top = _top_artists(everything, since=month_cutoff)

    long_term_set = {a for a, _ in long_term_top}
    last_month_set = {a for a, _ in last_month_top}

    core_artists = sorted(long_term_set & last_month_set)
    fling_artists = sorted(last_month_set - long_term_set)

    return {
        "top_long_term": [{"artist": a, "scrobbles": c} for a, c in long_term_top[:10]],
        "top_last_month": [{"artist": a, "scrobbles": c} for a, c in last_month_top[:10]],
        "core_artists": core_artists,
        "fling_artists": fling_artists,
        "notes": (
            "Core = present in both last_month and long_term top-20. "
            "Flings = in last_month top-20 but absent from long-term. "
            "long_term covers everything older than 30 days."
        ),
    }


__all__ = ["build"]
