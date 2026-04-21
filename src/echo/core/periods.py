"""
Parser for human-readable period strings used by every insight tool.

Accepted shapes (case-insensitive):

* ``"all"`` — unbounded period.
* ``"last_week"``, ``"last_month"``, ``"last_year"`` — rolling windows anchored at *now*.
* ``"YYYY"`` — a calendar year.
* ``"YYYY-MM"`` — a calendar month.
* ``"YYYY-Qn"`` — a calendar quarter (``n`` in 1..4).
* ``"YYYY-MM-DD..YYYY-MM-DD"`` — an explicit inclusive day range.

The parser returns a :class:`Period` with a half-open ``[start, end)`` window.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Final

from .types import Period

_QUARTER_RE: Final = re.compile(r"^(\d{4})-Q([1-4])$", re.IGNORECASE)
_YEAR_RE: Final = re.compile(r"^(\d{4})$")
_MONTH_RE: Final = re.compile(r"^(\d{4})-(\d{2})$")
_RANGE_RE: Final = re.compile(r"^(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})$")


class PeriodParseError(ValueError):
    """The period string did not match any of the accepted shapes."""


def parse_period(spec: str, *, now: datetime | None = None) -> Period:
    """
    Parse ``spec`` into a :class:`Period`.

    ``now`` is injectable for tests; defaults to ``datetime.now()``.
    """
    raw = spec.strip()
    if not raw:
        raise PeriodParseError("empty period")

    token = raw.lower()

    if token == "all":
        return Period(start=None, end=None, label="all")

    if token in _ROLLING:
        anchor = now or datetime.now()
        delta = _ROLLING[token]
        return Period(start=anchor - delta, end=anchor, label=token)

    if m := _QUARTER_RE.match(raw):
        year = int(m.group(1))
        quarter = int(m.group(2))
        start_month = (quarter - 1) * 3 + 1
        start = datetime(year, start_month, 1)
        end = _add_months(start, 3)
        return Period(start=start, end=end, label=f"{year}-Q{quarter}")

    if m := _MONTH_RE.match(raw):
        year, month = int(m.group(1)), int(m.group(2))
        if not 1 <= month <= 12:
            raise PeriodParseError(f"invalid month in {raw!r}")
        start = datetime(year, month, 1)
        end = _add_months(start, 1)
        return Period(start=start, end=end, label=raw)

    if m := _YEAR_RE.match(raw):
        year = int(m.group(1))
        return Period(
            start=datetime(year, 1, 1),
            end=datetime(year + 1, 1, 1),
            label=raw,
        )

    if m := _RANGE_RE.match(raw):
        try:
            start_d = date.fromisoformat(m.group(1))
            end_d = date.fromisoformat(m.group(2))
        except ValueError as e:
            raise PeriodParseError(f"invalid date in range {raw!r}: {e}") from e
        if end_d < start_d:
            raise PeriodParseError(f"range end before start: {raw!r}")
        start = datetime.combine(start_d, datetime.min.time())
        # The explicit range is inclusive on both ends; the internal window is half-open.
        end = datetime.combine(end_d + timedelta(days=1), datetime.min.time())
        return Period(start=start, end=end, label=raw)

    raise PeriodParseError(f"unrecognised period: {spec!r}")


_ROLLING: Final[dict[str, timedelta]] = {
    "last_week": timedelta(days=7),
    "last_month": timedelta(days=30),
    "last_year": timedelta(days=365),
}


def _add_months(anchor: datetime, months: int) -> datetime:
    total = anchor.month - 1 + months
    year = anchor.year + total // 12
    month = total % 12 + 1
    return anchor.replace(year=year, month=month)


__all__ = ["PeriodParseError", "parse_period"]
