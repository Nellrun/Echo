"""Regression tests for ``echo.providers.gaming.library_overview``."""

from __future__ import annotations

from datetime import datetime, timedelta

from my.ps_timetracker.common import Library, LibraryGame

from echo.providers.gaming import library_overview


def g(
    title: str,
    *,
    platform: str | None = "PS5",
    hours: float | None = 1.0,
    sessions: int | None = 1,
    last_played: datetime | None = None,
    game_id: str | None = "id",
    rank: int | None = None,
) -> LibraryGame:
    return LibraryGame(
        rank=rank,
        game_id=game_id,
        title=title,
        platform=platform,
        total_duration=timedelta(hours=hours) if hours is not None else None,
        total_duration_text=None,
        sessions_count=sessions,
        avg_session=None,
        avg_session_text=None,
        last_played_local=last_played,
    )


def snap(*games: LibraryGame, profile: str = "me") -> Library:
    return Library(
        fetched_at_utc=datetime(2026, 4, 20, 12, 0, 0),
        profile=profile,
        games=tuple(games),
    )


def test_empty_library() -> None:
    result = library_overview.build_overview(snap())
    assert result["total_games"] == 0
    assert result["total_hours"] == 0.0
    assert result["by_platform"] == {}
    assert result["top_by_hours"] == []
    assert result["recently_played"] == []
    assert result["profile"] == "me"
    assert result["fetched_at_utc"] == "2026-04-20T12:00:00"


def test_totals_and_platform_mix() -> None:
    library = snap(
        g("A", platform="PS5", hours=10.0),
        g("B", platform="PS5", hours=2.0),
        g("C", platform="PS4", hours=1.0),
    )
    result = library_overview.build_overview(library)
    assert result["total_games"] == 3
    assert result["total_hours"] == 13.0
    assert result["by_platform"] == {"PS4": 1, "PS5": 2}


def test_top_by_hours_sorted_desc_capped_at_ten() -> None:
    games = [g(f"G{i}", hours=float(20 - i)) for i in range(15)]
    result = library_overview.build_overview(snap(*games))
    assert len(result["top_by_hours"]) == 10
    assert result["top_by_hours"][0]["game"] == "G0"
    assert result["top_by_hours"][0]["hours"] == 20.0


def test_top_by_hours_puts_none_duration_last() -> None:
    games = [
        g("NoHours", hours=None),
        g("Played", hours=5.0),
    ]
    result = library_overview.build_overview(snap(*games))
    assert result["top_by_hours"][0]["game"] == "Played"
    assert result["top_by_hours"][1]["game"] == "NoHours"
    assert result["top_by_hours"][1]["hours"] is None


def test_recently_played_newest_first_capped_at_ten() -> None:
    games = [
        g(f"G{i}", last_played=datetime(2026, 1, i + 1)) for i in range(15)
    ]
    result = library_overview.build_overview(snap(*games))
    assert len(result["recently_played"]) == 10
    assert result["recently_played"][0]["game"] == "G14"
    assert result["recently_played"][0]["last_played"] == "2026-01-15T00:00:00"


def test_recently_played_puts_none_last() -> None:
    games = [
        g("Never", last_played=None),
        g("Recent", last_played=datetime(2026, 3, 1)),
    ]
    result = library_overview.build_overview(snap(*games))
    assert result["recently_played"][0]["game"] == "Recent"
    assert result["recently_played"][1]["game"] == "Never"
    assert result["recently_played"][1]["last_played"] is None


def test_platform_counter_skips_missing_platform() -> None:
    library = snap(
        g("A", platform=None, hours=1.0),
        g("B", platform="PS5", hours=2.0),
    )
    result = library_overview.build_overview(library)
    assert result["by_platform"] == {"PS5": 1}
    assert result["total_games"] == 2


def test_row_shape() -> None:
    library = snap(
        g("Elden Ring", platform="PS5", hours=42.5, sessions=17,
          last_played=datetime(2026, 4, 1, 21, 30))
    )
    row = library_overview.build_overview(library)["top_by_hours"][0]
    assert row == {
        "game": "Elden Ring",
        "platform": "PS5",
        "hours": 42.5,
        "sessions": 17,
        "last_played": "2026-04-01T21:30:00",
    }


def test_fetched_at_utc_none_becomes_none() -> None:
    library = Library(fetched_at_utc=None, profile="me", games=())
    result = library_overview.build_overview(library)
    assert result["fetched_at_utc"] is None
