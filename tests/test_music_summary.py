from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from echo.core.periods import parse_period
from echo.providers.music import summary


@dataclass
class FakeScrobble:
    when: datetime
    artist: str
    track: str
    album: str | None = None


def s(ts: datetime, artist: str, track: str, album: str | None = None) -> FakeScrobble:
    return FakeScrobble(when=ts, artist=artist, track=track, album=album)


def test_empty_summary() -> None:
    result = summary.build([], period=parse_period("all"))
    assert result["total_scrobbles"] == 0
    assert result["unique_artists"] == 0
    assert result["unique_tracks"] == 0
    assert result["top_artists"] == []


def test_counts_and_uniques() -> None:
    scrobs = [
        s(datetime(2026, 2, 1, 10), "A", "one"),
        s(datetime(2026, 2, 1, 11), "A", "one"),
        s(datetime(2026, 2, 2, 9), "A", "two"),
        s(datetime(2026, 2, 3, 9), "B", "x"),
    ]
    result = summary.build(scrobs, period=parse_period("2026-02"))
    assert result["total_scrobbles"] == 4
    assert result["unique_artists"] == 2
    assert result["unique_tracks"] == 3


def test_top_artists_sorted_desc() -> None:
    scrobs = [s(datetime(2026, 2, 1), "A", "x") for _ in range(5)]
    scrobs += [s(datetime(2026, 2, 1), "B", "x") for _ in range(3)]
    scrobs += [s(datetime(2026, 2, 1), "C", "x") for _ in range(1)]
    result = summary.build(scrobs, period=parse_period("2026-02"))
    assert [r["value"] for r in result["top_artists"]] == ["A", "B", "C"]
    assert result["top_artists"][0]["scrobbles"] == 5


def test_daily_distribution() -> None:
    scrobs = [
        s(datetime(2026, 2, 1, 10), "A", "x"),
        s(datetime(2026, 2, 1, 11), "A", "x"),
        s(datetime(2026, 2, 2, 9), "B", "y"),
    ]
    result = summary.build(scrobs, period=parse_period("2026-02"))
    assert result["daily_distribution"] == {"2026-02-01": 2, "2026-02-02": 1}


def test_does_not_expose_listening_hours() -> None:
    # Last.fm has no duration field; fabricating hours would mislead callers.
    result = summary.build([], period=parse_period("2026-02"))
    assert "listening_hours" not in result


def test_tz_aware_timestamps_are_accepted() -> None:
    scrobs = [s(datetime(2026, 2, 1, 10, tzinfo=timezone.utc), "A", "x")]
    result = summary.build(scrobs, period=parse_period("2026-02"))
    assert "2026-02-01" in result["daily_distribution"]


def test_empty_artist_not_counted_in_top() -> None:
    scrobs = [
        s(datetime(2026, 2, 1), "", "ghost"),
        s(datetime(2026, 2, 2), "Real", "song"),
    ]
    result = summary.build(scrobs, period=parse_period("2026-02"))
    assert [r["value"] for r in result["top_artists"]] == ["Real"]
