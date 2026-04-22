"""
FastMCP bootstrap.

Responsibilities:

* Construct the :class:`FastMCP` instance.
* Register every configured provider with the process-wide registry.
* Wire each provider's insight tools plus the cross-domain and query tools.
* Run the MCP stdio loop.
"""

from __future__ import annotations

import logging
import os

from echo.core.registry import default_registry
from echo.providers.films import FilmsProvider
from echo.providers.music import MusicProvider
from echo.providers.shows import ShowsProvider
from echo.tools import cross_tools, query_tools

log = logging.getLogger(__name__)


def _configure_logging() -> None:
    level = os.environ.get("ECHO_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def build_server() -> FastMCP:  # noqa: F821 — typing-only forward ref
    """
    Build a fully-wired FastMCP instance.

    Split from :func:`main` so tests (and future HTTP transports) can hold
    the server object without running the stdio loop.
    """
    from fastmcp import FastMCP

    mcp = FastMCP("echo")
    registry = default_registry()

    # Providers. ``is_available`` gates whether the provider's domain
    # tools are registered — tools for an unconfigured source would only
    # surface confusing errors when called.
    for provider in (FilmsProvider(), MusicProvider(), ShowsProvider()):
        try:
            available = provider.is_available()
        except Exception:
            log.exception("provider %s failed is_available()", provider.name)
            continue

        registry.register(provider)
        if available:
            provider.register_tools(mcp)
            log.info("registered provider %s", provider.name)
        else:
            log.warning(
                "provider %s installed but not configured — skipping tool registration",
                provider.name,
            )

    # Cross-domain and query tools always get registered: they degrade
    # gracefully when a specific source is missing.
    cross_tools.register(mcp, registry)
    query_tools.register(mcp, registry)
    return mcp


def main() -> None:
    _configure_logging()
    build_server().run()


if __name__ == "__main__":
    main()
