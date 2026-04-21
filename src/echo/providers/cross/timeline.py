"""
``cross.activity_timeline`` — a single merged feed of events from every
available provider.

The implementation is source-agnostic: it uses :meth:`Registry.iter_events`
so adding a new provider (Trakt, Spotify, GitHub, ...) automatically feeds
into this tool with zero code changes here.

A cross-domain response over a wide period can explode in size, so we
apply a hard cap (``MAX_EVENTS``). High-cardinality providers like Last.fm
are additionally *summarised per day* rather than emitted scrobble-by-
scrobble — scrolling through 300 individual scrobbles is never the useful
shape for an LLM.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any

from echo.core.registry import Registry, default_registry
from echo.core.types import Event, Period

MAX_EVENTS = 500
"""Hard ceiling on the total number of timeline entries returned."""

# Providers whose events we collapse to a daily summary line in the timeline.
# A scrobble-level view is always available via ``query.scrobbles``.
DENSE_SOURCES: frozenset[str] = frozenset({"music"})


def _summarise_music_day(day_events: list[Event]) -> Event:
    """Collapse a day's scrobbles into a single "N tracks, top artist: X" entry."""
    total = len(day_events)
    artists = Counter(
        e.payload.get("artist", "")
        for e in day_events
        if e.payload.get("artist")
    )
    top_artist, top_count = (artists.most_common(1) or [("", 0)])[0]

    # All events share a date; timestamp at midnight keeps sort stable.
    anchor = day_events[0].timestamp
    midnight = anchor.replace(hour=0, minute=0, second=0, microsecond=0)
    title = (
        f"{total} scrobbles — top: {top_artist} ({top_count})"
        if top_artist
        else f"{total} scrobbles"
    )
    return Event(
        timestamp=midnight,
        source="music",
        kind="daily_summary",
        title=title,
        payload={
            "scrobbles": total,
            "top_artist": top_artist,
            "top_artist_scrobbles": top_count,
            "unique_artists": len(artists),
        },
    )


def _collapse_dense(events: Iterable[Event]) -> Iterable[Event]:
    """Collapse dense-source events by (source, date); pass others through."""
    buckets: dict[tuple[str, Any], list[Event]] = defaultdict(list)
    passthrough: list[Event] = []
    for e in events:
        if e.source in DENSE_SOURCES:
            buckets[(e.source, e.timestamp.date())].append(e)
        else:
            passthrough.append(e)

    for (source, _), day_events in buckets.items():
        if source == "music":
            yield _summarise_music_day(day_events)
        else:
            # Shouldn't hit — DENSE_SOURCES currently only has "music" — but
            # keep the branch honest for future additions.
            yield from day_events
    yield from passthrough


def build(
    period: Period,
    *,
    registry: Registry | None = None,
    sources: Iterable[str] | None = None,
    max_events: int = MAX_EVENTS,
) -> dict[str, Any]:
    reg = registry or default_registry()
    raw = list(reg.iter_events(period, sources=sources))
    collapsed = sorted(_collapse_dense(raw), key=lambda e: e.timestamp)

    truncated = len(collapsed) > max_events
    kept = collapsed[:max_events] if truncated else collapsed

    return {
        "period": period.label or "custom",
        "total_events": len(kept),
        "truncated": truncated,
        "sources_seen": sorted({e.source for e in collapsed}),
        "events": [
            {
                "timestamp": e.timestamp.isoformat(),
                "source": e.source,
                "kind": e.kind,
                "title": e.title,
                "payload": e.payload,
            }
            for e in kept
        ],
    }


__all__ = ["build"]
