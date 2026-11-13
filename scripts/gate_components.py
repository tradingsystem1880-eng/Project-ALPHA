"""The CI job definitions, shared by CI and local runs. Nothing here records a result."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import gate

COMPONENTS = ("backend", "frontend", "literature", "qlib", "atlas", "eval")
Step = tuple[str, Path, list[str]]
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


def mutation_targets(root: Path, paths: list[str] | None) -> list[str]:
    """Return the exact target set used by the backend mutation gate."""
    if paths is None:
        return gate.all_quant_source_modules(root)
    return gate.quant_source_modules(root, paths)


def component_steps(
    root: Path, component: str, *, context: dict[str, Any] | None = None
) -> list[Step]:
    if component == "backend":
        harness_files = [rel for rel in gate.HARNESS_SCRIPTS if (root / rel).is_file()]
        commands: list[Step] = [
            (name, root, command)
            for name, command in [
                ("uv lock", ["uv", "lock", "--check"]),
                ("uv sync", ["uv", "sync", "--locked"]),
                ("ruff check", ["uv", "run", "ruff", "check", "."]),
                ("ruff format", ["uv", "run", "ruff", "format", "--check", "."]),
                ("import contracts", ["uv", "run", "lint-imports"]),
                ("mypy", list(gate.FULL_GATE_MYPY_COMMAND)),
                ("mypy harness", ["uv", "run", "mypy", *harness_files]),
                ("harness lint", [sys.executable, "scripts/gate.py", "lint-harness"]),
            ]
        ]
        if (root / gate.SEMGREP_RULES).is_file():
            commands += [
                ("semgrep", root, [sys.executable, "scripts/gate.py", "semgrep"]),
                ("semgrep contracts", root, [sys.executable, "scripts/check_semgrep_contracts.py"]),
            ]
        pytest = [
            "uv",
            "run",
            "pytest",
            "-q",
            "-n",
            "auto",
            "-m",
            "not network and not slow_oracle",
        ]
        commands += [
            (name, root, command)
            for name, command in [
                ("pytest + coverage", [*pytest, "--cov"]),
                (
                    "openapi freshness",
                    ["uv", "run", "python", "scripts/generate_web_openapi.py", "--check"],
                ),
                (
                    "openapi authority",
                    ["uv", "run", "python", "scripts/check_openapi_operations.py"],
                ),
                ("build wheels", ["uv", "build", "--all-packages"]),
                ("wheel smoke", ["uv", "run", "python", "scripts/wheel_smoke.py"]),
            ]
        ]
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


def run_component(
    root: Path,
    component: str,
    *,
    steps: list[Step] | None = None,
    context: dict[str, Any] | None = None,
) -> int:
    """Run one component's steps in order and stop at the first failure, as CI does."""
    steps = component_steps(root, component, context=context) if steps is None else steps
    if not steps:
        print(f"[gate:{component}] No verification steps are configured; refusing to pass.")
        return 1
    for name, cwd, command in steps:
        ok, seconds, output = gate._env_runner(command, cwd=cwd)
        print(f"[gate:{component}] {name}: {'PASS' if ok else 'FAIL'} ({seconds:.1f}s)", flush=True)
        if not ok:
            print(output)
            return 1
    return 0
