"""Regression tests for ``echo.providers.gaming.summary``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from echo.core.periods import parse_period
from echo.providers.gaming import summary


@dataclass
class FakeSession:
    when: datetime
    game: str
    platform: str
    duration_seconds: int
    duration_hours: float


def s(
    when: datetime, game: str, platform: str = "PS5", hours: float = 1.0
) -> FakeSession:
    return FakeSession(
        when=when,
        game=game,
        platform=platform,
        duration_seconds=int(hours * 3600),
        duration_hours=hours,
    )


def test_empty_summary() -> None:
    result = summary.build([], period=parse_period("all"))
    assert result["total_sessions"] == 0
    assert result["total_hours"] == 0.0
    assert result["unique_games"] == 0
    assert result["top_games"] == []
    assert result["hours_by_platform"] == {}
    assert result["daily_distribution"] == {}


def test_counts_and_totals() -> None:
    sessions = [
        s(datetime(2026, 2, 1, 20), "Elden Ring", hours=2.0),
        s(datetime(2026, 2, 2, 20), "Elden Ring", hours=1.5),
        s(datetime(2026, 2, 3, 10), "Hades", hours=0.5),
    ]
    result = summary.build(sessions, period=parse_period("2026-02"))
    assert result["total_sessions"] == 3
    assert result["total_hours"] == 4.0
    assert result["unique_games"] == 2


def test_top_games_sorted_by_hours_desc() -> None:
    # "Hades" would win by session count (3 vs 1), but Elden Ring should
    # still come first because it has more hours.
    sessions = [
        s(datetime(2026, 2, 1), "Elden Ring", hours=10.0),
        s(datetime(2026, 2, 1), "Hades", hours=0.2),
        s(datetime(2026, 2, 1), "Hades", hours=0.2),
        s(datetime(2026, 2, 1), "Hades", hours=0.2),
    ]
    result = summary.build(sessions, period=parse_period("2026-02"))
    assert [r["value"] for r in result["top_games"]] == ["Elden Ring", "Hades"]
    assert result["top_games"][0]["hours"] == 10.0
    assert result["top_games"][0]["sessions"] == 1
    assert result["top_games"][1]["sessions"] == 3


def test_top_games_capped_at_ten() -> None:
    sessions = [
        s(datetime(2026, 2, 1), f"Game{i}", hours=float(20 - i)) for i in range(15)
    ]
    result = summary.build(sessions, period=parse_period("2026-02"))
    assert len(result["top_games"]) == 10


def test_hours_by_platform_sorted_desc() -> None:
    sessions = [
        s(datetime(2026, 2, 1), "A", platform="PS5", hours=3.0),
        s(datetime(2026, 2, 1), "B", platform="PS4", hours=1.0),
    ]
    result = summary.build(sessions, period=parse_period("2026-02"))
    assert list(result["hours_by_platform"].keys()) == ["PS5", "PS4"]
    assert result["hours_by_platform"]["PS5"] == 3.0


def test_daily_distribution_uses_session_start() -> None:
    sessions = [
        s(datetime(2026, 2, 1, 23), "A", hours=0.5),
        s(datetime(2026, 2, 1, 23, 30), "A", hours=0.5),
        s(datetime(2026, 2, 2, 0, 5), "A", hours=0.5),
    ]
    result = summary.build(sessions, period=parse_period("2026-02"))
    assert result["daily_distribution"] == {"2026-02-01": 2, "2026-02-02": 1}


def test_missing_game_title_bucketed_as_unknown() -> None:
    sessions = [
        FakeSession(
            when=datetime(2026, 2, 1),
            game="",
            platform="PS5",
            duration_seconds=3600,
            duration_hours=1.0,
        ),
    ]
    result = summary.build(sessions, period=parse_period("2026-02"))
    assert result["top_games"][0]["value"] == "(unknown)"


def test_period_label_propagates() -> None:
    result = summary.build([], period=parse_period("2026-02"))
    assert result["period"] == "2026-02"
