"""Integration test for :class:`ShowsProvider` with a stubbed ``my.trakt.all``."""

from __future__ import annotations

import sys
import types
from datetime import UTC, datetime
from typing import Any

import pytest

from tests.conftest import (
    trakt_episode,
    trakt_history,
    trakt_movie,
    trakt_rating,
    trakt_show,
    trakt_watchlist,
)


class _StubTrakt:
    def __init__(self) -> None:
        self.history: list[Any] = []
        self.ratings: list[Any] = []
        self.watchlist: list[Any] = []


@pytest.fixture
def stub_trakt(monkeypatch: pytest.MonkeyPatch) -> _StubTrakt:
    """Install a fake ``my.trakt.all`` so ShowsProvider runs in-process."""
    stub = _StubTrakt()

    all_mod = types.ModuleType("my.trakt.all")
    all_mod.history = lambda: iter(stub.history)  # type: ignore[attr-defined]
    all_mod.ratings = lambda: iter(stub.ratings)  # type: ignore[attr-defined]
    all_mod.watchlist = lambda: iter(stub.watchlist)  # type: ignore[attr-defined]

    # is_available() probes `my.trakt.export.inputs()` — stub it to non-empty.
    export_mod = types.ModuleType("my.trakt.export")
    export_mod.inputs = lambda: ["fake.json"]  # type: ignore[attr-defined]

    trakt_pkg = types.ModuleType("my.trakt")
    monkeypatch.setitem(sys.modules, "my.trakt", trakt_pkg)
    monkeypatch.setitem(sys.modules, "my.trakt.all", all_mod)
    monkeypatch.setitem(sys.modules, "my.trakt.export", export_mod)
    return stub


def _ts(year: int, month: int, day: int, hour: int = 12) -> datetime:
    return datetime(year, month, day, hour, tzinfo=UTC)


def test_is_available_when_inputs_exist(stub_trakt) -> None:
    from echo.providers.shows import ShowsProvider

    assert ShowsProvider().is_available() is True


def test_is_available_false_when_no_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    export_mod = types.ModuleType("my.trakt.export")
    export_mod.inputs = list  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "my.trakt", types.ModuleType("my.trakt"))
    monkeypatch.setitem(sys.modules, "my.trakt.export", export_mod)
    # my.trakt.all doesn't need to exist for is_available.

    from echo.providers.shows import ShowsProvider

    assert ShowsProvider().is_available() is False


def test_events_splits_kinds_by_media_type(stub_trakt) -> None:
    from echo.core.periods import parse_period
    from echo.providers.shows import ShowsProvider

    bb = trakt_show("Breaking Bad", 2008, trakt_id=1)
    stub_trakt.history.extend(
        [
            trakt_history(_ts(2026, 2, 10), trakt_episode(bb, 1, 1, trakt_id=10)),
            trakt_history(_ts(2026, 2, 11), trakt_movie("Dune", 2021, trakt_id=501)),
        ]
    )

    events = list(ShowsProvider().events(parse_period("all")))
    kinds = [e.kind for e in events]
    assert "episode_watch" in kinds
    assert "movie_watch" in kinds


def test_events_filters_by_period(stub_trakt) -> None:
    from echo.core.periods import parse_period
    from echo.providers.shows import ShowsProvider

    bb = trakt_show("BB", 2008, trakt_id=1)
    stub_trakt.history.extend(
        [
            trakt_history(_ts(2026, 2, 10), trakt_episode(bb, 1, 1, trakt_id=10)),
            trakt_history(_ts(2026, 3, 10), trakt_episode(bb, 1, 2, trakt_id=11)),
        ]
    )
    events = list(ShowsProvider().events(parse_period("2026-02")))
    assert len(events) == 1


def test_events_drops_exception_rows(stub_trakt) -> None:
    from echo.core.periods import parse_period
    from echo.providers.shows import ShowsProvider

    bb = trakt_show("BB")
    stub_trakt.history.extend(
        [
            ValueError("broken row"),
            trakt_history(_ts(2026, 2, 10), trakt_episode(bb, 1, 1, trakt_id=10)),
        ]
    )
    events = list(ShowsProvider().events(parse_period("all")))
    titles = [e.title for e in events]
    assert len(titles) == 1
    assert titles[0].startswith("BB")


def test_episode_event_title_includes_season_episode(stub_trakt) -> None:
    from echo.core.periods import parse_period
    from echo.providers.shows import ShowsProvider

    bb = trakt_show("Breaking Bad", 2008, trakt_id=1)
    stub_trakt.history.append(
        trakt_history(
            _ts(2026, 2, 10),
            trakt_episode(bb, 1, 2, title="Cat's in the Bag", trakt_id=11),
        )
    )
    event = next(ShowsProvider().events(parse_period("all")))
    assert event.title == "Breaking Bad S01E02 — Cat's in the Bag"
    assert event.payload["media_type"] == "episode"
    assert event.payload["season"] == 1
    assert event.payload["episode"] == 2
    assert event.payload["show"] == "Breaking Bad"


def test_watchlist_add_event_emitted(stub_trakt) -> None:
    from echo.core.periods import parse_period
    from echo.providers.shows import ShowsProvider

    stub_trakt.watchlist.append(
        trakt_watchlist(trakt_show("Shogun", 2024, trakt_id=77), _ts(2024, 3, 10))
    )
    events = list(ShowsProvider().events(parse_period("all")))
    wl = [e for e in events if e.kind == "watchlist_add"]
    assert len(wl) == 1
    assert wl[0].payload["media_type"] == "show"


def test_watched_summary_delegates_to_aggregation(stub_trakt) -> None:
    from echo.core.periods import parse_period
    from echo.providers.shows import ShowsProvider

    bb = trakt_show("BB", 2008, trakt_id=1)
    stub_trakt.history.extend(
        [
            trakt_history(_ts(2026, 2, 1), trakt_episode(bb, 1, 1, trakt_id=10)),
            trakt_history(_ts(2026, 2, 2), trakt_episode(bb, 1, 2, trakt_id=11)),
        ]
    )
    result = ShowsProvider().watched_summary(parse_period("2026-02"))
    assert result["episodes_played"] == 2
    assert result["distinct_shows"] == 1


def test_taste_profile_passes_ratings_through(stub_trakt) -> None:
    from echo.providers.shows import ShowsProvider

    bb = trakt_show("BB", trakt_id=1)
    stub_trakt.ratings.append(trakt_rating(bb, 10))
    result = ShowsProvider().taste_profile()
    assert result["total_rated"] == 1
    assert result["avg_rating"] == 10
