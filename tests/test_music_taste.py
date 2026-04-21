from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from echo.providers.music import taste


@dataclass
class FakeScrobble:
    when: datetime
    artist: str


def scrobs_of(artist: str, when: datetime, n: int) -> list[FakeScrobble]:
    return [FakeScrobble(when=when, artist=artist) for _ in range(n)]


NOW = datetime(2026, 4, 21, 12, 0, 0)
LAST_YEAR = NOW - timedelta(days=30)
OLDER = NOW - timedelta(days=300)
ANCIENT = NOW - timedelta(days=1000)


def test_empty_taste() -> None:
    result = taste.build([], now=NOW)
    assert result["core_artists"] == []
    assert result["fling_artists"] == []


def test_core_artist_present_in_all_windows() -> None:
    scrobs = []
    # Steady: listened a lot ancient, last year, and last month.
    scrobs += scrobs_of("Steady", ANCIENT, 50)
    scrobs += scrobs_of("Steady", OLDER, 50)
    scrobs += scrobs_of("Steady", NOW - timedelta(days=5), 50)
    # Filler so Steady isn't the only artist anywhere.
    scrobs += scrobs_of("Noise", ANCIENT, 5)

    result = taste.build(scrobs, now=NOW)
    assert "Steady" in result["core_artists"]
    assert "Steady" not in result["fling_artists"]


def test_fling_artist_only_in_last_month_window() -> None:
    scrobs = []
    # Brand-new obsession — only exists in last month.
    scrobs += scrobs_of("Fling", NOW - timedelta(days=3), 30)
    # Long-term filler — none of these artists appear in last month.
    for i in range(5):
        scrobs += scrobs_of(f"Old{i}", ANCIENT, 10)

    result = taste.build(scrobs, now=NOW)
    assert "Fling" in result["fling_artists"]
    assert "Fling" not in result["core_artists"]


def test_core_artist_is_top_in_both_windows() -> None:
    scrobs = []
    scrobs += scrobs_of("Steady", ANCIENT, 50)
    scrobs += scrobs_of("Steady", OLDER, 50)
    scrobs += scrobs_of("Steady", NOW - timedelta(days=5), 50)
    scrobs += scrobs_of("Noise", ANCIENT, 5)

    result = taste.build(scrobs, now=NOW)
    assert "Steady" in result["core_artists"]
    assert "Steady" not in result["fling_artists"]


def test_long_term_excludes_last_month_listening() -> None:
    scrobs = []
    # Fling is only in last month — long_term must not see it.
    scrobs += scrobs_of("Fling", NOW - timedelta(days=3), 100)
    result = taste.build(scrobs, now=NOW)
    long_term_artists = [r["artist"] for r in result["top_long_term"]]
    assert "Fling" not in long_term_artists


def test_top_lists_are_sorted_desc() -> None:
    scrobs = []
    scrobs += scrobs_of("A", NOW - timedelta(days=1), 100)
    scrobs += scrobs_of("B", NOW - timedelta(days=1), 50)
    scrobs += scrobs_of("C", NOW - timedelta(days=1), 10)
    result = taste.build(scrobs, now=NOW)
    last_month_artists = [r["artist"] for r in result["top_last_month"]]
    assert last_month_artists[:3] == ["A", "B", "C"]


def test_scrobbles_without_artist_dropped() -> None:
    scrobs = [
        FakeScrobble(when=NOW - timedelta(days=1), artist=""),
        FakeScrobble(when=NOW - timedelta(days=1), artist="Real"),
    ]
    result = taste.build(scrobs, now=NOW)
    artists = [r["artist"] for r in result["top_last_month"]]
    assert artists == ["Real"]
