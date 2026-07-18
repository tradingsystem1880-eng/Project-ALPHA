"""Project ALPHA MCP server: drive the `alpha` research CLI conversationally.

A thin, purely-additive stdio MCP server that shells out to the installed ``alpha`` CLI and
returns the byte-stable manifests it writes. It composes nothing itself — the CLI is the
contract — so it sits at the very top of the architecture DAG (nothing imports it).
"""

from __future__ import annotations

from importlib.metadata import version

__version__ = version("alpha-mcp")
