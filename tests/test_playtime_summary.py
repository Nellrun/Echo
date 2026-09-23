"""Regression tests for the playtime pure-aggregation modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from echo.core.periods import parse_period
from echo.core.types import Period
from echo.providers.playtime import summary, taste, trophies

# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------


@dataclass
class FakeSession:
    when: datetime
    game: str
    platform: str
    source: str
    duration_seconds: int
    duration_hours: float


def s(
    when: datetime,
    game: str,
    *,
    platform: str = "PS5",
    source: str = "psn",
    hours: float = 1.0,
) -> FakeSession:
    return FakeSession(
        when=when,
        game=game,
        platform=platform,
        source=source,
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
    assert result["hours_by_source"] == {}


def test_summary_splits_by_source_and_platform() -> None:
    sessions = [
        s(datetime(2026, 6, 1, 20), "NieR", platform="PS5", source="psn", hours=3.0),
        s(datetime(2026, 6, 2, 20), "PoE2", platform="Steam", source="steam", hours=2.0),
        s(datetime(2026, 6, 3, 10), "Hyrule", platform="Nintendo", source="nintendo", hours=1.0),
    ]
    result = summary.build(sessions, period=parse_period("2026-06"))
    assert result["total_hours"] == 6.0
    assert result["unique_games"] == 3
    assert result["hours_by_source"] == {"psn": 3.0, "steam": 2.0, "nintendo": 1.0}
    assert result["hours_by_platform"] == {"PS5": 3.0, "Steam": 2.0, "Nintendo": 1.0}
    # source is carried on each top_games row
    nier = next(g for g in result["top_games"] if g["value"] == "NieR")
    assert nier["source"] == "psn"
    assert nier["hours"] == 3.0


def test_summary_top_games_ranked_by_hours() -> None:
    sessions = [
        s(datetime(2026, 6, 1), "Big", hours=10.0),
        s(datetime(2026, 6, 1), "Small", hours=0.2),
        s(datetime(2026, 6, 1), "Small", hours=0.2),
        s(datetime(2026, 6, 1), "Small", hours=0.2),
    ]
    result = summary.build(sessions, period=parse_period("2026-06"))
    assert [g["value"] for g in result["top_games"]] == ["Big", "Small"]
    assert result["top_games"][0]["sessions"] == 1
    assert result["top_games"][1]["sessions"] == 3


def test_summary_unknown_buckets() -> None:
    sessions = [
        FakeSession(
            when=datetime(2026, 6, 1),
            game="",
            platform="",
            source="",
            duration_seconds=3600,
            duration_hours=1.0,
        )
    ]
    result = summary.build(sessions, period=parse_period("2026-06"))
    assert result["top_games"][0]["value"] == "(unknown)"
    assert "(unknown)" in result["hours_by_platform"]
    assert "(unknown)" in result["hours_by_source"]


# ---------------------------------------------------------------------------
# taste
# ---------------------------------------------------------------------------


def test_taste_core_and_fling_split() -> None:
    now = datetime(2026, 6, 21)
    sessions = [
        # Core: present long-term and last month.
        s(datetime(2026, 4, 1), "Core", hours=20.0),
        s(datetime(2026, 6, 20), "Core", hours=5.0),
        # Fling: only last month.
        s(datetime(2026, 6, 19), "Fling", hours=8.0),
        # Old-only: long-term but not recent.
        s(datetime(2026, 3, 1), "OldOnly", hours=15.0),
    ]
    result = taste.build(sessions, now=now)
    assert "Core" in result["core_games"]
    assert "Fling" in result["fling_games"]
    assert "OldOnly" not in result["core_games"]
    assert "OldOnly" not in result["fling_games"]


# ---------------------------------------------------------------------------
# trophies
# ---------------------------------------------------------------------------


@dataclass
class FakeTrophy:
    when: datetime | None
    game: str
    name: str
    type: str | None
    rarity: float | None
    source: str


def t(
    when: datetime | None,
    game: str,
    name: str,
    *,
    ttype: str = "bronze",
    rarity: float | None = 50.0,
    source: str = "psn",
) -> FakeTrophy:
    return FakeTrophy(when=when, game=game, name=name, type=ttype, rarity=rarity, source=source)


def test_trophies_empty() -> None:
    result = trophies.build([], period=parse_period("all"))
    assert result["total_trophies"] == 0
    assert result["by_type"] == {}
    assert result["rarest"] == []
    assert result["recent"] == []


def test_trophies_counts_and_ordering() -> None:
    rows = [
        t(datetime(2026, 6, 21, 20), "NieR", "Platinum", ttype="platinum", rarity=2.0),
        t(datetime(2026, 6, 20), "NieR", "Boss", ttype="bronze", rarity=17.3),
        t(datetime(2026, 6, 19), "FF16", "Clive", ttype="gold", rarity=40.0, source="psn"),
    ]
    result = trophies.build(rows, period=parse_period("all"))
    assert result["total_trophies"] == 3
    # by_type ordered platinum > gold > silver > bronze
    assert list(result["by_type"].keys()) == ["platinum", "gold", "bronze"]
    # rarest first = lowest rarity
    assert result["rarest"][0]["trophy"] == "Platinum"
    assert result["rarest"][0]["rarity"] == 2.0
    # recent first = latest earned
    assert result["recent"][0]["trophy"] == "Platinum"
    # top games by count: NieR has 2
    assert result["top_games"][0] == {"game": "NieR", "count": 2}


def test_trophies_without_timestamp_excluded_from_recent() -> None:
    rows = [
        t(None, "Mystery", "NoDate", rarity=None),
        t(datetime(2026, 6, 21), "NieR", "Dated", rarity=10.0),
    ]
    result = trophies.build(rows, period=Period(None, None, "all"))
    assert result["total_trophies"] == 2
    # The undated trophy is counted but not in recent/rarest.
    assert [r["trophy"] for r in result["recent"]] == ["Dated"]
    assert [r["trophy"] for r in result["rarest"]] == ["Dated"]
