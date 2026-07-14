"""Project ALPHA CLI package."""

from __future__ import annotations

from typing import Final

__version__ = "1.0.0"

# Every run-type subdirectory the CLI writes under data_dir. This is the cross-app run
# registry: writers go through `_artifacts.run_dir(..., kind=...)` (which validates against
# it) and `alpha report`, the MCP read tools, and the web IDE search exactly these dirs.
# Kept here (not in _artifacts) so alpha_mcp can import it without paying for polars.
RUN_DIRS: Final[tuple[str, ...]] = (
    "runs",
    "portfolio",
    "cross_sectional",
    "optim",
    "propfirm",
    "forecast",
)
