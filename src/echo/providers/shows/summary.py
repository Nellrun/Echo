"""Pure aggregations for ``shows.watched_summary``."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from echo.core.aggregations import daily_distribution, top_n

if TYPE_CHECKING:
    from my.trakt.common import HistoryEntry

    from echo.core.types import Period


def _show_title(entry: HistoryEntry) -> str | None:
    from my.trakt.common import Episode

    if isinstance(entry.media_data, Episode):
        data = entry.media_data
        return (
            f"{data.show.title} ({data.show.year})"
            if data.show.year is not None
            else data.show.title
        )
    return None


def _movie_label(entry: HistoryEntry) -> str | None:
    from my.trakt.common import Movie

    if isinstance(entry.media_data, Movie):
        data = entry.media_data
        return f"{data.title} ({data.year})" if data.year is not None else data.title
    return None


def build(entries: Iterable[HistoryEntry], *, period: Period) -> dict[str, Any]:
    """
    Aggregate a pre-filtered iterable of ``HistoryEntry`` rows into a summary.

    ``entries`` must already be restricted to ``period`` — filtering happens
    in the provider, mirroring the films/music summary contract.
    """
    entries = list(entries)
    episodes = [e for e in entries if e.media_type == "episode"]
    movies = [e for e in entries if e.media_type == "movie"]

    # "Most watched" for shows is *episodes per show* — movies don't
    # typically repeat enough to produce a useful ranking here, so we keep a
    # separate small list of rewatched films.
    show_counter: Counter[str] = Counter()
    unique_episode_keys: set[tuple[int, int, int]] = set()
    for e in episodes:
        label = _show_title(e)
        if label:
            show_counter[label] += 1
        # Dedup key: show trakt id + season + episode. Lets us separate
        # "distinct episodes seen" from "plays" (rewatches count as plays).
        from my.trakt.common import Episode

        if isinstance(e.media_data, Episode):
            unique_episode_keys.add(
                (
                    e.media_data.show.ids.trakt_id,
                    e.media_data.season,
                    e.media_data.episode,
                )
            )

    movie_counter: Counter[str] = Counter()
    for e in movies:
        label = _movie_label(e)
        if label:
            movie_counter[label] += 1

    return {
        "period": period.label or "custom",
        "total_plays": len(entries),
        "episodes_played": len(episodes),
        "movies_played": len(movies),
        "distinct_shows": len(show_counter),
        "distinct_episodes": len(unique_episode_keys),
        "top_shows": top_n(
            (_show_title(e) for e in episodes if _show_title(e)),
            n=10,
            key="episodes",
        ),
        "most_watched_movies": [
            {"value": title, "plays": plays}
            for title, plays in movie_counter.most_common(5)
            if plays > 1
        ],
        "daily_distribution": daily_distribution(e.watched_at for e in entries),
    }


__all__ = ["build"]
