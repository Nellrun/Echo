"""Integration tests for :class:`PlaytimeProvider` with a stubbed ``my.gwm_stats``."""

from __future__ import annotations

import sys
import types
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from echo.core.periods import parse_period

# ---------------------------------------------------------------------------
# Fake HPI domain objects (shape of my.gwm_stats.common.{Session,Trophy,...})
# ---------------------------------------------------------------------------


def fake_session(
    *,
    title_id: str = "CUSA18774_00",
    title_name: str = "NieR Replicant",
    platform: str = "PS5",
    source: str = "psn",
    started_at: datetime,
    ended_at: datetime | None = None,
    seconds: int | None = 3600,
) -> SimpleNamespace:
    return SimpleNamespace(
        title_id=title_id,
        title_name=title_name,
        platform=platform,
        source=source,
        started_at=started_at,
        ended_at=ended_at,
        duration=timedelta(seconds=seconds) if seconds is not None else None,
    )


def fake_trophy(
    *,
    title_name: str = "NieR Replicant",
    trophy_name: str = "Boss of the Junk Heap",
    trophy_type: str = "bronze",
    rarity: float | None = 17.3,
    source: str = "psn",
    earned_at: datetime | None,
    np_comm_id: str = "NPWR19895_00",
    trophy_id: int = 36,
) -> SimpleNamespace:
    return SimpleNamespace(
        title_name=title_name,
        trophy_name=trophy_name,
        trophy_type=trophy_type,
        rarity=rarity,
        source=source,
        earned_at=earned_at,
        np_comm_id=np_comm_id,
        trophy_id=trophy_id,
    )


def fake_summary() -> SimpleNamespace:
    return SimpleNamespace(
        fetched_at_utc=datetime(2026, 6, 21, 22, tzinfo=UTC),
        name="Nellrun",
        player_name="Nellrun",
        member_count=5,
        is_self=False,
        totals=SimpleNamespace(
            total_duration=timedelta(seconds=105853),
            sessions_count=16,
            games_count=5,
            avg_session=timedelta(seconds=6615),
            longest_session=timedelta(seconds=17243),
            first_started_at=datetime(2026, 6, 17, 13, 49, tzinfo=UTC),
            last_ended_at=datetime(2026, 6, 21, 21, 32, tzinfo=UTC),
        ),
        top_games=(
            SimpleNamespace(
                title_id="CUSA18774_00",
                title_name="NieR Replicant",
                platform="PS5",
                source="psn",
                total_duration=timedelta(seconds=64432),
                sessions_count=7,
            ),
        ),
        platform_breakdown=(
            SimpleNamespace(
                source="psn",
                total_duration=timedelta(seconds=90082),
                sessions_count=13,
                games_count=3,
            ),
            SimpleNamespace(
                source="steam",
                total_duration=timedelta(seconds=10016),
                sessions_count=2,
                games_count=1,
            ),
        ),
    )


class _Stub:
    def __init__(self) -> None:
        self.sessions: list[Any] = []
        self.trophies: list[Any] = []
        self.summary: Any = fake_summary()
        self.inputs: list[Any] = ["fake.json"]


@pytest.fixture
def stub_gwm(monkeypatch: pytest.MonkeyPatch) -> _Stub:
    stub = _Stub()

    all_mod = types.ModuleType("my.gwm_stats.all")
    all_mod.sessions = lambda: iter(stub.sessions)  # type: ignore[attr-defined]
    all_mod.trophies = lambda: iter(stub.trophies)  # type: ignore[attr-defined]
    all_mod.summary = lambda: stub.summary  # type: ignore[attr-defined]

    export_mod = types.ModuleType("my.gwm_stats.export")
    export_mod.inputs = lambda: stub.inputs  # type: ignore[attr-defined]

    pkg = types.ModuleType("my.gwm_stats")
    monkeypatch.setitem(sys.modules, "my.gwm_stats", pkg)
    monkeypatch.setitem(sys.modules, "my.gwm_stats.all", all_mod)
    monkeypatch.setitem(sys.modules, "my.gwm_stats.export", export_mod)
    return stub


# ---------------------------------------------------------------------------
# _normalise / _naive — pure, no stub needed
# ---------------------------------------------------------------------------


def test_naive_strips_tz() -> None:
    from echo.providers.playtime import _naive

    aware = datetime(2026, 6, 21, 19, 42, tzinfo=UTC)
    out = _naive(aware)
    assert out is not None and out.tzinfo is None
    assert _naive(None) is None


def test_normalise_session_maps_fields() -> None:
    from echo.providers.playtime import _normalise_session

    s = fake_session(started_at=datetime(2026, 6, 21, 19, 42, tzinfo=UTC), seconds=7200)
    out = _normalise_session(s)
    assert out is not None
    assert out.when == datetime(2026, 6, 21, 19, 42)  # tz stripped
    assert out.game == "NieR Replicant"
    assert out.source == "psn"
    assert out.duration_hours == 2.0


def test_normalise_session_drops_without_duration() -> None:
    from echo.providers.playtime import _normalise_session

    s = fake_session(started_at=datetime(2026, 6, 21, tzinfo=UTC), seconds=None)
    assert _normalise_session(s) is None


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------


