from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

import pytest

from echo.core.periods import parse_period
from echo.core.registry import Registry
from echo.core.types import Event, Period


class _FakeProvider:
    def __init__(self, name: str, available: bool, events: list[Event]) -> None:
        self.name = name
        self._available = available
        self._events = events

    def is_available(self) -> bool:
        return self._available

    def events(self, period: Period) -> Iterator[Event]:
        for e in self._events:
            if period.contains(e.timestamp):
                yield e

    def register_tools(self, mcp) -> None:
        pass


def _ev(source: str, ts: datetime, title: str = "") -> Event:
    return Event(timestamp=ts, source=source, kind="x", title=title or source)


def test_duplicate_name_rejected() -> None:
    r = Registry()
    r.register(_FakeProvider("films", True, []))
    with pytest.raises(ValueError, match="already registered"):
        r.register(_FakeProvider("films", True, []))


def test_available_filters_out_unconfigured() -> None:
    r = Registry()
    r.register(_FakeProvider("films", True, []))
    r.register(_FakeProvider("music", False, []))
    names = [p.name for p in r.available()]
    assert names == ["films"]


def test_available_survives_raising_provider() -> None:
    class Broken:
        name = "broken"

        def is_available(self) -> bool:
            raise RuntimeError("boom")

        def events(self, period):
            yield from []

        def register_tools(self, mcp):
            pass

    r = Registry()
    r.register(Broken())
    r.register(_FakeProvider("films", True, []))
    assert [p.name for p in r.available()] == ["films"]


def test_iter_events_mixes_sources_inside_period() -> None:
    period = parse_period("2026-02")
    r = Registry()
    r.register(_FakeProvider("films", True, [
        _ev("films", datetime(2026, 2, 5)),
        _ev("films", datetime(2026, 3, 5)),  # outside
    ]))
    r.register(_FakeProvider("music", True, [
        _ev("music", datetime(2026, 2, 10)),
    ]))
    events = list(r.iter_events(period))
    assert {e.source for e in events} == {"films", "music"}
    assert len(events) == 2


def test_iter_events_respects_sources_filter() -> None:
    period = parse_period("all")
    r = Registry()
    r.register(_FakeProvider("films", True, [_ev("films", datetime(2026, 2, 1))]))
    r.register(_FakeProvider("music", True, [_ev("music", datetime(2026, 2, 1))]))
    only_music = list(r.iter_events(period, sources=["music"]))
    assert {e.source for e in only_music} == {"music"}


def test_iter_events_ignores_unknown_source_names() -> None:
    period = parse_period("all")
    r = Registry()
    r.register(_FakeProvider("films", True, [_ev("films", datetime(2026, 2, 1))]))
    events = list(r.iter_events(period, sources=["ghost"]))
    assert events == []


def test_iter_events_skips_failing_provider() -> None:
    class Exploding:
        name = "bad"

        def is_available(self) -> bool:
            return True

        def events(self, period):
            raise RuntimeError("boom")
            yield  # pragma: no cover

        def register_tools(self, mcp):
            pass

    period = parse_period("all")
    r = Registry()
    r.register(Exploding())
    r.register(_FakeProvider("films", True, [_ev("films", datetime(2026, 2, 1))]))
    events = list(r.iter_events(period))
    assert [e.source for e in events] == ["films"]
