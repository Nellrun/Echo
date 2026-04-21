"""
Registry of providers available to the server.

The registry is intentionally small — it's a list of instances plus a
helper that filters to the ones whose underlying ``my.*`` module is
configured. Cross-domain tools iterate this to gather events without
hard-coding source names.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator

from echo.core.types import Event, Period
from echo.providers.base import Provider

log = logging.getLogger(__name__)


class Registry:
    def __init__(self) -> None:
        self._providers: list[Provider] = []

    def register(self, provider: Provider) -> None:
        if any(p.name == provider.name for p in self._providers):
            raise ValueError(f"provider {provider.name!r} already registered")
        self._providers.append(provider)

    def all(self) -> list[Provider]:
        return list(self._providers)

    def available(self) -> list[Provider]:
        """Only providers whose ``is_available()`` reported ``True``."""
        ready: list[Provider] = []
        for p in self._providers:
            try:
                if p.is_available():
                    ready.append(p)
            except Exception:
                log.exception("provider %s failed is_available()", p.name)
        return ready

    def get(self, name: str) -> Provider | None:
        return next((p for p in self._providers if p.name == name), None)

    def iter_events(self, period: Period, *, sources: Iterable[str] | None = None) -> Iterator[Event]:
        """
        Yield events from every available provider inside ``period``.

        ``sources`` optionally narrows the set by name. Unknown names are
        silently ignored — useful for LLM-driven calls where a stale source
        list shouldn't surface as a hard error.
        """
        wanted = set(sources) if sources is not None else None
        for provider in self.available():
            if wanted is not None and provider.name not in wanted:
                continue
            try:
                yield from provider.events(period)
            except Exception:
                log.exception("provider %s failed to produce events", provider.name)


_default = Registry()


def default_registry() -> Registry:
    """The process-wide registry used by the MCP server."""
    return _default


__all__ = ["Registry", "default_registry"]
