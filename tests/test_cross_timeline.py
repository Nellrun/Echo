from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

from echo.core.periods import parse_period
from echo.core.registry import Registry
from echo.core.types import Event, Period
from echo.providers.cross import timeline


class Fixed:
    def __init__(self, name: str, events: list[Event]) -> None:
        self.name = name
        self._events = events

    def is_available(self) -> bool:
        return True

    def events(self, period: Period) -> Iterator[Event]:
        for e in self._events:
            if period.contains(e.timestamp):
                yield e

    def register_tools(self, mcp) -> None:  # noqa: ARG002
        pass


def film_event(ts: datetime, title: str) -> Event:
    return Event(timestamp=ts, source="films", kind="diary", title=title, payload={})


def scrobble(ts: datetime, artist: str, track: str) -> Event:
    return Event(
        timestamp=ts,
        source="music",
        kind="scrobble",
        title=f"{artist} — {track}",
        payload={"artist": artist, "track": track},
    )


def test_mixed_sources_merge_and_sort() -> None:
    r = Registry()
    r.register(Fixed("films", [film_event(datetime(2026, 2, 10, 20), "A")]))
    r.register(Fixed("music", [scrobble(datetime(2026, 2, 9, 14), "X", "y")]))
    result = timeline.build(parse_period("2026-02"), registry=r)
    timestamps = [e["timestamp"] for e in result["events"]]
    assert timestamps == sorted(timestamps)
    assert set(result["sources_seen"]) == {"films", "music"}


def test_music_collapsed_to_daily_summary() -> None:
    r = Registry()
    music_events = [
        scrobble(datetime(2026, 2, 10, 10), "A", "s1"),
        scrobble(datetime(2026, 2, 10, 11), "A", "s2"),
        scrobble(datetime(2026, 2, 10, 12), "B", "s3"),
    ]
    r.register(Fixed("music", music_events))
    result = timeline.build(parse_period("2026-02"), registry=r)
    # One collapsed summary, not three scrobble rows.
    assert result["total_events"] == 1
    evt = result["events"][0]
    assert evt["kind"] == "daily_summary"
    assert evt["payload"]["scrobbles"] == 3
    assert evt["payload"]["top_artist"] == "A"


def test_film_events_are_not_collapsed() -> None:
    r = Registry()
    films = [
        film_event(datetime(2026, 2, 10, 20), "A"),
        film_event(datetime(2026, 2, 10, 22), "B"),
    ]
    r.register(Fixed("films", films))
    result = timeline.build(parse_period("2026-02"), registry=r)
    assert result["total_events"] == 2
    assert {e["title"] for e in result["events"]} == {"A", "B"}


def test_truncation_flag_and_cap() -> None:
    r = Registry()
    films = [film_event(datetime(2026, 2, d + 1, 20), f"F{d}") for d in range(5)]
    r.register(Fixed("films", films))
    result = timeline.build(parse_period("2026-02"), registry=r, max_events=3)
    assert result["truncated"] is True
    assert result["total_events"] == 3
    # Truncation keeps the earliest events; the timeline is ascending.
    assert [e["title"] for e in result["events"]] == ["F0", "F1", "F2"]


def test_source_filter_narrows_providers() -> None:
    r = Registry()
    r.register(Fixed("films", [film_event(datetime(2026, 2, 1), "A")]))
    r.register(Fixed("music", [scrobble(datetime(2026, 2, 2), "B", "x")]))
    result = timeline.build(parse_period("2026-02"), registry=r, sources=["films"])
    assert result["sources_seen"] == ["films"]


def test_empty_registry_produces_empty_timeline() -> None:
    r = Registry()
    result = timeline.build(parse_period("2026-02"), registry=r)
    assert result["total_events"] == 0
    assert result["truncated"] is False
    assert result["sources_seen"] == []
