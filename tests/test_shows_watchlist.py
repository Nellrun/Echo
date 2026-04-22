from __future__ import annotations

from datetime import UTC, datetime

from echo.providers.shows import watchlist
from tests.conftest import trakt_movie, trakt_show, trakt_watchlist


def _ts(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


def test_empty_watchlist_is_zeroed() -> None:
    result = watchlist.build_overview([])
    assert result["total"] == 0
    assert result["by_media_type"] == {}
    assert result["recent_additions"] == []


def test_split_by_media_type_and_decade() -> None:
    items = [
        trakt_watchlist(trakt_show("Shogun", 2024, trakt_id=1), _ts(2024, 3, 10)),
        trakt_watchlist(trakt_movie("Dune: Part Two", 2024, trakt_id=2), _ts(2024, 3, 1)),
        trakt_watchlist(trakt_movie("Heat", 1995, trakt_id=3), _ts(2024, 2, 1)),
    ]
    result = watchlist.build_overview(items)
    assert result["total"] == 3
    assert result["by_media_type"] == {"show": 1, "movie": 2}
    assert result["by_release_decade"] == {"1990s": 1, "2020s": 2}


def test_recent_additions_newest_first_and_capped_at_ten() -> None:
    items = [
        trakt_watchlist(
            trakt_show(f"S{i}", trakt_id=i),
            _ts(2024, 1, i),
            listed_id=i,
        )
        for i in range(1, 15)
    ]
    result = watchlist.build_overview(items)
    # 14 items → recent_additions has 10, starting with the newest date.
    assert len(result["recent_additions"]) == 10
    assert result["recent_additions"][0]["added"] == "2024-01-14"
    assert result["oldest_pending"][0]["added"] == "2024-01-01"


def test_row_shape_carries_ids_and_type() -> None:
    items = [
        trakt_watchlist(
            trakt_show("Shogun", 2024, trakt_id=777),
            _ts(2024, 3, 10),
        )
    ]
    result = watchlist.build_overview(items)
    row = result["recent_additions"][0]
    assert row["title"] == "Shogun (2024)"
    assert row["media_type"] == "show"
    assert row["trakt_id"] == 777
