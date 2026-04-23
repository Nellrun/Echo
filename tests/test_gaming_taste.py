"""Regression tests for ``echo.providers.gaming.taste``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from echo.providers.gaming import taste


@dataclass
class FakeSession:
    when: datetime
    game: str
    duration_hours: float


def sessions_of(game: str, when: datetime, hours: float, n: int) -> list[FakeSession]:
    return [FakeSession(when=when, game=game, duration_hours=hours) for _ in range(n)]


NOW = datetime(2026, 4, 21, 12, 0, 0)
LAST_MONTH = NOW - timedelta(days=5)
OLDER = NOW - timedelta(days=300)


def test_empty_taste() -> None:
    result = taste.build([], now=NOW)
    assert result["core_games"] == []
    assert result["fling_games"] == []
    assert result["top_long_term"] == []
    assert result["top_last_month"] == []


def test_core_game_present_in_both_windows() -> None:
    sessions = []
    sessions += sessions_of("Steady", OLDER, hours=5.0, n=10)
    sessions += sessions_of("Steady", LAST_MONTH, hours=3.0, n=5)
    sessions += sessions_of("Noise", OLDER, hours=0.5, n=3)

    result = taste.build(sessions, now=NOW)
    assert "Steady" in result["core_games"]
    assert "Steady" not in result["fling_games"]


def test_fling_game_only_in_last_month() -> None:
    sessions = []
    sessions += sessions_of("Fling", LAST_MONTH, hours=4.0, n=5)
    for i in range(3):
        sessions += sessions_of(f"Old{i}", OLDER, hours=2.0, n=10)

    result = taste.build(sessions, now=NOW)
    assert "Fling" in result["fling_games"]
    assert "Fling" not in result["core_games"]


def test_long_term_excludes_last_month() -> None:
    sessions = sessions_of("OnlyRecent", LAST_MONTH, hours=10.0, n=5)
    result = taste.build(sessions, now=NOW)
    long_term_titles = [r["game"] for r in result["top_long_term"]]
    assert "OnlyRecent" not in long_term_titles


def test_top_lists_sorted_by_hours_desc() -> None:
    sessions = []
    sessions += sessions_of("A", LAST_MONTH, hours=5.0, n=2)   # 10h
    sessions += sessions_of("B", LAST_MONTH, hours=2.0, n=2)   # 4h
    sessions += sessions_of("C", LAST_MONTH, hours=0.5, n=2)   # 1h
    result = taste.build(sessions, now=NOW)
    top = [r["game"] for r in result["top_last_month"]]
    assert top[:3] == ["A", "B", "C"]


def test_ranking_uses_hours_not_session_count() -> None:
    # Fling appears in more sessions but fewer hours than Core.
    sessions = []
    sessions += sessions_of("Core", LAST_MONTH, hours=8.0, n=1)    # 8h in 1 session
    sessions += sessions_of("Fling", LAST_MONTH, hours=0.1, n=20)  # 2h in 20
    result = taste.build(sessions, now=NOW)
    top = [r["game"] for r in result["top_last_month"]]
    assert top[0] == "Core"


def test_sessions_without_game_dropped() -> None:
    sessions = [
        FakeSession(when=LAST_MONTH, game="", duration_hours=1.0),
        FakeSession(when=LAST_MONTH, game="Real", duration_hours=1.0),
    ]
    result = taste.build(sessions, now=NOW)
    titles = [r["game"] for r in result["top_last_month"]]
    assert titles == ["Real"]


def test_hours_rounded_to_two_decimals() -> None:
    sessions = sessions_of("A", LAST_MONTH, hours=1.2345, n=1)
    result = taste.build(sessions, now=NOW)
    assert result["top_last_month"][0]["hours"] == 1.23
