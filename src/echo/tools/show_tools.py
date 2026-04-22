"""FastMCP tool wiring for the shows (Trakt) provider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from echo.core.periods import parse_period

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from echo.providers.shows import ShowsProvider


def register(mcp: FastMCP, provider: ShowsProvider) -> None:
    @mcp.tool()
    def shows_watched_summary(period: str = "last_month") -> dict[str, Any]:
        """
        Summarise episodes and films watched on Trakt during ``period``.

        ``period`` accepts ``all``, ``last_week|month|year``, ``YYYY``,
        ``YYYY-MM``, ``YYYY-Qn``, or ``YYYY-MM-DD..YYYY-MM-DD``.

        Counts plays (so rewatches bump the total), exposes ``distinct_shows``
        / ``distinct_episodes`` for unique-coverage questions, and surfaces
        the ten most-watched shows plus films replayed more than once.
        """
        return provider.watched_summary(parse_period(period))

    @mcp.tool()
    def shows_taste_profile() -> dict[str, Any]:
        """
        All-time taste signals from the Trakt export: most-watched shows by
        episode count, most-rewatched films, rating distribution (1..10),
        and favourite release decades weighted by plays.

        Genre-level preferences are not available from the export — see
        ``coverage_note`` in the response.
        """
        return provider.taste_profile()

    @mcp.tool()
    def shows_watchlist_overview() -> dict[str, Any]:
        """
        Summary of the Trakt watchlist: total count, split by ``movie`` /
        ``show``, distribution by release decade, the 10 most recent
        additions, and the 5 entries that have been queued longest.

        For a raw list, use ``query_trakt_watchlist``.
        """
        return provider.watchlist_overview()


__all__ = ["register"]
