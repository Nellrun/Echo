"""
Provider protocol — the single extension point that every data source plugs into.

A provider wraps one logical source (Letterboxd, Last.fm, Trakt, ...). It has
two jobs:

1. Expose its own **insight tools** via :meth:`register_tools` (things like
   ``films.watched_summary``, ``music.taste_profile``).
2. Emit a canonical stream of :class:`~echo.core.types.Event` objects via
   :meth:`events` so that cross-domain tools can mix sources on a single
   timeline without knowing about specific ones.

The :meth:`is_available` check lets the server degrade softly when the user
hasn't configured the underlying ``my.<source>`` module — typically by
catching ``my.core.NotFoundError`` or similar, without importing anything
expensive at module load time.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from echo.core.types import Event, Period

if TYPE_CHECKING:
    from fastmcp import FastMCP


@runtime_checkable
class Provider(Protocol):
    name: str
    """Short lowercase identifier used as the MCP tool namespace (e.g. ``"films"``)."""

    def is_available(self) -> bool:
        """Return ``True`` if the underlying ``my.<source>`` module is configured."""

    def events(self, period: Period) -> Iterator[Event]:
        """
        Stream every event from this source that falls inside ``period``.

        Implementations are expected to skip/log ``Exception`` items from
        ``my.*`` (``Res[T]`` = ``T | Exception``) rather than abort — partial
        data is more useful than no data.
        """

    def register_tools(self, mcp: FastMCP) -> None:
        """Register the provider's domain-specific insight tools with FastMCP."""


__all__ = ["Provider"]
