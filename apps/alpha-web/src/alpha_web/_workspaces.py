"""Server-side store for named workspace layouts (``data_dir/web/workspaces/<slug>.json``).

A workspace bundles a Dockview ``toJSON()`` layout + the linked symbol/date context under a
slugified name. This is UI state — plain JSON, not a byte-stable run manifest — so the determinism
rules don't apply; the ``updated`` timestamp is fine.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from alpha_core import DataError

_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def _dir(data_dir: Path) -> Path:
    return data_dir / "web" / "workspaces"


def slugify(name: str) -> str:
    """A filesystem-safe slug from a workspace name (fails loud on an empty result)."""
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    if not slug:
        raise DataError(f"workspace name {name!r} has no usable characters")
    return slug


def _path(data_dir: Path, slug: str) -> Path:
    if not slug or "/" in slug or "\\" in slug or ".." in slug:
        raise DataError(f"invalid workspace slug {slug!r}")
    return _dir(data_dir) / f"{slug}.json"


def list_workspaces(*, data_dir: Path) -> list[dict[str, Any]]:
    """Every saved workspace as ``{slug, name, updated}``, sorted by slug."""
    base = _dir(data_dir)
    if not base.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(base.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        out.append(
            {"slug": path.stem, "name": doc.get("name", path.stem), "updated": doc.get("updated")}
        )
    return out


def get_workspace(slug: str, *, data_dir: Path) -> dict[str, Any]:
    """The full workspace document (name + linked_context + dockview layout)."""
    path = _path(data_dir, slug)
    if not path.exists():
        raise FileNotFoundError(f"no workspace {slug!r}")
    result: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return result


def save_workspace(slug: str, doc: dict[str, Any], *, data_dir: Path) -> dict[str, Any]:
    """Write a workspace document; returns its ``{slug, name}``."""
    path = _path(data_dir, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
    return {"slug": slug, "name": doc.get("name", slug)}


def delete_workspace(slug: str, *, data_dir: Path) -> None:
    """Remove a workspace (no-op if already gone)."""
    path = _path(data_dir, slug)
    path.unlink(missing_ok=True)
