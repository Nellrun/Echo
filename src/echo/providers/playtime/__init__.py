"""
Playtime provider — thin adapter over :mod:`my.gwm_stats`.

``gwm-stats`` is a cross-platform play aggregator: it pulls sessions and
trophies from PSN, Steam and Nintendo into a single feed. This provider is
deliberately kept **separate** from :mod:`echo.providers.gaming` (which
wraps the PSN-only, friend-presence ps-timetracker source) — the two
answer overlapping but distinct questions, and merging them would risk
double-counting PSN hours. ``gaming`` stays as-is; ``playtime`` adds the
cross-platform picture plus trophies.

Aggregation logic lives in pure-function modules (:mod:`.summary`,
:mod:`.taste`, :mod:`.trophies`, :mod:`.overview`) that accept neutral
iterables and are tested without touching HPI.

Design notes:

* gwm-stats timestamps are **UTC-aware** (unlike ps-timetracker's naive
  local times). We strip tz to naive via :func:`_naive` before comparing
  against :class:`~echo.core.types.Period`, exactly as the music provider
  does for Last.fm — mixed aware/naive comparisons raise ``TypeError``.
* "Hours" rather than "session count" is the natural unit everywhere here:
  ranked tops and taste classification use total duration.
* Sessions without a duration can't contribute to time-on-a-timeline
  views, so they're dropped with a debug log (not an error).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from echo.core.types import Event, Period
from echo.providers.playtime import overview as _overview
from echo.providers.playtime import summary as _summary
from echo.providers.playtime import taste as _taste
from echo.providers.playtime import trophies as _trophies

if TYPE_CHECKING:
    from fastmcp import FastMCP

log = logging.getLogger(__name__)


def _naive(ts: datetime | None) -> datetime | None:
    """Drop tzinfo so timestamps compare cleanly against a naive Period."""
    if ts is None:
        return None
    return ts.replace(tzinfo=None) if ts.tzinfo is not None else ts


def _normalise_session(s: Any) -> SimpleNamespace | None:
    """
    Adapt a :class:`~my.gwm_stats.common.Session` to the neutral shape used
    by the aggregation functions. Returns ``None`` when the session has no
    duration (can't contribute hours) — the caller drops it.
    """
    when = _naive(getattr(s, "started_at", None))
    duration: timedelta | None = getattr(s, "duration", None)
    if when is None or duration is None:
        return None
    duration_seconds = int(duration.total_seconds())
    return SimpleNamespace(
        when=when,
        game=getattr(s, "title_name", None) or "",
        platform=getattr(s, "platform", None) or "",
        source=getattr(s, "source", None) or "",
        duration_seconds=duration_seconds,
        duration_hours=duration_seconds / 3600,
        title_id=getattr(s, "title_id", None),
        end=_naive(getattr(s, "ended_at", None)),
    )


def _normalise_trophy(t: Any) -> SimpleNamespace:
    """Adapt a :class:`~my.gwm_stats.common.Trophy` to the neutral shape."""
    return SimpleNamespace(
        when=_naive(getattr(t, "earned_at", None)),
        game=getattr(t, "title_name", None) or "",
        name=getattr(t, "trophy_name", None) or "",
        type=getattr(t, "trophy_type", None),
        rarity=getattr(t, "rarity", None),
        source=getattr(t, "source", None) or "",
        np_comm_id=getattr(t, "np_comm_id", None),
        trophy_id=getattr(t, "trophy_id", None),
    )


def _load_sessions() -> Iterator[SimpleNamespace]:
    """Stream normalised sessions, dropping broken and undurated rows."""
    from my.gwm_stats.all import sessions

    for s in sessions():
        if isinstance(s, Exception):
            log.debug("skipping broken gwm-stats session: %s", s)
            continue
        ns = _normalise_session(s)
        if ns is None:
            log.debug("skipping session without start/duration: %r", s)
            continue
        yield ns


def _load_trophies() -> Iterator[SimpleNamespace]:
    """Stream normalised trophies, dropping broken rows."""
    from my.gwm_stats.all import trophies

    for t in trophies():
        if isinstance(t, Exception):
            log.debug("skipping broken gwm-stats trophy: %s", t)
            continue
        yield _normalise_trophy(t)


class PlaytimeProvider:
    name = "playtime"

    def is_available(self) -> bool:
        try:
            from my.gwm_stats import export

            return bool(export.inputs())
        except Exception:
            log.debug("playtime provider unavailable", exc_info=True)
            return False

    def events(self, period: Period) -> Iterator[Event]:
        # Play sessions.
        for s in _load_sessions():
            if not period.contains(s.when):
                continue
            hours = s.duration_hours
            title = (
                f"{s.game}: {hours:.1f}h" if s.game else f"play session: {hours:.1f}h"
            )
            yield Event(
                timestamp=s.when,
                source=self.name,
                kind="play",
                title=title,
                payload={
                    "game": s.game,
                    "platform": s.platform,
                    "source": s.source,
                    "duration_seconds": s.duration_seconds,
                    "duration_hours": round(hours, 3),
                    "end": s.end.isoformat() if s.end else None,
                    "title_id": s.title_id,
                },
            )
        # Trophies — only those with a known earned-at can sit on a timeline.
        for t in _load_trophies():
            if t.when is None or not period.contains(t.when):
                continue
            label = f"{t.name} — {t.game}" if t.game else (t.name or "trophy")
            yield Event(
                timestamp=t.when,
                source=self.name,
                kind="trophy",
                title=f"🏆 {label}",
                payload={
                    "game": t.game,
                    "trophy": t.name,
                    "type": t.type,
                    "rarity": t.rarity,
                    "source": t.source,
                },
            )

    def play_summary(self, period: Period) -> dict[str, Any]:
        filtered = (s for s in _load_sessions() if period.contains(s.when))
        return _summary.build(filtered, period=period)

    def taste_profile(self, *, now: datetime | None = None) -> dict[str, Any]:
        return _taste.build(list(_load_sessions()), now=now)

    def trophy_summary(self, period: Period) -> dict[str, Any]:
        # Trophies with no earned-at can't be placed in a bounded window;
        # keep them only for the all-time view.
        def _keep(t: SimpleNamespace) -> bool:
            if period.is_all_time:
                return True
            return t.when is not None and period.contains(t.when)

        filtered = (t for t in _load_trophies() if _keep(t))
        return _trophies.build(filtered, period=period)

    def overview(self) -> dict[str, Any]:
        from my.gwm_stats.all import summary

        snap = summary()
        # Count trophies for the headline number; cheap relative to the scan
        # the LLM would otherwise do via trophy_summary.
        trophy_count = sum(1 for _ in _load_trophies())
        return _overview.build_overview(snap, trophy_count=trophy_count)

    def register_tools(self, mcp: FastMCP) -> None:
        from echo.tools import playtime_tools

        playtime_tools.register(mcp, self)


__all__ = ["PlaytimeProvider"]
