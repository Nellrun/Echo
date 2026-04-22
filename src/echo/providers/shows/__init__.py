"""
Shows provider — thin adapter over :mod:`my.trakt`.

Trakt tracks both movies and TV, but Letterboxd already covers the film side
in the ``films`` provider; this one is primarily about *shows* — hence the
name. We still surface movie events and watchlist items when they're in the
Trakt dump, so nothing gets silently dropped for users who log cinema
through Trakt instead of Letterboxd.

As elsewhere, the heavy lifting lives in pure-function aggregation modules
(:mod:`.summary`, :mod:`.taste`, :mod:`.watchlist`) so they're trivially
unit-testable without HPI being configured.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from echo.core.types import Event, Period
from echo.providers.shows import summary as _summary
from echo.providers.shows import taste as _taste
from echo.providers.shows import watchlist as _watchlist

if TYPE_CHECKING:
    from datetime import datetime

    from fastmcp import FastMCP
    from my.trakt.common import HistoryEntry, Rating, WatchListEntry

log = logging.getLogger(__name__)


def _naive(ts: datetime) -> datetime:
    """Strip tz so Period.contains (naive) stays comparable with Trakt (UTC-aware)."""
    return ts.replace(tzinfo=None) if ts.tzinfo is not None else ts


def _load_history() -> Iterator[HistoryEntry]:
    from my.trakt.all import history

    for item in history():
        if isinstance(item, Exception):
            log.debug("skipping broken history row: %s", item)
            continue
        yield item


def _load_ratings() -> Iterator[Rating]:
    from my.trakt.all import ratings

    for item in ratings():
        if isinstance(item, Exception):
            log.debug("skipping broken rating row: %s", item)
            continue
        yield item


def _load_watchlist() -> Iterator[WatchListEntry]:
    from my.trakt.all import watchlist

    for item in watchlist():
        if isinstance(item, Exception):
            log.debug("skipping broken watchlist row: %s", item)
            continue
        yield item


def _history_title(entry: HistoryEntry) -> str:
    """One-line label for a history event (movie title or ``Show S01E02 — Title``)."""
    from my.trakt.common import Movie

    data = entry.media_data
    if isinstance(data, Movie):
        return f"{data.title} ({data.year})" if data.year is not None else data.title
    # Episode
    sxe = f"S{data.season:02d}E{data.episode:02d}"
    if data.title:
        return f"{data.show.title} {sxe} — {data.title}"
    return f"{data.show.title} {sxe}"


def _history_payload(entry: HistoryEntry) -> dict[str, Any]:
    """Serialise a history entry into a JSON-safe dict for Events / query tools."""
    from my.trakt.common import Movie

    data = entry.media_data
    if isinstance(data, Movie):
        return {
            "media_type": "movie",
            "title": data.title,
            "year": data.year,
            "trakt_id": data.ids.trakt_id,
            "imdb_id": data.ids.imdb_id,
            "action": entry.action,
        }
    return {
        "media_type": "episode",
        "show": data.show.title,
        "show_year": data.show.year,
        "season": data.season,
        "episode": data.episode,
        "episode_title": data.title,
        "trakt_id": data.ids.trakt_id,
        "imdb_id": data.ids.imdb_id,
        "show_trakt_id": data.show.ids.trakt_id,
        "show_imdb_id": data.show.ids.imdb_id,
        "action": entry.action,
    }


def _watchlist_title(item: WatchListEntry) -> str:
    data = item.media_data
    return f"{data.title} ({data.year})" if data.year is not None else data.title


class ShowsProvider:
    name = "shows"

    def is_available(self) -> bool:
        try:
            from my.trakt import export

            return bool(export.inputs())
        except Exception:
            log.debug("shows provider unavailable", exc_info=True)
            return False

    def events(self, period: Period) -> Iterator[Event]:
        # History — one event per watch. Movie events coexist with episode
        # events; consumers filter by ``payload["media_type"]`` if they care.
        for entry in _load_history():
            ts = _naive(entry.watched_at)
            if not period.contains(ts):
                continue
            payload = _history_payload(entry)
            kind = "episode_watch" if payload["media_type"] == "episode" else "movie_watch"
            yield Event(
                timestamp=ts,
                source=self.name,
                kind=kind,
                title=_history_title(entry),
                payload=payload,
            )

        # Watchlist additions — one event per queued item.
        for item in _load_watchlist():
            ts = _naive(item.listed_at)
            if not period.contains(ts):
                continue
            yield Event(
                timestamp=ts,
                source=self.name,
                kind="watchlist_add",
                title=f"+ watchlist: {_watchlist_title(item)}",
                payload={
                    "media_type": item.media_type,
                    "title": item.media_data.title,
                    "year": item.media_data.year,
                    "trakt_id": item.media_data.ids.trakt_id,
                    "imdb_id": item.media_data.ids.imdb_id,
                },
            )

    def watched_summary(self, period: Period) -> dict[str, Any]:
        history = [
            e for e in _load_history() if period.contains(_naive(e.watched_at))
        ]
        return _summary.build(history, period=period)

    def taste_profile(self) -> dict[str, Any]:
        return _taste.build(list(_load_history()), list(_load_ratings()))

    def watchlist_overview(self) -> dict[str, Any]:
        return _watchlist.build_overview(list(_load_watchlist()))

    def history(self) -> list[HistoryEntry]:
        """All history rows. Materialised because query tools rescan it."""
        return list(_load_history())

    def ratings(self) -> list[Rating]:
        return list(_load_ratings())

    def watchlist(self) -> list[WatchListEntry]:
        return list(_load_watchlist())

    def register_tools(self, mcp: FastMCP) -> None:
        from echo.tools import show_tools

        show_tools.register(mcp, self)


__all__ = ["ShowsProvider"]
