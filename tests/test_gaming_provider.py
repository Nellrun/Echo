"""Regression tests for the gaming provider's HPI adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from echo.providers.gaming import _normalise


@dataclass
class FakeSession:
    """Minimal shape of ``my.ps_timetracker.common.Session``."""

    playtime_id: int
    game_title: str | None
    platform: str | None
    duration: timedelta | None
    start_local: datetime | None
    end_local: datetime | None = None
    game_id: str | None = None


def test_normalise_maps_fields() -> None:
    s = FakeSession(
        playtime_id=7,
        game_title="Elden Ring",
        platform="PS5",
        duration=timedelta(seconds=3600),
        start_local=datetime(2026, 2, 1, 20, 0),
        end_local=datetime(2026, 2, 1, 21, 0),
        game_id="PPSA02530_00",
    )
    out = _normalise(s)
    assert out is not None
    assert out.when == datetime(2026, 2, 1, 20, 0)
    assert out.game == "Elden Ring"
    assert out.platform == "PS5"
    assert out.duration_seconds == 3600
    assert out.duration_hours == 1.0
    assert out.end_local == datetime(2026, 2, 1, 21, 0)
    assert out.game_id == "PPSA02530_00"
    assert out.playtime_id == 7


def test_normalise_drops_session_without_start() -> None:
    s = FakeSession(
        playtime_id=1,
        game_title="X",
        platform="PS5",
        duration=timedelta(seconds=60),
        start_local=None,
    )
    # Without a start timestamp we can't place the session on a timeline
    # — aggregations expect ``when`` to be non-null.
    assert _normalise(s) is None


def test_normalise_drops_session_without_duration() -> None:
    s = FakeSession(
        playtime_id=1,
        game_title="X",
        platform="PS5",
        duration=None,
        start_local=datetime(2026, 2, 1),
    )
    assert _normalise(s) is None


def test_normalise_coerces_missing_strings_to_empty() -> None:
    s = FakeSession(
        playtime_id=1,
        game_title=None,
        platform=None,
        duration=timedelta(seconds=30),
        start_local=datetime(2026, 2, 1),
    )
    out = _normalise(s)
    assert out is not None
    assert out.game == ""
    assert out.platform == ""
    assert out.duration_seconds == 30
