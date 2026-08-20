"""Read-only Atlas server: graph, node projections, bounded file excerpts, SPA.

Loopback only. No write endpoints exist and the server never subprocesses
anything — generation is a separate explicit CLI step. Excerpts are jailed to
the repository root with a denylist for secrets, data stores, harness state,
and the hidden holdout tests.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

GRAPH_REL = "architecture/atlas/generated/graph.json"
INPUTS_REL = "architecture/atlas/generated/inputs.json"

EXCERPT_MAX_LINES = 400

_DENY_PREFIXES = ("data/", ".claude/", ".codex/", ".git/", "tests/holdout/", ".quantpad/")
_DENY_BASENAME_PREFIXES = (".env",)
_DENY_SUBSTRINGS = (".sqlite3",)


def _default_root() -> Path:
    root = Path(__file__).resolve().parents[5]
    if not (root / "CLAUDE.md").is_file():
        raise RuntimeError(f"cannot locate the ALPHA repo root from {__file__}")
    return root


def _load_graph(root: Path) -> dict[str, Any]:
    graph_path = root / GRAPH_REL
    if not graph_path.is_file():
        raise HTTPException(
            status_code=503,
            detail="atlas graph not generated; run: "
            "cd tools/alpha-atlas && uv run python -m alpha_atlas.generate",
        )
    payload: dict[str, Any] = json.loads(graph_path.read_text(encoding="utf-8"))
    return payload


def _jailed_path(root: Path, rel: str) -> Path:
    if rel.startswith(("/", "~")) or "\\" in rel:
        raise HTTPException(status_code=400, detail="path must be repo-relative")
    resolved_root = root.resolve()
    candidate = (resolved_root / rel).resolve()
    if not candidate.is_relative_to(resolved_root):
        raise HTTPException(status_code=403, detail="path escapes the repository root")
    normalized = candidate.relative_to(resolved_root).as_posix()
    basename = normalized.rsplit("/", 1)[-1]
    if (
        normalized.startswith(_DENY_PREFIXES)
        or basename.startswith(_DENY_BASENAME_PREFIXES)
        or any(marker in normalized for marker in _DENY_SUBSTRINGS)
    ):
        raise HTTPException(status_code=403, detail=f"path is denied: {normalized}")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail=f"no such file: {normalized}")
    return candidate


def create_app(root: Path | None = None) -> FastAPI:
    repo_root = root if root is not None else _default_root()
    app = FastAPI(title="alpha-atlas", docs_url=None, redoc_url=None)

    @app.get("/api/meta")
    def meta() -> dict[str, Any]:
        graph = _load_graph(repo_root)
        inputs = json.loads((repo_root / INPUTS_REL).read_text(encoding="utf-8"))
        stale = False
        for rel, digest in inputs["files"].items():
            path = repo_root / rel
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                stale = True
                break
        return {
            "schema_version": graph["schema_version"],
            "inputs_hash": graph["inputs_hash"],
            "stale": stale,
            "node_count": graph["stats"]["node_count"],
            "edge_count": graph["stats"]["edge_count"],
        }

    @app.get("/api/graph")
    def graph() -> JSONResponse:
        return JSONResponse(_load_graph(repo_root))

    @app.get("/api/node/{node_id:path}")
    def node(node_id: str) -> dict[str, Any]:
        payload = _load_graph(repo_root)
        found = next((n for n in payload["nodes"] if n["id"] == node_id), None)
        if found is None:
            raise HTTPException(status_code=404, detail=f"no such node: {node_id}")
        incident = [e for e in payload["edges"] if node_id in (e["source"], e["target"])]
        neighbor_ids = {e["source"] for e in incident} | {e["target"] for e in incident}
        neighbor_ids.discard(node_id)
        labels = {
            n["id"]: {"label": n["label"], "kind": n["kind"], "level": n["evidence"]["level"]}
            for n in payload["nodes"]
            if n["id"] in neighbor_ids
        }
        return {"node": found, "edges": incident, "neighbors": labels}

    @app.get("/api/excerpt")
    def excerpt(path: str, start: int = 1, end: int | None = None) -> dict[str, Any]:
        target = _jailed_path(repo_root, path)
        raw = target.read_bytes()
        if b"\x00" in raw[:8192]:
            raise HTTPException(status_code=415, detail="binary file")
        lines = raw.decode("utf-8", errors="replace").splitlines()
        first = max(start, 1)
        last = min(end if end is not None else first + EXCERPT_MAX_LINES - 1, len(lines))
        last = min(last, first + EXCERPT_MAX_LINES - 1)
        return {
            "path": path,
            "start": first,
            "end": last,
            "total_lines": len(lines),
            "lines": lines[first - 1 : last],
        }

    dist = repo_root / "tools/alpha-atlas/frontend/dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="spa")
    else:

        @app.get("/")
        def spa_missing() -> JSONResponse:
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "atlas SPA not built; run: "
                    "cd tools/alpha-atlas/frontend && npm install && npm run build"
                },
            )

    return app


def main() -> None:
    port_raw = os.environ.get("ALPHA_ATLAS_PORT", "8803")
    try:
        port = int(port_raw)
    except ValueError as exc:
        raise SystemExit(f"invalid ALPHA_ATLAS_PORT: {port_raw!r}") from exc
    uvicorn.run(create_app(), host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
