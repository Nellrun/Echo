from __future__ import annotations

import sys
import types
from datetime import date, datetime

import pytest

from tests.conftest import FakeDiary, FakeWatchlistItem, film


class _StubLetterboxd:
    """Container for the fake HPI module's mutable sources."""

    def __init__(self) -> None:
        self.diary: list[FakeDiary] = []
        self.watchlist: list[FakeWatchlistItem] = []


@pytest.fixture
def stub_letterboxd(monkeypatch: pytest.MonkeyPatch) -> _StubLetterboxd:
    """Inject a fake ``my.letterboxd.all`` so the provider can be driven in-process."""
    stub = _StubLetterboxd()

    ll = types.ModuleType("my.letterboxd.all")
    ll.diary = lambda: iter(stub.diary)  # type: ignore[attr-defined]
    ll.ratings = lambda: iter([])  # type: ignore[attr-defined]
    ll.watchlist = lambda: iter(stub.watchlist)  # type: ignore[attr-defined]

    my_pkg = types.ModuleType("my")
    letterboxd_pkg = types.ModuleType("my.letterboxd")
    monkeypatch.setitem(sys.modules, "my", my_pkg)
    monkeypatch.setitem(sys.modules, "my.letterboxd", letterboxd_pkg)
    monkeypatch.setitem(sys.modules, "my.letterboxd.all", ll)
    return stub


def test_events_title_includes_year_when_available(stub_letterboxd) -> None:
    from echo.core.periods import parse_period
    from echo.providers.films import FilmsProvider

    stub_letterboxd.diary.append(
        FakeDiary(film=film("Amélie", year=2001), logged_date=date(2026, 2, 5), rating=5.0)
    )
    events = list(FilmsProvider().events(parse_period("all")))
    assert len(events) == 1
    assert events[0].title == "Amélie (2001)"
    assert events[0].timestamp == datetime(2026, 2, 5)
    assert events[0].source == "films"
    assert events[0].kind == "diary"
    assert events[0].payload["rating"] == 5.0


def test_events_filters_by_period(stub_letterboxd) -> None:
    from echo.core.periods import parse_period
    from echo.providers.films import FilmsProvider

    stub_letterboxd.diary.extend([
        FakeDiary(film=film("In"), logged_date=date(2026, 2, 15)),
        FakeDiary(film=film("Out"), logged_date=date(2026, 3, 5)),
    ])
    events = list(FilmsProvider().events(parse_period("2026-02")))
    assert [e.title for e in events] == ["In (2020)"]


def test_events_uses_watched_date_when_set(stub_letterboxd) -> None:
    from echo.core.periods import parse_period
    from echo.providers.films import FilmsProvider

    stub_letterboxd.diary.append(
        FakeDiary(
            film=film("X"),
            logged_date=date(2026, 3, 30),
            watched_date=date(2026, 2, 20),
        )
    )
    events = list(FilmsProvider().events(parse_period("2026-02")))
    assert len(events) == 1
    assert events[0].timestamp.date() == date(2026, 2, 20)


def test_events_drops_exception_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    from echo.core.periods import parse_period
    from echo.providers.films import FilmsProvider

    ll = types.ModuleType("my.letterboxd.all")
    ll.diary = lambda: iter([  # type: ignore[attr-defined]
        ValueError("broken row"),
        FakeDiary(film=film("Good"), logged_date=date(2026, 2, 5)),
    ])
    ll.ratings = lambda: iter([])  # type: ignore[attr-defined]
    ll.watchlist = lambda: iter([])  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "my", types.ModuleType("my"))
    monkeypatch.setitem(sys.modules, "my.letterboxd", types.ModuleType("my.letterboxd"))
    monkeypatch.setitem(sys.modules, "my.letterboxd.all", ll)

    events = list(FilmsProvider().events(parse_period("all")))
    assert [e.title for e in events] == ["Good (2020)"]


def test_diary_payload_includes_review_and_tags(stub_letterboxd) -> None:
    from echo.core.periods import parse_period
    from echo.providers.films import FilmsProvider

    stub_letterboxd.diary.append(
        FakeDiary(
            film=film("Memento"),
            logged_date=date(2026, 2, 5),
            review="brilliant on rewatch",
            tags=("noir", "rewatch"),
        )
    )
    events = list(FilmsProvider().events(parse_period("all")))
    assert events[0].payload["review"] == "brilliant on rewatch"
    assert events[0].payload["tags"] == ["noir", "rewatch"]


def test_events_emits_watchlist_add_kind(stub_letterboxd) -> None:
    from echo.core.periods import parse_period
    from echo.providers.films import FilmsProvider

    stub_letterboxd.watchlist.append(
        FakeWatchlistItem(film=film("Dune", year=2021), date=date(2026, 2, 10))
    )
    events = list(FilmsProvider().events(parse_period("all")))
    kinds = [e.kind for e in events]
    assert "watchlist_add" in kinds
    wl = next(e for e in events if e.kind == "watchlist_add")
    assert wl.timestamp == datetime(2026, 2, 10)
    assert wl.title == "+ watchlist: Dune (2021)"
    assert wl.payload["film"] == "Dune"
    assert wl.payload["year"] == 2021


def test_events_watchlist_filters_by_period(stub_letterboxd) -> None:
    from echo.core.periods import parse_period
    from echo.providers.films import FilmsProvider

    stub_letterboxd.watchlist.extend([
        FakeWatchlistItem(film=film("In"), date=date(2026, 2, 5)),
        FakeWatchlistItem(film=film("Out"), date=date(2026, 3, 5)),
    ])
    events = list(FilmsProvider().events(parse_period("2026-02")))
    wl_titles = [e.title for e in events if e.kind == "watchlist_add"]
    assert wl_titles == ["+ watchlist: In (2020)"]


def test_watchlist_overview_delegates_to_aggregation(stub_letterboxd) -> None:
    from echo.providers.films import FilmsProvider

    stub_letterboxd.watchlist.extend([
        FakeWatchlistItem(film=film("A", year=2015), date=date(2026, 1, 1)),
        FakeWatchlistItem(film=film("B", year=2022), date=date(2026, 2, 1)),
    ])
    overview = FilmsProvider().watchlist_overview()
    assert overview["total"] == 2
    assert overview["by_release_decade"] == {"2010s": 1, "2020s": 1}


def test_watchlist_public_accessor_materialises_list(stub_letterboxd) -> None:
    from echo.providers.films import FilmsProvider

    stub_letterboxd.watchlist.append(
        FakeWatchlistItem(film=film("A"), date=date(2026, 1, 1))
    )
    items = FilmsProvider().watchlist()
    assert len(items) == 1
    assert items[0].film.name == "A"
