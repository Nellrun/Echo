"""
Gaming provider — thin adapter over :mod:`my.ps_timetracker`.

Aggregation logic lives in pure-function modules (:mod:`.summary`,
:mod:`.taste`, :mod:`.library_overview`) that accept iterables of sessions
(or a :class:`~my.ps_timetracker.common.Library` snapshot) and are tested
without touching HPI.

Design notes:

* ps-timetracker timestamps are **naive** (account-local timezone), which
  matches how :class:`~echo.core.types.Period` compares moments. No tz
  stripping needed — unlike music, where Last.fm returns UTC-aware values.
* A session without ``start_local`` or ``duration`` can't contribute to
  time-on-a-timeline views, so the provider drops those rows with a debug
  log. They're not errors; ps-timetracker occasionally records a game
  detection with no closing pings.
* "Hours" rather than "session count" is the natural unit everywhere in
  this domain — a 30-minute session and a 10-hour session are wildly
  different experiences. Ranked tops and taste classification all use
  total duration, not play count.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from echo.core.types import Event, Period
from echo.providers.gaming import library_overview as _library
from echo.providers.gaming import summary as _summary
from echo.providers.gaming import taste as _taste

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from my.ps_timetracker.common import Library

log = logging.getLogger(__name__)


def _normalise(s: Any) -> SimpleNamespace | None:
    """
    Adapt a :class:`~my.ps_timetracker.common.Session` to the neutral shape
    used by the aggregation functions.

    Returns ``None`` if the row is missing ``start_local`` or ``duration``
    — those rows can't be placed on a timeline or contribute to hours. The
    caller drops them.
    """
    when = getattr(s, "start_local", None)
    duration: timedelta | None = getattr(s, "duration", None)
    if when is None or duration is None:
        return None
    game = getattr(s, "game_title", None) or ""
    platform = getattr(s, "platform", None) or ""
    duration_seconds = int(duration.total_seconds())
    return SimpleNamespace(
        when=when,
        game=game,
        platform=platform,
        duration_seconds=duration_seconds,
        duration_hours=duration_seconds / 3600,
        game_id=getattr(s, "game_id", None),
        end_local=getattr(s, "end_local", None),
        playtime_id=getattr(s, "playtime_id", None),
    )


def _load_sessions() -> Iterator[SimpleNamespace]:
    """Stream normalised sessions, dropping broken rows and unplaceable ones."""
    from my.ps_timetracker.all import sessions

    for s in sessions():
        if isinstance(s, Exception):
            log.debug("skipping broken ps-timetracker session: %s", s)
            continue
        ns = _normalise(s)
        if ns is None:
            log.debug("skipping session without start/duration: %r", s)
            continue
        yield ns


class GamingProvider:
    name = "gaming"

    def is_available(self) -> bool:
        try:
            from my.ps_timetracker import export

            return bool(export.inputs())
        except Exception:
            log.debug("gaming provider unavailable", exc_info=True)
            return False

    def events(self, period: Period) -> Iterator[Event]:
        for s in _load_sessions():
            if not period.contains(s.when):
                continue
            hours = s.duration_hours
            # Compact, human-scannable title. "h" suffix works for both 0.3h
            # and 12.5h; switching to "Xh Ym" would break at the zero-hour
            # end without helping the common case.
            title = f"{s.game}: {hours:.1f}h" if s.game else f"play session: {hours:.1f}h"
            yield Event(
                timestamp=s.when,
                source=self.name,
                kind="play",
                title=title,
                payload={
                    "game": s.game,
                    "platform": s.platform,
                    "duration_seconds": s.duration_seconds,
                    "duration_hours": round(hours, 3),
                    "end": s.end_local.isoformat() if s.end_local else None,
                    "game_id": s.game_id,
                    "playtime_id": s.playtime_id,
                },
            )

    def play_summary(self, period: Period) -> dict[str, Any]:
        filtered = (s for s in _load_sessions() if period.contains(s.when))
        return _summary.build(filtered, period=period)

    def taste_profile(self, *, now: datetime | None = None) -> dict[str, Any]:
        return _taste.build(list(_load_sessions()), now=now)

    def library_overview(self) -> dict[str, Any]:
        from my.ps_timetracker.all import library

        snap: Library = library()
        return _library.build_overview(snap)

    def register_tools(self, mcp: FastMCP) -> None:
        from echo.tools import gaming_tools

        gaming_tools.register(mcp, self)


__all__ = ["GamingProvider"]
