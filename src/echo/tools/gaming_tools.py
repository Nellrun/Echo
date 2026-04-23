"""FastMCP tool wiring for the gaming provider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from echo.core.periods import parse_period

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from echo.providers.gaming import GamingProvider


def register(mcp: FastMCP, provider: GamingProvider) -> None:
    @mcp.tool()
    def gaming_play_summary(period: str = "last_month") -> dict[str, Any]:
        """
        Summarise PlayStation sessions in ``period``: total hours, top
        games by hours, platform mix, daily distribution.

        Data comes from ps-timetracker (friend-presence based, so sessions
        are wall-clock durations observed from outside — they can be
        shorter than true play time if the bot missed pings).

        ``period`` accepts ``all``, ``last_week|month|year``, ``YYYY``,
        ``YYYY-MM``, ``YYYY-Qn``, or ``YYYY-MM-DD..YYYY-MM-DD``.
        """
        return provider.play_summary(parse_period(period))

    @mcp.tool()
    def gaming_taste_profile() -> dict[str, Any]:
        """
        Classify games into core (steady hours long-term + recent) and
        flings (only in the last 30 days). Takes no period; windows are
        fixed by design. Ranked by hours played, not session count.
        """
        return provider.taste_profile()

    @mcp.tool()
    def gaming_library_overview() -> dict[str, Any]:
        """
        Summary of the ps-timetracker game library snapshot: total games,
        total hours across everything, platform breakdown, top 10 by
        hours, and the 10 most-recently-played titles.

        Unlike films' watchlist, there is no "queued" concept here —
        ps-timetracker only exposes games already seen, with aggregate
        stats and last-played time. For raw session rows use
        ``query_gaming_sessions``.
        """
        return provider.library_overview()


__all__ = ["register"]
