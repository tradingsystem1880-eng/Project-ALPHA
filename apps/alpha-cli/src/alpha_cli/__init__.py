"""Project ALPHA CLI package."""

from __future__ import annotations

__version__ = "0.0.0"

# The run-type subdirectories `alpha` writes manifests under — the single public source of truth
# (kept here, polars-free, so the MCP/web clients atop the DAG can import it cheaply). `alpha
# report`, the MCP reader, and the web run store all index these directories.
RUN_DIRS = ("runs", "portfolio", "cross_sectional", "optim", "propfirm", "forecast")

__all__ = ["RUN_DIRS", "__version__"]
