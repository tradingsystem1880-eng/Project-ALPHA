"""Atlas generation pipeline: extractors -> merge -> validate -> canonical outputs.

Usage:
    uv run python -m alpha_atlas.generate            # write outputs
    uv run python -m alpha_atlas.generate --check    # verify committed outputs are fresh

Determinism contract: outputs are sorted, timestamp-free, and keyed by
`inputs_hash` — a sha256 over generated/inputs.json, which records the exact
repository files the extractors read. Generated outputs are never inputs, so
regeneration can never invalidate itself.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

from alpha_atlas.core.evidence import resolve_levels
from alpha_atlas.core.mermaid import emit_docs
from alpha_atlas.core.model import (
    AtlasError,
    Fragment,
    dumps_canonical,
    dumps_compact,
    graph_payload,
    merge_fragments,
    validate_graph,
)
from alpha_atlas.core.paths import GRAPH_PATH, INPUTS_PATH, UNKNOWNS_PATH, find_repo_root
from alpha_atlas.generators import (
    api_routes,
    cli_tree,
    components,
    docs_scan,
    frontend_scan,
    importlinter,
    mcp_tools,
    python_modules,
    tests_map,
    workflow,
)

_FORBIDDEN_INPUT_PREFIXES = ("architecture/atlas/generated/", "docs/atlas/")


def build_outputs(root: Path) -> dict[str, str]:
    """Run the full pipeline in memory; returns {repo-relative path: file content}."""
    fragments: list[Fragment] = []
    inputs: dict[str, str] = {}

    def add(result: tuple[Fragment, dict[str, str]]) -> Fragment:
        fragment, read = result
        fragments.append(fragment)
        for path, digest in read.items():
            if path.startswith(_FORBIDDEN_INPUT_PREFIXES):
                raise AtlasError(f"generated output used as input: {path}")
            if inputs.get(path, digest) != digest:
                raise AtlasError(f"inconsistent input digests for {path}")
            inputs[path] = digest
        return fragment

    add(importlinter.extract(root))
    add(docs_scan.extract(root))
    add(components.extract(root))
    modules_fragment = add(python_modules.extract(root))
    cli_fragment = add(cli_tree.extract(root))
    add(mcp_tools.extract(root, cli_ids={n.id for n in cli_fragment.nodes}))
    add(api_routes.extract(root))
    add(frontend_scan.extract(root))
    workflow_fragment = add(workflow.extract(root))
    module_ids = {n.id for n in modules_fragment.nodes}
    add(tests_map.extract(root, workflow_fragment=workflow_fragment, module_ids=module_ids))
    graph = merge_fragments(fragments)
    resolve_levels(graph)
    validate_graph(graph)
    inputs_text = dumps_canonical({"schema_version": 1, "files": inputs})
    inputs_hash = hashlib.sha256(inputs_text.encode("utf-8")).hexdigest()
    payload = graph_payload(graph, inputs_hash)
    graph_text = dumps_compact(payload)
    unknowns = sorted(node.id for node in graph.nodes.values() if node.evidence.level == "unknown")
    unknowns_text = dumps_canonical(
        {
            "schema_version": 1,
            "inputs_hash": inputs_hash,
            "purpose": "review queue: nodes with no doc anchor, test, or cross-layer link",
            "unknown_node_ids": unknowns,
        }
    )
    return {
        GRAPH_PATH: graph_text,
        INPUTS_PATH: inputs_text,
        UNKNOWNS_PATH: unknowns_text,
        **emit_docs(payload),
    }


def discover_repo_root() -> Path:
    return find_repo_root(Path(__file__).resolve())


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def refresh_cli_cache(root: Path) -> None:
    """Explicitly re-enumerate the CLI surface into the committed cache (subprocess)."""
    import json
    import subprocess

    result = subprocess.run(
        ["uv", "run", "alpha", "info", "commands", "--json"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    commands = json.loads(result.stdout)
    _write_atomic(
        root / cli_tree.CACHE_REL,
        dumps_compact({"schema_version": 1, "commands": commands}),
    )
    print(f"wrote {cli_tree.CACHE_REL} ({len(commands)} commands)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the Atlas knowledge graph.")
    parser.add_argument("--check", action="store_true", help="verify committed outputs are fresh")
    parser.add_argument("--repo", type=Path, default=None, help="repository root override")
    parser.add_argument(
        "--refresh-cli",
        action="store_true",
        help="re-run `alpha info commands --json` into the committed cache first",
    )
    args = parser.parse_args(argv)
    root = args.repo.resolve() if args.repo is not None else discover_repo_root()
    if args.refresh_cli:
        refresh_cli_cache(root)
    outputs = build_outputs(root)
    if args.check:
        stale = [
            rel
            for rel, text in sorted(outputs.items())
            if not (root / rel).is_file() or (root / rel).read_text(encoding="utf-8") != text
        ]
        if stale:
            print(f"stale generated atlas output: {', '.join(stale)}", file=sys.stderr)
            print(
                "run: cd tools/alpha-atlas && uv run python -m alpha_atlas.generate",
                file=sys.stderr,
            )
            return 1
        print(f"atlas outputs fresh ({len(outputs)} file(s))")
        return 0
    for rel, text in sorted(outputs.items()):
        _write_atomic(root / rel, text)
        print(f"wrote {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
