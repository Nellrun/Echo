"""
Films provider — thin adapter over :mod:`my.letterboxd`.

The interesting work (aggregation) lives in :mod:`.summary` and :mod:`.taste`
as pure functions that accept iterables of ``Diary``/``Rating`` objects.
That keeps them trivially unit-testable without HPI being configured.

The provider itself is a thin adapter: it pulls from ``my.letterboxd.all``,
filters out ``Exception`` values (``Res[T] = T | Exception`` in HPI), and
hands the cleaned stream to the aggregation functions.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from echo.core.types import Event, Period
from echo.providers.films import summary as _summary
from echo.providers.films import taste as _taste
from echo.providers.films import watchlist as _watchlist

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from my.letterboxd.common import Diary, Rating, WatchlistItem

log = logging.getLogger(__name__)


def _diary_date(entry: Diary) -> date:
    """Prefer the actual watch date; fall back to the logged date for old entries."""
    return entry.watched_date or entry.logged_date


def _film_label(f) -> str:
    return f"{f.name} ({f.year})" if f.year is not None else f.name


def _load_diary() -> Iterator[Diary]:
    """Stream ``Diary`` entries, dropping ``Exception`` values with a log line."""
    from my.letterboxd.all import diary

    for item in diary():
        if isinstance(item, Exception):
            log.debug("skipping broken diary row: %s", item)
            continue
        yield item


def _load_ratings() -> Iterator[Rating]:
    from my.letterboxd.all import ratings

    for item in ratings():
        if isinstance(item, Exception):
            log.debug("skipping broken rating row: %s", item)
            continue
        yield item


def _load_watchlist() -> Iterator[WatchlistItem]:
    from my.letterboxd.all import watchlist

    for item in watchlist():
        if isinstance(item, Exception):
            log.debug("skipping broken watchlist row: %s", item)
            continue
        yield item


class FilmsProvider:
    name = "films"

    def is_available(self) -> bool:
        try:
            from my.letterboxd import export

            return bool(export.inputs())
        except Exception:
            log.debug("films provider unavailable", exc_info=True)
            return False

    def events(self, period: Period) -> Iterator[Event]:
        # Diary entries — one event per logged watch.
        for entry in _load_diary():
            when = _diary_date(entry)
            ts = datetime.combine(when, datetime.min.time())
            if not period.contains(ts):
                continue
            yield Event(
                timestamp=ts,
                source=self.name,
                kind="diary",
                title=_film_label(entry.film),
                payload={
                    "film": entry.film.name,
                    "year": entry.film.year,
                    "rating": entry.rating,
                    "rewatch": entry.rewatch,
                    "uri": entry.film.uri,
                    "review": entry.review,
                    "tags": list(entry.tags),
                },
            )

        # Watchlist additions — one event per item added to the watchlist.
        # Consumers filter by ``kind`` when they want diary-only views.
        for item in _load_watchlist():
            ts = datetime.combine(item.date, datetime.min.time())
            if not period.contains(ts):
                continue
            yield Event(
                timestamp=ts,
                source=self.name,
                kind="watchlist_add",
                title=f"+ watchlist: {_film_label(item.film)}",
                payload={
                    "film": item.film.name,
                    "year": item.film.year,
                    "uri": item.film.uri,
                },
            )

    def watched_summary(self, period: Period) -> dict[str, Any]:
        diary = [
            e
            for e in _load_diary()
            if period.contains(datetime.combine(_diary_date(e), datetime.min.time()))
        ]
        return _summary.build(diary, period=period)

    def taste_profile(self) -> dict[str, Any]:
        return _taste.build(list(_load_diary()), list(_load_ratings()))

    def watchlist_overview(self) -> dict[str, Any]:
        return _watchlist.build_overview(list(_load_watchlist()))

    def ratings(self) -> list[Rating]:
        """All current per-film ratings. Materialised because callers rescan it."""
        return list(_load_ratings())

    def watchlist(self) -> list[WatchlistItem]:
        """All watchlist items. Materialised because callers rescan it."""
        return list(_load_watchlist())

    def register_tools(self, mcp: FastMCP) -> None:
        # Actual @mcp.tool() decorators live in echo/tools/film_tools.py so
        # that tool wiring is not coupled to provider logic. The server
        # passes the mcp instance there directly.
        from echo.tools import film_tools

        film_tools.register(mcp, self)


__all__ = ["FilmsProvider"]
