"""Shared helpers for the JSON routers."""

from __future__ import annotations

from pathlib import Path

from alpha_core.config import AlphaSettings


def data_dir() -> Path:
    """The active store root — shared with the CLI, MCP server, and legacy Jinja pages."""
    return AlphaSettings().data_dir
