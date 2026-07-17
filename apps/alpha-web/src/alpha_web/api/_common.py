"""Shared helpers for the JSON routers."""

from __future__ import annotations

from pathlib import Path

from alpha_core.config import AlphaSettings


def data_dir() -> Path:
    """The active store root — shared with the CLI and the MCP server."""
    return AlphaSettings().data_dir
