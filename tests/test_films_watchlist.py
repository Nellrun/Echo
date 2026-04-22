from __future__ import annotations

from datetime import date

from echo.providers.films import watchlist as _watchlist
from tests.conftest import FakeWatchlistItem, film


def wli(name: str, year: int | None, added: date) -> FakeWatchlistItem:
    return FakeWatchlistItem(film=film(name, year=year), date=added)


def test_empty_watchlist() -> None:
    result = _watchlist.build_overview([])
    assert result["total"] == 0
    assert result["by_release_decade"] == {}
    assert result["recent_additions"] == []
    assert result["oldest_pending"] == []


def test_by_release_decade_sorted_by_decade() -> None:
    items = [
        wli("A", 2007, date(2026, 1, 1)),
        wli("B", 2012, date(2026, 2, 1)),
        wli("C", 2018, date(2026, 3, 1)),
        wli("D", 2021, date(2026, 4, 1)),
    ]
    result = _watchlist.build_overview(items)
    assert result["by_release_decade"] == {"2000s": 1, "2010s": 2, "2020s": 1}
    # Dict should iterate in sorted order.
    assert list(result["by_release_decade"].keys()) == ["2000s", "2010s", "2020s"]


def test_by_release_decade_skips_items_without_year() -> None:
    items = [
        wli("Known", 2015, date(2026, 1, 1)),
        wli("Unknown", None, date(2026, 2, 1)),
    ]
    result = _watchlist.build_overview(items)
    assert result["by_release_decade"] == {"2010s": 1}
    assert result["total"] == 2


def test_recent_additions_newest_first_capped_at_ten() -> None:
    items = [wli(f"F{i}", 2020, date(2026, 1, i + 1)) for i in range(15)]
    result = _watchlist.build_overview(items)
    assert len(result["recent_additions"]) == 10
    dates = [r["added"] for r in result["recent_additions"]]
    assert dates == sorted(dates, reverse=True)
    # Newest added is 2026-01-15.
    assert dates[0] == "2026-01-15"


def test_oldest_pending_oldest_first_capped_at_five() -> None:
    items = [wli(f"F{i}", 2020, date(2026, 1, i + 1)) for i in range(8)]
    result = _watchlist.build_overview(items)
    assert len(result["oldest_pending"]) == 5
    dates = [r["added"] for r in result["oldest_pending"]]
    assert dates == sorted(dates)
    assert dates[0] == "2026-01-01"


def test_row_shape_includes_film_label_year_added_uri() -> None:
    items = [wli("Amélie", 2001, date(2026, 3, 15))]
    result = _watchlist.build_overview(items)
    row = result["recent_additions"][0]
    assert row["film"] == "Amélie (2001)"
    assert row["year"] == 2001
    assert row["added"] == "2026-03-15"
    assert row["uri"].endswith("/film/amélie/")


def test_row_label_without_year() -> None:
    items = [wli("Untitled", None, date(2026, 4, 1))]
    result = _watchlist.build_overview(items)
    assert result["recent_additions"][0]["film"] == "Untitled"
