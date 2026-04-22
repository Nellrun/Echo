from __future__ import annotations

from datetime import UTC, datetime

from echo.core.periods import parse_period
from echo.providers.shows import summary
from tests.conftest import trakt_episode, trakt_history, trakt_movie, trakt_show


def _ts(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


def test_empty_history_gives_zero_counts() -> None:
    result = summary.build([], period=parse_period("2026-02"))
    assert result["total_plays"] == 0
    assert result["episodes_played"] == 0
    assert result["movies_played"] == 0
    assert result["top_shows"] == []


def test_top_shows_counts_episode_plays() -> None:
    bb = trakt_show("Breaking Bad", year=2008, trakt_id=1)
    tw = trakt_show("Twin Peaks", year=1990, trakt_id=2)
    history = [
        trakt_history(_ts(2026, 2, 1), trakt_episode(bb, 1, 1, trakt_id=10)),
        trakt_history(_ts(2026, 2, 2), trakt_episode(bb, 1, 2, trakt_id=11)),
        trakt_history(_ts(2026, 2, 3), trakt_episode(tw, 1, 1, trakt_id=20)),
    ]
    result = summary.build(history, period=parse_period("2026-02"))
    assert result["episodes_played"] == 3
    assert result["distinct_shows"] == 2
    top = {r["value"]: r["episodes"] for r in result["top_shows"]}
    assert top["Breaking Bad (2008)"] == 2
    assert top["Twin Peaks (1990)"] == 1


def test_distinct_episodes_dedupes_rewatches() -> None:
    bb = trakt_show("BB", trakt_id=1)
    ep = trakt_episode(bb, 1, 1, trakt_id=10)
    history = [
        trakt_history(_ts(2026, 2, 1), ep, history_id=1),
        trakt_history(_ts(2026, 2, 8), ep, history_id=2),  # rewatch
    ]
    result = summary.build(history, period=parse_period("2026-02"))
    assert result["episodes_played"] == 2
    assert result["distinct_episodes"] == 1


def test_most_watched_movies_only_includes_repeats() -> None:
    dune = trakt_movie("Dune", year=2021, trakt_id=501)
    parasite = trakt_movie("Parasite", year=2019, trakt_id=502)
    history = [
        trakt_history(_ts(2026, 2, 1), dune, history_id=1),
        trakt_history(_ts(2026, 2, 20), dune, history_id=2),  # rewatch
        trakt_history(_ts(2026, 2, 5), parasite, history_id=3),  # once — excluded
    ]
    result = summary.build(history, period=parse_period("2026-02"))
    assert result["movies_played"] == 3
    assert [m["value"] for m in result["most_watched_movies"]] == ["Dune (2021)"]


def test_daily_distribution_uses_watched_at_date() -> None:
    bb = trakt_show("BB")
    history = [
        trakt_history(_ts(2026, 2, 5), trakt_episode(bb, 1, 1, trakt_id=1)),
        trakt_history(_ts(2026, 2, 5), trakt_episode(bb, 1, 2, trakt_id=2)),
        trakt_history(_ts(2026, 2, 10), trakt_episode(bb, 1, 3, trakt_id=3)),
    ]
    result = summary.build(history, period=parse_period("2026-02"))
    assert result["daily_distribution"] == {"2026-02-05": 2, "2026-02-10": 1}


def test_period_label_echoed() -> None:
    result = summary.build([], period=parse_period("2026-Q1"))
    assert result["period"] == "2026-Q1"
