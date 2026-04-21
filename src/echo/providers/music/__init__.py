"""
Music provider — thin adapter over :mod:`my.lastfm`.

As with the films provider, aggregation logic lives in pure-function modules
(:mod:`.summary`, :mod:`.taste`) that accept iterables of scrobbles and are
tested without touching HPI.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from echo.core.types import Event, Period
from echo.providers.music import summary as _summary
from echo.providers.music import taste as _taste

if TYPE_CHECKING:
    from fastmcp import FastMCP

log = logging.getLogger(__name__)


def _naive(ts: datetime) -> datetime:
    """
    Drop timezone info for period comparisons.

    ``my.lastfm`` yields tz-aware timestamps; our Period uses naive
    datetimes. Stripping tz keeps comparisons simple and, crucially,
    keeps ``contains`` from raising ``TypeError`` on mixed tz/naive
    comparison.
    """
    return ts.replace(tzinfo=None) if ts.tzinfo is not None else ts


def _normalise(s: Any) -> SimpleNamespace:
    """
    Adapt a karlicoss HPI ``Scrobble`` (``dt`` / ``artist`` / ``name`` /
    ``album``) to the neutral shape used by downstream aggregation code
    (``when`` / ``artist`` / ``track`` / ``album``).

    Accepting both field names keeps the adapter forward- and
    backward-compatible across HPI releases that have renamed the
    attributes over time.
    """
    when = getattr(s, "dt", None)
    if when is None:
        when = getattr(s, "when", None)
    track = getattr(s, "name", None)
    if track is None:
        track = getattr(s, "track", None)
    return SimpleNamespace(
        when=when,
        artist=getattr(s, "artist", "") or "",
        track=track or "",
        album=getattr(s, "album", None),
    )


def _load_scrobbles() -> Iterator[SimpleNamespace]:
    from my.lastfm import scrobbles

    for s in scrobbles():
        if isinstance(s, Exception):
            log.debug("skipping broken scrobble: %s", s)
            continue
        yield _normalise(s)


class MusicProvider:
    name = "music"

    def is_available(self) -> bool:
        try:
            from my.lastfm import scrobbles

            # Pull a single item to surface config errors without materialising
            # the whole dataset.
            next(iter(scrobbles()), None)
            return True
        except Exception:
            log.debug("music provider unavailable", exc_info=True)
            return False

    def events(self, period: Period) -> Iterator[Event]:
        for s in _load_scrobbles():
            ts = _naive(s.when)
            if not period.contains(ts):
                continue
            artist = getattr(s, "artist", "") or ""
            track = getattr(s, "track", "") or ""
            yield Event(
                timestamp=ts,
                source=self.name,
                kind="scrobble",
                title=f"{artist} — {track}" if artist and track else track or artist,
                payload={
                    "artist": artist,
                    "track": track,
                    "album": getattr(s, "album", None),
                },
            )

    def listening_summary(self, period: Period) -> dict[str, Any]:
        filtered = (s for s in _load_scrobbles() if period.contains(_naive(s.when)))
        return _summary.build(filtered, period=period)

    def taste_profile(self, *, now: datetime | None = None) -> dict[str, Any]:
        return _taste.build(list(_load_scrobbles()), now=now)

    def register_tools(self, mcp: FastMCP) -> None:
        from echo.tools import music_tools

        music_tools.register(mcp, self)


__all__ = ["MusicProvider"]
