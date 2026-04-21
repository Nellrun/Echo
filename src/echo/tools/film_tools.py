"""FastMCP tool wiring for the films provider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from echo.core.periods import parse_period

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from echo.providers.films import FilmsProvider


def register(mcp: FastMCP, provider: FilmsProvider) -> None:
    @mcp.tool()
    def films_watched_summary(period: str = "last_month") -> dict[str, Any]:
        """
        Summarise films watched in ``period``.

        ``period`` accepts ``all``, ``last_week|month|year``, ``YYYY``,
        ``YYYY-MM``, ``YYYY-Qn``, or ``YYYY-MM-DD..YYYY-MM-DD``.
        """
        return provider.watched_summary(parse_period(period))

    @mcp.tool()
    def films_taste_profile() -> dict[str, Any]:
        """
        Long-term film taste signals: favourite decades, most-rewatched
        films, overall rating distribution.

        Director-level preferences and Letterboxd-average comparisons are
        not available from the export alone.
        """
        return provider.taste_profile()

    @mcp.tool()
    def films_watchlist_overview() -> dict[str, Any]:
        """
        Summary of the Letterboxd watchlist: total count, distribution
        by release decade, the 10 most recent additions, and the 5
        entries that have been sitting in the queue longest.

        For a raw list, use ``query.watchlist``.
        """
        return provider.watchlist_overview()


__all__ = ["register"]
