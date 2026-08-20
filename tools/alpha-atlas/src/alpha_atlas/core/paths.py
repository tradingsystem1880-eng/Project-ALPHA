"""One authority for repo-root discovery and generated-artifact locations.

The generator (writer), the backend (reader), and the test suite previously
each derived these independently (three different `parents[N]` counts, two
path-literal copies) — a silent-drift hazard when a file moves.
"""

from __future__ import annotations

from pathlib import Path

from alpha_atlas.core.model import AtlasError

GRAPH_PATH = "architecture/atlas/generated/graph.json"
INPUTS_PATH = "architecture/atlas/generated/inputs.json"
UNKNOWNS_PATH = "architecture/atlas/generated/views/unknowns.json"


def find_repo_root(start: Path) -> Path:
    """Walk up from `start` to the ALPHA repo root (CLAUDE.md sentinel); fail loud."""
    for candidate in (start, *start.resolve().parents):
        if (candidate / "CLAUDE.md").is_file():
            return candidate
    raise AtlasError(f"cannot locate the ALPHA repo root above {start}")
