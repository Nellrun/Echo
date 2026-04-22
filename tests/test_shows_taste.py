from __future__ import annotations

from datetime import UTC, datetime

from echo.providers.shows import taste
from tests.conftest import (
    trakt_episode,
    trakt_history,
    trakt_movie,
    trakt_rating,
    trakt_show,
)


def _ts(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


def test_empty_inputs_return_none_averages() -> None:
    result = taste.build([], [])
    assert result["total_plays"] == 0
    assert result["avg_rating"] is None
    assert result["most_watched_shows"] == []
    assert result["most_rewatched_movies"] == []


def test_most_watched_shows_ranks_by_episode_plays() -> None:
    a = trakt_show("A", year=2010, trakt_id=1)
    b = trakt_show("B", year=2015, trakt_id=2)
    history = [
        trakt_history(_ts(2024, 1, 1), trakt_episode(a, 1, 1, trakt_id=10)),
        trakt_history(_ts(2024, 1, 2), trakt_episode(a, 1, 2, trakt_id=11)),
        trakt_history(_ts(2024, 1, 3), trakt_episode(a, 1, 3, trakt_id=12)),
        trakt_history(_ts(2024, 1, 4), trakt_episode(b, 1, 1, trakt_id=20)),
    ]
    result = taste.build(history, [])
    assert result["most_watched_shows"][0] == {"show": "A (2010)", "episodes": 3}
    assert result["most_watched_shows"][1] == {"show": "B (2015)", "episodes": 1}


def test_most_rewatched_movies_needs_more_than_one_play() -> None:
    dune = trakt_movie("Dune", year=2021, trakt_id=1)
    matrix = trakt_movie("Matrix", year=1999, trakt_id=2)
    history = [
        trakt_history(_ts(2024, 1, 1), dune, history_id=1),
        trakt_history(_ts(2024, 2, 1), dune, history_id=2),  # rewatch
        trakt_history(_ts(2024, 3, 1), matrix, history_id=3),  # once — excluded
    ]
    result = taste.build(history, [])
    assert [m["movie"] for m in result["most_rewatched_movies"]] == ["Dune (2021)"]


def test_favourite_decades_applies_minimum_sample() -> None:
    # Exactly 5 plays in the 2010s, 4 in the 2020s. Only the 2010s passes
    # the MIN_PLAYS_PER_DECADE threshold.
    a = trakt_show("A", year=2015, trakt_id=1)
    b = trakt_show("B", year=2022, trakt_id=2)
    history = [
        trakt_history(_ts(2024, 1, i), trakt_episode(a, 1, i, trakt_id=10 + i))
        for i in range(1, 6)
    ] + [
        trakt_history(_ts(2024, 2, i), trakt_episode(b, 1, i, trakt_id=20 + i))
        for i in range(1, 5)
    ]
    result = taste.build(history, [])
    decades = [d["decade"] for d in result["favourite_decades"]]
    assert "2010s" in decades
    assert "2020s" not in decades


def test_rating_distribution_uses_integer_buckets() -> None:
    bb = trakt_show("BB", trakt_id=1)
    ratings = [
        trakt_rating(bb, 10),
        trakt_rating(bb, 10),
        trakt_rating(bb, 9),
    ]
    result = taste.build([], ratings)
    # step=1.0 keeps each integer as its own bucket.
    assert result["rating_distribution"] == {"9.0": 1, "10.0": 2}
    assert result["avg_rating"] == (10 + 10 + 9) / 3
