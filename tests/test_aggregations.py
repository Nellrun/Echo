from __future__ import annotations

from datetime import date, datetime

from echo.core.aggregations import (
    average,
    daily_distribution,
    rating_distribution,
    top_n,
)


def test_top_n_returns_n_most_common() -> None:
    result = top_n(["a", "b", "a", "c", "a", "b"], n=2)
    assert result == [{"value": "a", "count": 3}, {"value": "b", "count": 2}]


def test_top_n_returns_fewer_when_not_enough_distinct() -> None:
    assert top_n(["a", "a"], n=5) == [{"value": "a", "count": 2}]


def test_top_n_custom_key() -> None:
    result = top_n(["x"], n=1, key="plays")
    assert result == [{"value": "x", "plays": 1}]


def test_daily_distribution_sorts_and_counts() -> None:
    moments = [
        datetime(2026, 1, 2, 10),
        datetime(2026, 1, 2, 20),
        datetime(2026, 1, 1, 9),
        date(2026, 1, 3),
    ]
    assert daily_distribution(moments) == {
        "2026-01-01": 1,
        "2026-01-02": 2,
        "2026-01-03": 1,
    }


def test_rating_distribution_groups_by_half_steps_and_unrated() -> None:
    result = rating_distribution([3.5, 3.5, 4.0, None, 5.0, None])
    assert result["3.5"] == 2
    assert result["4.0"] == 1
    assert result["5.0"] == 1
    assert result["unrated"] == 2


def test_rating_distribution_formats_integers_with_one_decimal() -> None:
    # Without the format, a user with mixed int/float ratings would get
    # both "3" and "3.0" as separate buckets.
    result = rating_distribution([3, 3.0, 3.5])
    assert set(result.keys()) == {"3.0", "3.5"}
    assert result["3.0"] == 2


def test_rating_distribution_snaps_noisy_floats() -> None:
    assert rating_distribution([3.4999999])["3.5"] == 1


def test_average_empty_is_none() -> None:
    assert average([]) is None


def test_average_basic() -> None:
    assert average([1.0, 2.0, 3.0]) == 2.0
