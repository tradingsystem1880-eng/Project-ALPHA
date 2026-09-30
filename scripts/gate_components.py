"""Shared local/CI checks. Receipts describe evidence, never application authority."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import gate

COMPONENTS = ("backend", "frontend", "literature", "qlib", "atlas", "eval")
Step = tuple[str, Path, list[str]]


def changed_paths(root: Path, base: str | None = None) -> list[str] | None:
    """Merge-base diff plus dirty/untracked files; unavailable history is not no change."""
    reference = base or os.environ.get("ALPHA_GATE_BASE", "origin/main")
    resolved = gate._git(root, "merge-base", reference, "HEAD", check=False).strip()
    if not resolved:
        return None
    committed_and_dirty = gate._git(root, "diff", "--name-only", "-z", resolved)
    untracked = gate._git(root, "ls-files", "--others", "--exclude-standard", "-z")
    return sorted(set(filter(None, (committed_and_dirty + untracked).split("\0"))))


def required_components(paths: list[str] | None) -> set[str]:
    """Unknown impact is conservative; backend/Atlas inspect repository-wide contracts."""
    if paths is None:
        return set(COMPONENTS)
    required = {"backend", "atlas"}
    for path in paths:
        if path.startswith(("scripts/", ".github/", "tests/")) or path in {
            "pyproject.toml",
            "uv.lock",
            "CLAUDE.md",
            "AGENTS.md",
        }:
            return set(COMPONENTS)
        if path.startswith("apps/alpha-web/"):
            required.add("frontend")
        for worker in ("literature", "qlib"):
            if path.startswith(f"workers/{worker}/"):
                required.add(worker)
        if path.startswith("tools/alpha-eval/"):
            required.add("eval")
        if not path.startswith(("packages/", "apps/", "workers/", "docs/", "tools/")):
            return set(COMPONENTS)
    return required


def component_steps(root: Path, component: str) -> list[Step]:
    if component == "backend":
        commands = [
            (name, root, [arg for arg in command if name != "semgrep" or arg != "--changed"])
            for name, command in gate.gate_steps("full", root)
            if name not in {"slow oracles", "mutation gate"}
        ]
        paths = changed_paths(root)
        modules = (
            gate.all_quant_source_modules(root)
            if paths is None
            else gate.quant_source_modules(root, paths)
        )
        if modules:
            commands.extend(
                [
                    ("slow oracles", root, ["uv", "run", "pytest", "-q", "-m", "slow_oracle"]),
                    (
                        "mutation gate",
                        root,
                        ["uv", "run", "python", "scripts/gate.py", "mutate", *modules],
                    ),
                ]
            )
        return commands
    if component == "frontend":
        cwd = root / "apps/alpha-web/frontend"
        return [
            ("install", cwd, ["npm", "ci"]),
            ("lint", cwd, ["npm", "run", "lint", "--", "--deny-warnings"]),
            ("types", cwd, ["npx", "tsc", "-b", "--pretty", "false"]),
            ("coverage", cwd, ["npm", "run", "test:coverage"]),
            ("API generation", cwd, ["npm", "run", "generate:api"]),
            ("API freshness", cwd, ["git", "diff", "--exit-code", "--", "src/api/generated.ts"]),
            ("browser", cwd, ["npm", "run", "test:e2e"]),
            (
                "SPA freshness",
                root,
                ["git", "diff", "--exit-code", "--", "apps/alpha-web/src/alpha_web/static/app"],
            ),
        ]
    if component in {"literature", "qlib", "atlas", "eval"}:
        tools = {"atlas": "tools/alpha-atlas", "eval": "tools/alpha-eval"}
        cwd = root / tools.get(component, f"workers/{component}")
        steps: list[Step] = [
            ("lock", cwd, ["uv", "lock", "--check"]),
            ("install", cwd, ["uv", "sync", "--locked"]),
            ("lint", cwd, ["uv", "run", "ruff", "check", "."]),
            ("format", cwd, ["uv", "run", "ruff", "format", "--check", "."]),
            ("types", cwd, ["uv", "run", "mypy"]),
            ("tests", cwd, ["uv", "run", "pytest", "-q", "-m", "not network"]),
        ]
        if component == "atlas":
            steps.append(
                ("freshness", cwd, ["uv", "run", "python", "-m", "alpha_atlas.generate", "--check"])
            )
        return steps
    raise ValueError(f"Unknown gate component: {component}")


def definition_hash(root: Path, component: str) -> str:
    return _steps_hash(root, component_steps(root, component))


def _steps_hash(root: Path, steps: list[Step]) -> str:
    normalized = [(name, str(cwd.relative_to(root)), cmd) for name, cwd, cmd in steps]
    return hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()


def run_component(root: Path, component: str, *, steps: list[Step] | None = None) -> int:
    """Execute a complete component; record failures as well as stable-tree success."""
    gate.clear_stamp(root)
    receipt_path = root / gate.STATE_DIR / f"component-{component}.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    gate.write_json_atomic(
        receipt_path,
        {
            "schema_version": 1,
            "component": component,
            "tree_hash": None,
            "definition_hash": None,
            "ok": False,
            "status": "started",
            "steps": [],
        },
    )
    initial = gate.compute_tree_hash(root)
    steps = component_steps(root, component) if steps is None else steps
    definition = _steps_hash(root, steps)
    results: list[dict[str, object]] = []
    success = True
    for name, cwd, command in steps:
        ok, seconds, output = gate._env_runner(command, cwd=cwd)
        results.append(
            {
                "name": name,
                "command": command,
                "cwd": str(cwd.relative_to(root)),
                "ok": ok,
                "seconds": seconds,
            }
        )
        print(f"[gate:{component}] {name}: {'PASS' if ok else 'FAIL'} ({seconds:.1f}s)", flush=True)
        if not ok:
            print(output)
            success = False
            break
    stable = gate.compute_tree_hash(root) == initial
    success = success and stable
    gate.write_json_atomic(
        receipt_path,
        {
            "schema_version": 1,
            "component": component,
            "tree_hash": initial,
            "definition_hash": definition,
            "ok": success,
            "status": "passed" if success else "failed",
            "stable_tree": stable,
            "steps": results,
        },
    )
    if not stable:
        print(f"[gate:{component}] Tree changed during verification; receipt is not a pass.")
    return 0 if success else 1


def run_full(root: Path) -> int:
    """A full stamp requires every component on the same unchanged tree."""
    gate.clear_stamp(root)
    initial = gate.compute_tree_hash(root)
    definitions = {name: component_steps(root, name) for name in COMPONENTS}
    for component in COMPONENTS:
        if run_component(root, component, steps=definitions[component]):
            return 1
    if gate.compute_tree_hash(root) != initial:
        print("[gate:full] Tree changed between components; no stamp written.")
        return 1
    receipts = [
        gate.read_json(root / gate.STATE_DIR / f"component-{name}.json") for name in COMPONENTS
    ]
    if any(
        not _receipt_matches(root, name, definitions[name], initial, receipt)
        for name, receipt in zip(COMPONENTS, receipts, strict=True)
    ):
        return 1
    gate.write_stamp(
        root,
        "full",
        steps=[(name, 0.0, True) for name in COMPONENTS],
        duration=sum(
            float(step["seconds"]) for receipt in receipts if receipt for step in receipt["steps"]
        ),
        tested_tree=initial,
    )
    print("[gate:full] All components passed on one stable tree.")
    return 0


def _receipt_matches(
    root: Path,
    component: str,
    steps: list[Step],
    tree_hash: str,
    receipt: dict[str, object] | None,
) -> bool:
    if not receipt or any(
        receipt.get(key) != value
        for key, value in {
            "schema_version": 1,
            "component": component,
            "tree_hash": tree_hash,
            "definition_hash": _steps_hash(root, steps),
            "status": "passed",
        }.items()
    ):
        return False
    if receipt.get("ok") is not True or receipt.get("stable_tree") is not True:
        return False
    recorded = receipt.get("steps")
    if not isinstance(recorded, list) or len(recorded) != len(steps):
        return False
    for actual, (name, cwd, command) in zip(recorded, steps, strict=True):
        if not isinstance(actual, dict) or (
            actual.get("name") != name
            or actual.get("command") != command
            or actual.get("cwd") != str(cwd.relative_to(root))
            or actual.get("ok") is not True
        ):
            return False
        seconds = actual.get("seconds")
        if (
            not isinstance(seconds, (int, float))
            or isinstance(seconds, bool)
            or not math.isfinite(seconds)
            or seconds < 0
        ):
            return False
    return True
