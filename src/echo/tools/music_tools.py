"""FastMCP tool wiring for the music provider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from echo.core.periods import parse_period

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from echo.providers.music import MusicProvider


def register(mcp: FastMCP, provider: MusicProvider) -> None:
    @mcp.tool()
    def music_listening_summary(period: str = "last_month") -> dict[str, Any]:
        """
        Summarise listening in ``period``: totals, top artists/tracks,
        daily distribution.

        ``period`` accepts ``all``, ``last_week|month|year``, ``YYYY``,
        ``YYYY-MM``, ``YYYY-Qn``, or ``YYYY-MM-DD..YYYY-MM-DD``.
        """
        return provider.listening_summary(parse_period(period))

    @mcp.tool()
    def music_taste_profile() -> dict[str, Any]:
        """
        Classify artists into core (consistent long-term + recent) and
        flings (only in the last 30 days). Takes no period; windows are
        fixed by design.
        """
        return provider.taste_profile()


__all__ = ["register"]
