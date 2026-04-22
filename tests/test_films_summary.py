from __future__ import annotations

from datetime import date

from echo.core.periods import parse_period
from echo.providers.films import summary
from tests.conftest import FakeDiary, film


def d(year: int, month: int, day: int) -> date:
    return date(year, month, day)


def test_empty_diary_gives_zero_counts() -> None:
    result = summary.build([], period=parse_period("2026-02"))
    assert result["count"] == 0
    assert result["avg_rating"] is None
    assert result["top_rated"] == []
    assert result["rewatches_count"] == 0


def test_summary_uses_watched_date_when_present() -> None:
    entries = [
        FakeDiary(film=film("A"), logged_date=d(2026, 3, 1), watched_date=d(2026, 2, 10), rating=4.0),
        FakeDiary(film=film("B"), logged_date=d(2026, 2, 5), watched_date=None, rating=3.5),
    ]
    result = summary.build(entries, period=parse_period("2026-02"))
    assert result["count"] == 2
    assert result["daily_distribution"] == {"2026-02-05": 1, "2026-02-10": 1}


def test_avg_rating_skips_unrated() -> None:
    entries = [
        FakeDiary(film=film("A"), logged_date=d(2026, 2, 1), rating=4.0),
        FakeDiary(film=film("B"), logged_date=d(2026, 2, 2), rating=None),
        FakeDiary(film=film("C"), logged_date=d(2026, 2, 3), rating=3.0),
    ]
    result = summary.build(entries, period=parse_period("2026-02"))
    assert result["avg_rating"] == 3.5


def test_rewatches_counted_but_dont_affect_top_rated() -> None:
    entries = [
        FakeDiary(film=film("A"), logged_date=d(2026, 2, 1), rating=4.5, rewatch=True),
        FakeDiary(film=film("A"), logged_date=d(2026, 2, 5), rating=4.5, rewatch=False),
    ]
    result = summary.build(entries, period=parse_period("2026-02"))
    assert result["rewatches_count"] == 1
    assert len(result["top_rated"]) == 2


def test_top_rated_limited_to_ten_and_sorted_desc() -> None:
    entries = [
        FakeDiary(film=film(f"F{i}"), logged_date=d(2026, 2, i + 1), rating=float(i) / 10.0 * 5.0)
        for i in range(1, 15)
    ]
    result = summary.build(entries, period=parse_period("2026-02"))
    assert len(result["top_rated"]) == 10
    ratings = [r["rating"] for r in result["top_rated"]]
    assert ratings == sorted(ratings, reverse=True)


def test_top_rated_tiebreaks_by_more_recent_watch() -> None:
    entries = [
        FakeDiary(film=film("Old"), logged_date=d(2026, 2, 1), rating=5.0),
        FakeDiary(film=film("New"), logged_date=d(2026, 2, 20), rating=5.0),
    ]
    result = summary.build(entries, period=parse_period("2026-02"))
    assert result["top_rated"][0]["film"].startswith("New")


def test_period_label_echoed() -> None:
    result = summary.build([], period=parse_period("2026-Q1"))
    assert result["period"] == "2026-Q1"


def test_film_label_handles_missing_year() -> None:
    entries = [FakeDiary(film=film("Untitled", year=None), logged_date=d(2026, 2, 1), rating=4.0)]
    result = summary.build(entries, period=parse_period("2026-02"))
    assert result["top_rated"][0]["film"] == "Untitled"


def test_most_watched_counts_include_rewatches() -> None:
    entries = [
        FakeDiary(film=film("A"), logged_date=d(2026, 2, 1)),
        FakeDiary(film=film("A"), logged_date=d(2026, 2, 10), rewatch=True),
        FakeDiary(film=film("B"), logged_date=d(2026, 2, 3)),
    ]
    result = summary.build(entries, period=parse_period("2026-02"))
    top = {r["value"]: r["watches"] for r in result["most_watched_films"]}
    assert top["A (2020)"] == 2
    assert top["B (2020)"] == 1