def test_is_available_true(stub_gwm: _Stub) -> None:
    from echo.providers.playtime import PlaytimeProvider

    assert PlaytimeProvider().is_available() is True


def test_is_available_false_when_no_inputs(stub_gwm: _Stub) -> None:
    from echo.providers.playtime import PlaytimeProvider

    stub_gwm.inputs = []
    assert PlaytimeProvider().is_available() is False


# ---------------------------------------------------------------------------
# events — play + trophy
# ---------------------------------------------------------------------------


def test_events_emits_play_and_trophy(stub_gwm: _Stub) -> None:
    from echo.providers.playtime import PlaytimeProvider

    stub_gwm.sessions = [
        fake_session(started_at=datetime(2026, 6, 20, 18, tzinfo=UTC), seconds=3600)
    ]
    stub_gwm.trophies = [
        fake_trophy(earned_at=datetime(2026, 6, 20, 19, tzinfo=UTC))
    ]
    events = list(PlaytimeProvider().events(parse_period("2026-06")))
    kinds = {e.kind for e in events}
    assert kinds == {"play", "trophy"}
    # all timestamps naive after normalisation
    assert all(e.timestamp.tzinfo is None for e in events)
    play = next(e for e in events if e.kind == "play")
    assert play.payload["source"] == "psn"


def test_events_filtered_by_period(stub_gwm: _Stub) -> None:
    from echo.providers.playtime import PlaytimeProvider

    stub_gwm.sessions = [
        fake_session(started_at=datetime(2026, 6, 20, tzinfo=UTC)),
        fake_session(started_at=datetime(2026, 7, 20, tzinfo=UTC)),  # outside
    ]
    events = list(PlaytimeProvider().events(parse_period("2026-06")))
    assert len(events) == 1


def test_events_skips_trophy_without_earned_at(stub_gwm: _Stub) -> None:
    from echo.providers.playtime import PlaytimeProvider

    stub_gwm.trophies = [fake_trophy(earned_at=None)]
    events = list(PlaytimeProvider().events(parse_period("all")))
    assert events == []


def test_events_skips_broken_rows(stub_gwm: _Stub) -> None:
    from echo.providers.playtime import PlaytimeProvider

    stub_gwm.sessions = [
        ValueError("boom"),
        fake_session(started_at=datetime(2026, 6, 20, tzinfo=UTC)),
    ]
    events = list(PlaytimeProvider().events(parse_period("all")))
    assert len(events) == 1


# ---------------------------------------------------------------------------
# insight methods
# ---------------------------------------------------------------------------


def test_play_summary(stub_gwm: _Stub) -> None:
    from echo.providers.playtime import PlaytimeProvider

    stub_gwm.sessions = [
        fake_session(started_at=datetime(2026, 6, 20, tzinfo=UTC), source="psn", seconds=3600),
        fake_session(
            title_name="PoE2",
            platform="Steam",
            source="steam",
            started_at=datetime(2026, 6, 21, tzinfo=UTC),
            seconds=7200,
        ),
    ]
    out = PlaytimeProvider().play_summary(parse_period("2026-06"))
    assert out["total_sessions"] == 2
    assert out["total_hours"] == 3.0
    assert out["hours_by_source"] == {"steam": 2.0, "psn": 1.0}


def test_trophy_summary_all(stub_gwm: _Stub) -> None:
    from echo.providers.playtime import PlaytimeProvider

    stub_gwm.trophies = [
        fake_trophy(earned_at=datetime(2026, 6, 21, tzinfo=UTC), trophy_type="platinum", rarity=2.0),
        fake_trophy(earned_at=None, trophy_name="Undated", rarity=None),
    ]
    out = PlaytimeProvider().trophy_summary(parse_period("all"))
    # both counted under all-time
    assert out["total_trophies"] == 2


def test_trophy_summary_bounded_drops_undated(stub_gwm: _Stub) -> None:
    from echo.providers.playtime import PlaytimeProvider

    stub_gwm.trophies = [
        fake_trophy(earned_at=datetime(2026, 6, 21, tzinfo=UTC)),
        fake_trophy(earned_at=None, trophy_name="Undated"),
    ]
    out = PlaytimeProvider().trophy_summary(parse_period("2026-06"))
    assert out["total_trophies"] == 1


def test_overview(stub_gwm: _Stub) -> None:
    from echo.providers.playtime import PlaytimeProvider

    stub_gwm.trophies = [
        fake_trophy(earned_at=datetime(2026, 6, 21, tzinfo=UTC)),
        fake_trophy(earned_at=datetime(2026, 6, 20, tzinfo=UTC), trophy_id=37),
    ]
    out = PlaytimeProvider().overview()
    assert out["player"] == "Nellrun"
    assert out["total_sessions"] == 16
    assert out["trophies_earned"] == 2
    assert out["total_hours"] == round(105853 / 3600, 2)
    assert len(out["top_games"]) == 1
    assert [p["source"] for p in out["platform_breakdown"]] == ["psn", "steam"]
