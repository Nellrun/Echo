"""FastMCP tool wiring for cross-domain tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from echo.core.periods import parse_period
from echo.providers.cross import timeline

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from echo.core.registry import Registry


def register(mcp: FastMCP, registry: Registry) -> None:
    @mcp.tool()
    def cross_activity_timeline(
        period: str = "last_week",
        sources: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Unified chronological feed of events from every available provider.

        Dense sources (music scrobbles) are collapsed to one daily summary
        entry; film and other low-cardinality sources come through as-is.
        The response is capped at 500 entries — narrow ``period`` or use
        ``sources`` to filter if you hit the cap.

        ``sources`` restricts which providers contribute (e.g. ``["films"]``);
        unknown names are ignored.
        """
        return timeline.build(parse_period(period), registry=registry, sources=sources)


__all__ = ["register"]
