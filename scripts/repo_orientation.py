"""Small source-only adapter to the shared Atlas developer index; no viewer required."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any


def orientation(root: Path, *, component: str | None = None) -> dict[str, Any]:
    # Atlas remains an isolated developer tool, not a runtime package dependency.
    source = str(root / "tools/alpha-atlas/src")
    sys.path.insert(0, source)
    try:
        index = importlib.import_module("alpha_atlas.developer_index")
        result: dict[str, Any] = index.developer_index(root, component=component)
    finally:
        sys.path.remove(source)
    if component is None and len(json.dumps(result).encode("utf-8")) > 6_000:
        raise ValueError("orientation exceeds 6 KB; narrow the default summary")
    return result


def render_orientation(payload: dict[str, Any]) -> str:
    rows = ["Repository orientation (source index; authority: none)"]
    rows.extend(
        f"  {item['id']}: {item['path']} ({item['modules']} modules)"
        for item in payload["components"]
    )
    rows.append("Documents: " + ", ".join(payload["documents"]))
    rows.extend(payload["commands"].values())
    rows.extend(f"  {item['id']}: {item['path']}" for item in payload.get("modules", []))
    return "\n".join(rows)
