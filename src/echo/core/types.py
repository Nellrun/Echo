"""Core dataclasses shared across providers and the cross-domain layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Period:
    """
    A half-open time window ``[start, end)``.

    ``start`` is inclusive, ``end`` is exclusive — that makes concatenation
    of consecutive periods natural (``[Jan, Feb) + [Feb, Mar) = [Jan, Mar)``)
    and avoids the usual off-by-one traps at month/year boundaries.

    The special "all time" period is represented with ``start=None`` and
    ``end=None``; :meth:`contains` is always true for it.
    """

    start: datetime | None
    end: datetime | None
    label: str = ""
    """Short human-readable tag echoed back in summaries (e.g. ``"2026-Q1"``)."""

    def contains(self, moment: datetime | date) -> bool:
        if isinstance(moment, date) and not isinstance(moment, datetime):
            moment = datetime.combine(moment, datetime.min.time())
        if self.start is not None and moment < self.start:
            return False
        return not (self.end is not None and moment >= self.end)

    @property
    def is_all_time(self) -> bool:
        return self.start is None and self.end is None


@dataclass(frozen=True, slots=True)
class Event:
    """
    A single point-in-time activity from any provider.

    ``payload`` is free-form; the cross-domain consumers treat events
    opaquely except for the header fields. Providers should keep payloads
    small (identity + a few top-level attributes) — the goal is a scannable
    timeline, not a raw dump.
    """

    timestamp: datetime
    source: str
    """Provider name, e.g. ``"films"``, ``"music"``."""
    kind: str
    """Event subtype within the source, e.g. ``"diary"``, ``"scrobble"``."""
    title: str
    """One-line human-readable label."""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Summary:
    """Envelope returned by ``*.summary`` tools. Providers fill ``data`` freely."""

    period: str
    source: str
    data: dict[str, Any]


__all__ = ["Event", "Period", "Summary"]
