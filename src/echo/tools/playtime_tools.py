"""FastMCP tool wiring for the playtime (gwm-stats) provider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from echo.core.periods import parse_period

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from echo.providers.playtime import PlaytimeProvider


def register(mcp: FastMCP, provider: PlaytimeProvider) -> None:
    @mcp.tool()
    def playtime_summary(period: str = "last_month") -> dict[str, Any]:
        """
        Cross-platform play summary for ``period``: total hours, top games
        by hours, and the split across both platforms (PS5/PS4/Switch/PC)
        and sources (psn/steam/nintendo), plus a daily distribution.

        Data comes from the gwm-stats aggregator, which spans PlayStation,
        Steam and Nintendo. For PSN-only friend-presence data use
        ``gaming_play_summary`` instead.

        ``period`` accepts ``all``, ``last_week|month|year``, ``YYYY``,
        ``YYYY-MM``, ``YYYY-Qn``, or ``YYYY-MM-DD..YYYY-MM-DD``.
        """
        return provider.play_summary(parse_period(period))

    @mcp.tool()
    def playtime_taste_profile() -> dict[str, Any]:
        """
        Classify games into core (steady hours long-term + recent) and
        flings (only in the last 30 days), across every platform. Takes no
        period; windows are fixed by design. Ranked by hours played, not
        session count.
        """
        return provider.taste_profile()

    @mcp.tool()
    def playtime_overview() -> dict[str, Any]:
        """
        All-time cross-platform picture from the aggregator's own
        precomputed totals: total hours/sessions/games, average and longest
        session, first/last played, trophies earned, top 10 games by hours,
        and a per-source breakdown (psn/steam/nintendo).

        This is the one-call "where do I stand overall" view. For a specific
        window use ``playtime_summary``; for raw rows use
        ``query_playtime_sessions``.
        """
        return provider.overview()

    @mcp.tool()
    def playtime_trophy_summary(period: str = "all") -> dict[str, Any]:
        """
        Trophy/achievement digest for ``period``: total earned, counts by
        type (platinum/gold/silver/bronze) and by source, the games with the
        most trophies, the rarest earned (lowest global rarity %), and the
        most recent.

        Trophies come from PSN via gwm-stats; Steam/Nintendo rows appear if
        the aggregator has them. ``period`` accepts the same shapes as
        ``playtime_summary``; defaults to ``all``.
        """
        return provider.trophy_summary(parse_period(period))


__all__ = ["register"]
