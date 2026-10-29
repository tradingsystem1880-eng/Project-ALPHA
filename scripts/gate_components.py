"""Shared local/CI checks. Receipts describe evidence, never application authority."""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import gate

COMPONENTS = ("backend", "frontend", "literature", "qlib", "atlas", "eval")
Step = tuple[str, Path, list[str]]
CHECKPOINT_DIR = gate.STATE_DIR / "gate-checkpoints"
# Explicit allowlist: gate, review and coverage evidence only; never env, tokens or transcripts.
PRESERVED_EVIDENCE = (
    *(
        gate.STATE_DIR / name
        for name in (gate.STAMP_FILE, gate.REVIEW_VERDICT_FILE, gate.QUANT_ATTESTATION_FILE)
    ),
    *(gate.STATE_DIR / f"component-{name}.json" for name in COMPONENTS),
    Path(".coverage"),
    Path("apps/alpha-web/frontend/coverage/clover.xml"),
    Path("apps/alpha-web/frontend/coverage/coverage-final.json"),
)
GitOutputRunner = Callable[..., str]


def comparison_context(
    root: Path,
    base: str | None = None,
    *,
    git_runner: GitOutputRunner | None = None,
) -> dict[str, Any]:
    """The one comparison-base resolution: reference, resolved commit, merge base and paths.

    The merge base is taken from the resolved commit, never the ref string. Unavailable
    history is not no change: ``paths`` is None and selection is conservative.
    """
    if base is not None:
        reference, source = base, "argument"
    elif "ALPHA_GATE_BASE" in os.environ:
        reference, source = os.environ["ALPHA_GATE_BASE"], "environment"
    else:
        reference, source = "origin/main", "default"
    run_git = git_runner or gate._git
    resolve = ("rev-parse", "--verify", "--quiet", "--end-of-options", f"{reference}^{{commit}}")
    resolved = run_git(root, *resolve, check=False).strip()
    merge_base = ""
    if resolved:
        merge_base = run_git(root, "merge-base", resolved, "HEAD", check=False).strip()
    paths: list[str] | None = None
    if merge_base:
        committed_and_dirty = run_git(root, "diff", "--name-only", "-z", merge_base)
        untracked = run_git(root, "ls-files", "--others", "--exclude-standard", "-z")
        paths = sorted(set(filter(None, (committed_and_dirty + untracked).split("\0"))))
    return {
        "reference": reference,
        "reference_source": source,
        "resolved_base": resolved or None,
        "merge_base": merge_base or None,
        "selection_mode": "exact_diff" if merge_base else "conservative_fallback",
        "paths": paths,
    }


_BINDING_KEYS = ("reference", "resolved_base", "merge_base", "selection_mode")


def binding(context: dict[str, Any]) -> dict[str, Any]:
    """Fields a stamp binds; the reference source is diagnostic only."""
    return {key: context[key] for key in _BINDING_KEYS}


def changed_paths(
    root: Path,
    base: str | None = None,
    *,
    git_runner: GitOutputRunner | None = None,
) -> list[str] | None:
    """Merge-base diff plus dirty/untracked files; unavailable history is not no change."""
    paths: list[str] | None = comparison_context(root, base, git_runner=git_runner)["paths"]
    return paths


def mutation_targets(root: Path, paths: list[str] | None) -> list[str]:
    """Return the exact target set used by the backend mutation gate."""
    if paths is None:
        return gate.all_quant_source_modules(root)
    return gate.quant_source_modules(root, paths)


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


def component_steps(
    root: Path, component: str, *, context: dict[str, Any] | None = None
) -> list[Step]:
    if component == "backend":
        commands = [
            (name, root, [arg for arg in command if name != "semgrep" or arg != "--changed"])
            for name, command in gate.gate_steps("full", root)
            if name not in {"slow oracles", "mutation gate"}
        ]
        # Reuse the coverage suite's guard before expensive checks, after locked setup.
        setup_end = next(i for i, (name, _, _) in enumerate(commands) if name == "uv sync")
        commands.insert(
            setup_end + 1,
            (
                "manual preflight",
                root,
                [
                    "uv",
                    "run",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "tests/unit/test_claude_md_relocation.py::TestCurrentManual::test_core_is_small",
                ],
            ),
        )
        paths = (context or comparison_context(root))["paths"]
        modules = mutation_targets(root, paths)
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
            ("build + types", cwd, ["npm", "run", "build"]),
            ("coverage", cwd, ["npm", "run", "test:coverage"]),
            ("API generation", cwd, ["npm", "run", "generate:api"]),
            ("API freshness", cwd, ["git", "diff", "--exit-code", "--", "src/api/generated.ts"]),
            ("browser", cwd, ["npm", "run", "test:e2e:built"]),
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


def _portable(command: object, interpreter: object) -> object:
    """Abstract only the interpreter path, which differs between the gate and the Git hook."""
    if not isinstance(command, list):
        return command
    return ["{python}" if arg == interpreter else arg for arg in command]


def _steps_hash(root: Path, steps: list[Step]) -> str:
    normalized = [
        (name, str(cwd.relative_to(root)), _portable(cmd, sys.executable))
        for name, cwd, cmd in steps
    ]
    return hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()


def run_component(
    root: Path,
    component: str,
    *,
    steps: list[Step] | None = None,
    context: dict[str, Any] | None = None,
) -> int:
    """Execute a complete component; record failures as well as stable-tree success."""
    if not preserve_prior_evidence(root):
        return 1
    return _run_component(root, component, steps=steps, context=context)


