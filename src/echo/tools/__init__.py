"""
FastMCP tool declarations.

Each module exports a ``register(mcp, provider)`` (or ``register(mcp,
registry)``) callable that attaches tools to a FastMCP instance. Keeping
the decorators here — separate from provider logic — means the providers
remain importable and testable without FastMCP installed.
"""
