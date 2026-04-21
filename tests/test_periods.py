from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from echo.core.periods import PeriodParseError, parse_period


def test_all_is_unbounded() -> None:
    p = parse_period("all")
    assert p.is_all_time
    assert p.start is None
    assert p.end is None
    assert p.label == "all"


def test_all_is_case_insensitive() -> None:
    assert parse_period("ALL").is_all_time


def test_year() -> None:
    p = parse_period("2025")
    assert p.start == datetime(2025, 1, 1)
    assert p.end == datetime(2026, 1, 1)
    assert p.label == "2025"


def test_month() -> None:
    p = parse_period("2026-02")
    assert p.start == datetime(2026, 2, 1)
    assert p.end == datetime(2026, 3, 1)


def test_month_december_rolls_to_next_year() -> None:
    p = parse_period("2026-12")
    assert p.start == datetime(2026, 12, 1)
    assert p.end == datetime(2027, 1, 1)


def test_month_rejects_invalid_month() -> None:
    with pytest.raises(PeriodParseError):
        parse_period("2026-13")


def test_quarter_q1() -> None:
    p = parse_period("2026-Q1")
    assert p.start == datetime(2026, 1, 1)
    assert p.end == datetime(2026, 4, 1)
    assert p.label == "2026-Q1"


def test_quarter_q4() -> None:
    p = parse_period("2026-Q4")
    assert p.start == datetime(2026, 10, 1)
    assert p.end == datetime(2027, 1, 1)


def test_quarter_case_insensitive() -> None:
    assert parse_period("2026-q2") == parse_period("2026-Q2")


def test_explicit_range_is_inclusive() -> None:
    p = parse_period("2026-01-10..2026-01-12")
    assert p.start == datetime(2026, 1, 10)
    # Internal window is half-open; Jan 12 23:59 should still be contained.
    assert p.end == datetime(2026, 1, 13)
    assert p.contains(datetime(2026, 1, 12, 23, 59))
    assert not p.contains(datetime(2026, 1, 13, 0, 0))


def test_explicit_range_rejects_reversed() -> None:
    with pytest.raises(PeriodParseError):
        parse_period("2026-03-01..2026-02-01")


def test_rolling_last_week_uses_injected_now() -> None:
    now = datetime(2026, 4, 21, 10, 0, 0)
    p = parse_period("last_week", now=now)
    assert p.end == now
    assert p.start == now - timedelta(days=7)
    assert p.label == "last_week"


def test_rolling_last_year_uses_injected_now() -> None:
    now = datetime(2026, 4, 21)
    p = parse_period("last_year", now=now)
    assert p.start == now - timedelta(days=365)


def test_unknown_raises() -> None:
    with pytest.raises(PeriodParseError):
        parse_period("yesterday")


def test_empty_raises() -> None:
    with pytest.raises(PeriodParseError):
        parse_period("   ")


def test_contains_respects_half_open_end() -> None:
    p = parse_period("2026-02")
    assert p.contains(datetime(2026, 2, 1))
    assert p.contains(datetime(2026, 2, 28, 23, 59))
    assert not p.contains(datetime(2026, 3, 1))


def test_contains_accepts_date() -> None:
    from datetime import date

    p = parse_period("2026-02")
    assert p.contains(date(2026, 2, 15))
    assert not p.contains(date(2026, 3, 1))


def test_contains_all_is_always_true() -> None:
    p = parse_period("all")
    assert p.contains(datetime(1900, 1, 1))
    assert p.contains(datetime(2999, 12, 31))
