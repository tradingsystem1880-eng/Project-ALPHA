"""Private, fixed-case MCP facade; all operations use the supported CLI seam."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ContentBlock, Tool

from alpha_mcp._invoke import run_json


class _InvestigationMCP(FastMCP):
    async def list_tools(self) -> list[Tool]:
        result = await super().list_tools()
        for tool in result:
            tool.inputSchema["additionalProperties"] = False
        return result

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> Sequence[ContentBlock] | dict[str, Any]:
        if arguments:
            raise ValueError("Investigation tools accept no arguments")
        return await super().call_tool(name, arguments)


def build_server(case: Path) -> FastMCP:
    case = case.resolve(strict=True)
    server = _InvestigationMCP("alpha_investigation")

    def call(action: str) -> dict[str, Any]:
        result = run_json(
            ["research", "diagnostic", "investigation-tool", str(case), action],
            data_dir=case,
        )
        if not isinstance(result, dict):
            raise RuntimeError("Investigation CLI returned a non-object")
        return result

    @server.tool()
    def inspect_execution() -> dict[str, Any]:
        """Verify this case's execution integrity before interpreting performance."""
        return call("inspect_execution")

    @server.tool()
    def inspect_losses() -> dict[str, Any]:
        """Measure verified drawdown episodes; requires inspect_execution first."""
        return call("inspect_losses")

    @server.tool()
    def suggest_followups() -> dict[str, Any]:
        """Read grounded starting questions, not completed experiments or causal findings."""
        return call("suggest_followups")

    return server


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m alpha_mcp.investigation_server CASE_DIRECTORY")
    build_server(Path(sys.argv[1])).run(transport="stdio")


if __name__ == "__main__":
    main()
