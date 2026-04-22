from __future__ import annotations

from datetime import date

from echo.providers.films import taste
from tests.conftest import FakeDiary, FakeRating, film


def r(name: str, year: int | None, rating: float) -> FakeRating:
    return FakeRating(film=film(name, year=year, slug=name), rating=rating, date=date(2024, 1, 1))


def test_empty_inputs() -> None:
    result = taste.build([], [])
    assert result["total_rated_films"] == 0
    assert result["avg_rating"] is None
    assert result["favourite_decades"] == []
    assert result["most_rewatched"] == []


def test_favourite_decades_requires_minimum_sample() -> None:
    ratings = [r(f"A{i}", 1995, 4.0) for i in range(4)]  # 1990s — only 4, below threshold
    ratings += [r(f"B{i}", 2002, 3.5) for i in range(6)]  # 2000s — 6, above threshold
    result = taste.build([], ratings)
    decades = [d["decade"] for d in result["favourite_decades"]]
    assert "2000s" in decades
    assert "1990s" not in decades


def test_favourite_decades_sorted_by_count_desc() -> None:
    ratings = [r(f"A{i}", 1995, 4.0) for i in range(10)]
    ratings += [r(f"B{i}", 2005, 3.5) for i in range(6)]
    result = taste.build([], ratings)
    decades = [d["decade"] for d in result["favourite_decades"]]
    assert decades[0] == "1990s"
    assert decades[1] == "2000s"


def test_decade_avg_rating_computed_per_decade() -> None:
    ratings = [r(f"A{i}", 1995, 5.0) for i in range(5)]
    ratings += [r(f"B{i}", 2005, 3.0) for i in range(5)]
    result = taste.build([], ratings)
    by_decade = {d["decade"]: d["avg_rating"] for d in result["favourite_decades"]}
    assert by_decade["1990s"] == 5.0
    assert by_decade["2000s"] == 3.0


def test_films_without_year_dropped_from_decades() -> None:
    ratings = [r(f"U{i}", None, 4.0) for i in range(10)]
    result = taste.build([], ratings)
    assert result["favourite_decades"] == []


def test_most_rewatched_only_includes_count_gt_one() -> None:
    entries = [
        FakeDiary(film=film("A"), logged_date=date(2026, 2, 1)),
        FakeDiary(film=film("A"), logged_date=date(2026, 2, 10)),
        FakeDiary(film=film("A"), logged_date=date(2026, 3, 1)),
        FakeDiary(film=film("B"), logged_date=date(2026, 2, 5)),
    ]
    result = taste.build(entries, [])
    rewatched = {r["film"]: r["watches"] for r in result["most_rewatched"]}
    assert rewatched == {"A (2020)": 3}


def test_coverage_note_is_explicit_about_missing_data() -> None:
    result = taste.build([], [])
    assert "director" in result["coverage_note"].lower()


def test_avg_rating_across_all_ratings() -> None:
    result = taste.build([], [r("A", 2000, 3.0), r("B", 2000, 5.0)])
    assert result["avg_rating"] == 4.0