def _run_component(
    root: Path,
    component: str,
    *,
    steps: list[Step] | None = None,
    context: dict[str, Any] | None = None,
) -> int:
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
    context = comparison_context(root) if context is None else context
    steps = component_steps(root, component, context=context) if steps is None else steps
    definition = _steps_hash(root, steps)
    results: list[dict[str, object]] = []
    success = bool(steps)
    if not steps:
        print(
            f"[gate:{component}] No verification steps are configured; refusing to pass component."
        )
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
            "comparison": binding(context),
            "interpreter": sys.executable,
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
    """A full stamp requires every component on the same unchanged tree and comparison base."""
    if not preserve_prior_evidence(root):
        return 1
    gate.clear_stamp(root)
    initial = gate.compute_tree_hash(root)
    context = comparison_context(root)
    definitions = {name: component_steps(root, name, context=context) for name in COMPONENTS}
    for component in COMPONENTS:
        if _run_component(root, component, steps=definitions[component], context=context):
            return 1
    if gate.compute_tree_hash(root) != initial:
        print("[gate:full] Tree changed between components; no stamp written.")
        return 1
    if binding(comparison_context(root)) != binding(context):
        print("[gate:full] Comparison base changed during verification; no stamp written.")
        return 1
    receipts = [
        gate.read_json(root / gate.STATE_DIR / f"component-{name}.json") for name in COMPONENTS
    ]
    if any(
        not _receipt_current(root, name, definitions[name], initial, receipt, binding(context))
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
        comparison=binding(context),
    )
    print("[gate:full] All components passed on one stable tree.")
    return 0


def preserve_prior_evidence(root: Path) -> bool:
    """Copy existing evidence to a hash-verified, read-only checkpoint before a run replaces it."""
    rows = [
        (path.as_posix(), (root / path).read_bytes())
        for path in PRESERVED_EVIDENCE
        if (root / path).is_file()
    ]
    if not rows:
        return True
    manifest = "".join(
        f"{name}\t{len(data)}\t{hashlib.sha256(data).hexdigest()}\n" for name, data in rows
    )
    target = root / CHECKPOINT_DIR / f"pre-run-{hashlib.sha256(manifest.encode()).hexdigest()[:16]}"
    staging: Path | None = None
    try:
        if target.exists():
            if not _checkpoint_matches(target, manifest):
                raise OSError(f"{target.relative_to(root)} exists with different contents")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=".incomplete-", dir=target.parent))
            for name, data in rows:
                (staging / name).parent.mkdir(parents=True, exist_ok=True)
                (staging / name).write_bytes(data)
            (staging / "MANIFEST.tsv").write_text(manifest)
            if not _checkpoint_matches(staging, manifest):
                raise OSError("the copied evidence does not match its manifest")
            if any((root / name).read_bytes() != data for name, data in rows):
                raise OSError("the evidence changed while it was being preserved")
            for path in sorted(staging.rglob("*"), reverse=True):
                path.chmod(0o444 if path.is_file() else 0o555)
            staging.chmod(0o555)
            staging.rename(target)
    except OSError as exc:
        # A failed attempt's staging copy is kept as evidence of that attempt; nothing cleans it up.
        kept = f"; incomplete copy kept at {staging.relative_to(root)}" if staging else ""
        print(f"[gate] Prior evidence was not preserved ({exc}{kept}); refusing to overwrite it.")
        return False
    print(f"[gate] Prior evidence preserved in {target.relative_to(root)}.")
    return True


def _checkpoint_matches(directory: Path, manifest: str) -> bool:
    rows = [line.split("\t") for line in manifest.splitlines()]
    files = sorted(p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file())
    if files != sorted([*(name for name, _, _ in rows), "MANIFEST.tsv"]):
        return False
    if (directory / "MANIFEST.tsv").read_text() != manifest:
        return False
    for name, size, digest in rows:
        data = (directory / name).read_bytes()
        if len(data) != int(size) or hashlib.sha256(data).hexdigest() != digest:
            return False
    return True


def full_stamp_usable(root: Path, stamp: dict[str, Any]) -> tuple[bool, str]:
    """Whether a full stamp still matches today's comparison base and component definitions."""
    context = comparison_context(root)
    recorded = stamp.get("comparison")
    if not isinstance(recorded, dict) or recorded != binding(context):
        return False, "the comparison base differs from the gated base or was not recorded"
    for name in COMPONENTS:
        receipt = gate.read_json(root / gate.STATE_DIR / f"component-{name}.json")
        steps = component_steps(root, name, context=context)
        if not _receipt_current(
            root, name, steps, str(stamp.get("tree_hash")), receipt, binding(context)
        ):
            return False, f"the {name} receipt is missing or stale"
    return True, ""


def _receipt_current(
    root: Path,
    component: str,
    steps: list[Step],
    tree_hash: str,
    receipt: dict[str, object] | None,
    comparison: dict[str, Any],
) -> bool:
    if not receipt or receipt.get("comparison") != comparison:
        return False
    return _receipt_matches(root, component, steps, tree_hash, receipt)


def _receipt_matches(
    root: Path,
    component: str,
    steps: list[Step],
    tree_hash: str,
    receipt: dict[str, object] | None,
) -> bool:
    if not steps:
        return False
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
    interpreter = receipt.get("interpreter")
    recorded = receipt.get("steps")
    if not isinstance(interpreter, str) or not interpreter:
        return False
    if not isinstance(recorded, list) or len(recorded) != len(steps):
        return False
    for actual, (name, cwd, command) in zip(recorded, steps, strict=True):
        if not isinstance(actual, dict) or (
            actual.get("name") != name
            or _portable(actual.get("command"), interpreter) != _portable(command, sys.executable)
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
