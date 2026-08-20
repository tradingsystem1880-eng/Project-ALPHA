"""Generate AI Context: turn a graph selection into a high-quality agent prompt.

The pack is Atlas's bridge from human understanding to a safe Codex/Claude
prompt. Twelve fixed sections; everything in them is drawn from the graph
(computed evidence, verified anchors, incident edges) plus the repository's
own governance files (.claude/rules paths globs). Tier flags are conservative
pointers, not enforcement — the harness remains the authority.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any

from alpha_atlas.core.model import AtlasError

SECTIONS: tuple[str, ...] = (
    "TARGET AREA",
    "CURRENT STATE",
    "ARCHITECTURAL INTENT",
    "EXISTING IMPLEMENTATION",
    "DEPENDENCIES",
    "DO NOT CHANGE",
    "FILES LIKELY TO MODIFY",
    "FILES NOT TO MODIFY",
    "TEST REQUIREMENTS",
    "VALIDATION COMMANDS",
    "OPEN QUESTIONS / KNOWN LIMITATIONS",
    "RELEVANT DOCUMENTATION",
)

# Conservative pointers mirrored from the harness docs; gate.py is the authority.
_QUANT_PREFIXES = ("packages/alpha-validation/src/", "packages/alpha-research/src/")
_RISK_FILES = tuple(
    f"apps/alpha-cli/src/alpha_cli/{name}.py"
    for name in ("_gauntlet", "_optim", "_seeds", "_identity", "_surrogate", "_synth", "_runner")
)
_PROTECTED_POINTER = (
    "Protected control plane (audited ack per edit; see scripts/gate.py for the "
    "authoritative list): scripts/gate.py, scripts/claude_hooks.py, CLAUDE.md, "
    "AGENTS.md, .claude/**, .github/workflows/**, tests/bias_guards|holdout|oracles/**"
)

_RULE_GLOB_RE = re.compile(r'^\s*-\s*"([^"]+)"\s*$')


def load_rule_globs(root: Path) -> dict[str, list[str]]:
    """Rule-file stem -> paths globs, parsed from .claude/rules front matter."""
    rules: dict[str, list[str]] = {}
    for path in sorted((root / ".claude/rules").glob("*.md")):
        globs: list[str] = []
        in_front = False
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip() == "---":
                if in_front:
                    break
                in_front = True
                continue
            if in_front:
                match = _RULE_GLOB_RE.match(line)
                if match:
                    globs.append(match.group(1))
        if globs:
            rules[path.stem] = globs
    return rules


def _meta_list(meta: dict[str, Any], key: str) -> list[str]:
    value = meta.get(key)
    return [str(item) for item in value] if isinstance(value, list) else []


def build_prompt_pack(
    graph: dict[str, Any], node_ids: list[str], rules: dict[str, list[str]]
) -> str:
    nodes_by_id = {n["id"]: n for n in graph["nodes"]}
    missing = [node_id for node_id in node_ids if node_id not in nodes_by_id]
    if missing:
        raise AtlasError(f"unknown node id(s): {', '.join(missing)}")
    selected = [nodes_by_id[node_id] for node_id in node_ids]
    selected_ids = set(node_ids)
    incident = [
        e for e in graph["edges"] if e["source"] in selected_ids or e["target"] in selected_ids
    ]

    anchors: list[dict[str, Any]] = []
    anchor_paths: list[str] = []
    for node in selected:
        for anchor in node.get("meta", {}).get("verified_anchors", []):
            anchors.append(anchor)
            anchor_paths.append(str(anchor["path"]))
        if node.get("path"):
            anchor_paths.append(str(node["path"]))

    def label_of(node_id: str) -> str:
        node = nodes_by_id.get(node_id)
        return f"{node['label']} ({node_id})" if node else node_id

    sections: dict[str, list[str]] = {name: [] for name in SECTIONS}

    for node in selected:
        meta = node.get("meta", {})
        purpose = meta.get("purpose", "")
        sections["TARGET AREA"].append(
            f"- **{node['label']}** [{node['kind']}] `{node['id']}`"
            + (f" — {purpose}" if purpose else "")
        )
        level = node["evidence"]["level"]
        flags = " — NEEDS RE-VERIFICATION" if meta.get("needs_reverification") else ""
        sections["CURRENT STATE"].append(
            f"- {node['label']}: computed evidence level **{level}**{flags} "
            f"({len(node['evidence']['provenance'])} provenance record(s))"
        )
        if level in ("unknown", "declared"):
            sections["OPEN QUESTIONS / KNOWN LIMITATIONS"].append(
                f"- {node['label']} is only **{level}** — no verified implementation anchor; "
                "confirm it exists before building on it"
            )
        for item in _meta_list(meta, "limitations"):
            sections["OPEN QUESTIONS / KNOWN LIMITATIONS"].append(f"- {item}")
        for item in _meta_list(meta, "safe_change"):
            sections["FILES LIKELY TO MODIFY"].append(f"- {item}")

    defining_docs = sorted(
        {e["source"] for e in incident if e["type"] == "defines" and e["target"] in selected_ids}
    )
    for doc_id in defining_docs:
        sections["ARCHITECTURAL INTENT"].append(f"- Defined by {label_of(doc_id)}")
        doc = nodes_by_id.get(doc_id)
        if doc and doc.get("path"):
            sections["RELEVANT DOCUMENTATION"].append(f"- {doc['path']}")

    for anchor in anchors:
        symbol = f" — `{anchor['symbol']}`" if anchor.get("symbol") else ""
        sections["EXISTING IMPLEMENTATION"].append(f"- {anchor['path']}:{anchor['line']}{symbol}")
        sections["FILES LIKELY TO MODIFY"].append(f"- {anchor['path']}")

    for edge in incident:
        if edge["type"] in ("depends_on", "calls", "serves", "produces"):
            arrow = "→" if edge["source"] in selected_ids else "←"
            other = edge["target"] if edge["source"] in selected_ids else edge["source"]
            sections["DEPENDENCIES"].append(f"- {edge['type']} {arrow} {label_of(other)}")

    matched_rules = sorted(
        {
            stem
            for stem, globs in rules.items()
            for path in anchor_paths
            for glob in globs
            if fnmatch.fnmatch(path, glob)
        }
    )
    for stem in matched_rules:
        sections["DO NOT CHANGE"].append(
            f"- Follow `.claude/rules/{stem}.md` (path-scoped rule matching this area)"
        )
        sections["RELEVANT DOCUMENTATION"].append(f"- .claude/rules/{stem}.md")
    top_modules = {
        path.split("/src/")[1].split("/")[0].split(".")[0]
        for path in anchor_paths
        if "/src/" in path
    }
    for node in graph["nodes"]:
        if node["kind"] != "contract":
            continue
        if top_modules & set(node.get("meta", {}).get("source_modules", [])):
            sections["DO NOT CHANGE"].append(f"- Import-linter contract: {node['label']}")
    sections["DO NOT CHANGE"].append(f"- {_PROTECTED_POINTER}")
    sections["FILES NOT TO MODIFY"].append(f"- {_PROTECTED_POINTER}")

    validating = sorted(
        {e["source"] for e in incident if e["type"] == "validates" and e["target"] in selected_ids}
    )
    for test_id in validating[:20]:
        sections["TEST REQUIREMENTS"].append(f"- {test_id.removeprefix('test:')}")
    if len(validating) > 20:
        sections["TEST REQUIREMENTS"].append(f"- … and {len(validating) - 20} more")
    sections["TEST REQUIREMENTS"].append(
        "- TDD: write the failing test first; new data/strategy units need a "
        "@pytest.mark.bias_guard future-poison test"
    )

    quant = any(p.startswith(_QUANT_PREFIXES) for p in anchor_paths)
    risk = any(p in _RISK_FILES for p in anchor_paths)
    commands = [
        "- `uv run python scripts/gate.py fast` after edits; `full` before any commit",
    ]
    if quant:
        commands.append(
            "- QUANT TIER touched: `/verify-quant` (primary-source verification) required "
            "before Stop"
        )
    if risk:
        commands.append("- RISK TIER touched: `/review-gate` APPROVE required before commit")
    if any(p.startswith("apps/alpha-web/frontend/") for p in anchor_paths):
        commands.append("- Frontend gate: see CLAUDE.md Commands (npm ci … test:e2e)")
    sections["VALIDATION COMMANDS"] = commands
    sections["RELEVANT DOCUMENTATION"].append(
        "- docs/atlas/ (generated maps) and architecture/atlas/generated/graph.json"
    )

    out = ["# AI CONTEXT — generated by Alpha Atlas", ""]
    for name in SECTIONS:
        out.append(f"## {name}")
        body = sections[name] if sections[name] else ["- (none recorded)"]
        out.extend(dict.fromkeys(body))  # dedupe, keep order
        out.append("")
    return "\n".join(out)
