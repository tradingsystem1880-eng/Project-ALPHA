"""The CI job definitions, shared by CI and local runs. Nothing here records a result."""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import gate

COMPONENTS = (
    "backend",
    "backend-static",
    "backend-tests",
    "backend-quant",
    "frontend",
    "frontend-full",
    "literature",
    "qlib",
    "eval",
)
Step = tuple[str, Path, list[str]]
GitOutputRunner = Callable[..., str]

PYTEST_MARKERS = "not network and not slow_oracle"
# Steps whose output is printed even when they pass (the mutation report is the evidence).
SHOW_OUTPUT = frozenset({"mutation gate"})

# Pull-request path filters for the isolated jobs. An entry ending in "/" or "*" is a prefix,
# anything else an exact path. Push to main and an unknown comparison base run everything.
_ALWAYS = (".github/", "scripts/gate*", "scripts/run_owned_test.py")
PATH_FILTERS: dict[str, tuple[str, ...]] = {
    # The worker is isolated, but its bridge test drives the alpha-cli journal through the
    # platform interpreter (workers/qlib/tests/test_w09_durable_bridge.py).
    "qlib": (
        "workers/qlib/",
        "packages/",
        "apps/alpha-cli/",
        "tests/unit/test_w09_durable_observations.py",
        "pyproject.toml",
        "uv.lock",
    ),
    "literature": ("workers/literature/",),
    # Benchmark worlds run in the platform environment and its tests read repository paths.
    "eval": ("tools/alpha-eval/", "packages/", "apps/", "docs/", "pyproject.toml", "uv.lock"),
}


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


def _touches(path: str, entries: tuple[str, ...]) -> bool:
    return any(
        path.startswith(e.rstrip("*")) if e.endswith(("/", "*")) else path == e for e in entries
    )


def ci_changes(root: Path, context: dict[str, Any], *, run_all: bool = False) -> dict[str, bool]:
    """Which conditional CI jobs a change needs. Unknown history is not "no change": run all."""
    paths = context["paths"]
    selected = {
        name: run_all
        or paths is None
        or any(_touches(path, (*_ALWAYS, *entries)) for path in paths)
        for name, entries in PATH_FILTERS.items()
    }
    # The quant job keeps its own rule (touched quant-tier source, as before), on every event.
    selected["quant"] = bool(mutation_targets(root, paths))
    return selected


def collected_test_files(root: Path) -> list[str]:
    """Every file pytest collects under ``tests/`` (default ``python_files`` patterns)."""
    found = {*root.glob("tests/**/test_*.py"), *root.glob("tests/**/*_test.py")}
    return sorted(p.relative_to(root).as_posix() for p in found if p.is_file())


DURATIONS_FILE = Path("scripts") / "gate_test_durations.json"


def shard_paths(root: Path, index: int, total: int) -> list[str]:
    """Shard ``index`` (1-based) of ``total``: whole test files, balanced by measured time.

    Longest-first greedy packing over the per-file seconds in ``DURATIONS_FILE``; a file with
    no measurement weighs the median. Every collected file lands in exactly one shard, so stale
    timings can only unbalance the shards, never drop a test.
    """
    if not 1 <= index <= total:
        raise ValueError(f"shard {index}/{total} is out of range")
    files = collected_test_files(root)
    recorded = gate.read_json(root / DURATIONS_FILE) or {}
    seconds = {
        path: float(value)
        for path, value in recorded.get("seconds", {}).items()
        if isinstance(value, int | float)
    }
    known = sorted(seconds[path] for path in files if path in seconds)
    default = known[len(known) // 2] if known else 1.0
    loads = [0.0] * total
    shards: list[list[str]] = [[] for _ in range(total)]
    for path in sorted(files, key=lambda path: (-seconds.get(path, default), path)):
        target = loads.index(min(loads))
        loads[target] += seconds.get(path, default)
        shards[target].append(path)
    return sorted(shards[index - 1])


def file_durations(reports: list[Path]) -> dict[str, float]:
    """Per-file test seconds summed from pytest JUnit XML reports (the shard balance input)."""
    import xml.etree.ElementTree as ET

    totals: dict[str, float] = {}
    for report in reports:
        for case in ET.parse(report).getroot().iter("testcase"):
            parts = (case.get("classname") or "").split(".")
            modules = [i for i, part in enumerate(parts) if part.startswith("test_")]
            if not modules:
                continue
            path = "/".join(parts[: modules[-1] + 1]) + ".py"
            totals[path] = totals.get(path, 0.0) + float(case.get("time") or 0.0)
    return {path: round(value, 1) for path, value in sorted(totals.items())}


def _backend_static(root: Path) -> list[Step]:
    """Locked setup, lint, the one mypy run, harness wiring, semgrep, OpenAPI and wheels."""
    harness_files = [rel for rel in gate.HARNESS_SCRIPTS if (root / rel).is_file()]
    steps: list[Step] = [
        (name, root, command)
        for name, command in [
            ("uv lock", ["uv", "lock", "--check"]),
            ("uv sync", ["uv", "sync", "--locked"]),
            ("ruff check", ["uv", "run", "ruff", "check", "."]),
            ("ruff format", ["uv", "run", "ruff", "format", "--check", "."]),
            ("import contracts", ["uv", "run", "lint-imports"]),
            # One mypy run: pyproject's strict config covers packages, apps, tests and harness.
            ("mypy", [*gate.FULL_GATE_MYPY_COMMAND, *harness_files]),
            ("harness lint", [sys.executable, "scripts/gate.py", "lint-harness"]),
            ("harness doctor", ["uv", "run", "python", "scripts/gate.py", "doctor"]),
        ]
    ]
    if (root / gate.SEMGREP_RULES).is_file():
        steps += [
            ("semgrep", root, [sys.executable, "scripts/gate.py", "semgrep"]),
            ("semgrep contracts", root, [sys.executable, "scripts/check_semgrep_contracts.py"]),
        ]
    steps += [
        (name, root, command)
        for name, command in [
            (
                "openapi freshness",
                ["uv", "run", "python", "scripts/generate_web_openapi.py", "--check"],
            ),
            ("openapi authority", ["uv", "run", "python", "scripts/check_openapi_operations.py"]),
            ("build wheels", ["uv", "build", "--all-packages"]),
            ("wheel smoke", ["uv", "run", "python", "scripts/wheel_smoke.py"]),
        ]
    ]
    return steps


def pytest_command(paths: list[str] | None = None) -> list[str]:
    """The CI pytest run: every test but ``network`` and ``slow_oracle``, with coverage data.

    The coverage figure is reported (and changed lines gated) by the coverage step, never here.
    """
    return [
        *("uv", "run", "pytest", "-q", "-n", "auto", "--dist", "worksteal"),
        *("-m", PYTEST_MARKERS, "--cov", "--cov-report="),
        *(paths or []),
    ]


def _backend_tests(root: Path, shard: tuple[int, int] | None) -> list[Step]:
    if shard is None:
        return [("pytest + coverage", root, pytest_command())]
    index, total = shard
    command = [*pytest_command(shard_paths(root, *shard)), f"--junitxml=pytest-shard-{index}.xml"]
    return [(f"pytest shard {index}/{total}", root, command)]


def _backend_quant(root: Path, context: dict[str, Any] | None) -> list[Step]:
    """Slow oracles and the mutation gate, only when quant-tier source changed."""
    paths = (context or comparison_context(root))["paths"]
    modules = mutation_targets(root, paths)
    if not modules:
        return []
    return [
        ("slow oracles", root, ["uv", "run", "pytest", "-q", "-m", "slow_oracle"]),
        ("mutation gate", root, ["uv", "run", "python", "scripts/gate.py", "mutate", *modules]),
    ]


def component_steps(
    root: Path,
    component: str,
    *,
    context: dict[str, Any] | None = None,
    shard: tuple[int, int] | None = None,
) -> list[Step]:
    if component == "backend":
        # The whole backend in one process, for local runs; CI splits it into the three below.
        return [
            *_backend_static(root),
            *_backend_tests(root, None),
            *_backend_quant(root, context),
        ]
    if component == "backend-static":
        return _backend_static(root)
    if component == "backend-tests":
        return [("uv sync", root, ["uv", "sync", "--locked"]), *_backend_tests(root, shard)]
    if component == "backend-quant":
        return [("uv sync", root, ["uv", "sync", "--locked"]), *_backend_quant(root, context)]
    if component in {"frontend", "frontend-full"}:
        cwd = root / "apps/alpha-web/frontend"
        # Pull requests run one viewport; nightly runs all four (frontend-full).
        viewports = "all" if component == "frontend-full" else "reference"
        return [
            ("install", cwd, ["npm", "ci"]),
            ("lint", cwd, ["npm", "run", "lint", "--", "--deny-warnings"]),
            ("build + types", cwd, ["npm", "run", "build"]),
            ("coverage", cwd, ["npm", "run", "test:coverage"]),
            ("API generation", cwd, ["npm", "run", "generate:api"]),
            ("API freshness", cwd, ["git", "diff", "--exit-code", "--", "src/api/generated.ts"]),
            ("browser", cwd, ["npm", "run", "test:e2e:built", "--", "--viewports", viewports]),
            (
                "SPA freshness",
                root,
                ["git", "diff", "--exit-code", "--", "apps/alpha-web/src/alpha_web/static/app"],
            ),
        ]
    if component in {"literature", "qlib", "eval"}:
        cwd = root / ("tools/alpha-eval" if component == "eval" else f"workers/{component}")
        return [
            ("lock", cwd, ["uv", "lock", "--check"]),
            ("install", cwd, ["uv", "sync", "--locked"]),
            ("lint", cwd, ["uv", "run", "ruff", "check", "."]),
            ("format", cwd, ["uv", "run", "ruff", "format", "--check", "."]),
            ("types", cwd, ["uv", "run", "mypy"]),
            ("tests", cwd, ["uv", "run", "pytest", "-q", "-m", "not network"]),
        ]
    raise ValueError(f"Unknown gate component: {component}")


def run_component(
    root: Path,
    component: str,
    *,
    steps: list[Step] | None = None,
    context: dict[str, Any] | None = None,
    shard: tuple[int, int] | None = None,
) -> int:
    """Run one component's steps in order and stop at the first failure, as CI does."""
    if steps is None:
        steps = component_steps(root, component, context=context, shard=shard)
    if not steps:
        print(f"[gate:{component}] No verification steps are configured; refusing to pass.")
        return 1
    for name, cwd, command in steps:
        ok, seconds, output = gate._env_runner(command, cwd=cwd)
        print(f"[gate:{component}] {name}: {'PASS' if ok else 'FAIL'} ({seconds:.1f}s)", flush=True)
        if not ok or name in SHOW_OUTPUT:
            print(output)
        if not ok:
            return 1
    return 0


def run_coverage(root: Path, *, shards: int, base: str | None, summary: Path | None = None) -> int:
    """Combine the shards' coverage data, report the global figure, gate changed lines.

    The global percentage is printed and written to the job summary but never gates. With a
    ``base``, changed lines of product source (``[tool.diff_cover]`` in pyproject.toml) must
    reach its ``fail_under``.
    """
    data = [root / f".coverage.shard-{index}" for index in range(1, shards + 1)]
    missing = [path.name for path in data if not path.is_file()]
    if missing:
        print(f"[gate:coverage] missing shard coverage data: {', '.join(missing)}")
        return 1
    run = gate._env_runner
    steps: list[tuple[str, list[str]]] = [
        ("combine", ["uv", "run", "coverage", "combine", "--keep", *map(str, data)]),
        ("global figure", ["uv", "run", "coverage", "report", "--format=total"]),
        ("xml", ["uv", "run", "coverage", "xml", "-o", "coverage.xml"]),
    ]
    lines: list[str] = []
    for name, command in steps:
        ok, seconds, output = run(command, cwd=root)
        print(f"[gate:coverage] {name}: {'PASS' if ok else 'FAIL'} ({seconds:.1f}s)", flush=True)
        if not ok:
            print(output)
            return 1
        if name == "global figure":
            # The total prints with the configured precision (e.g. 93.16); other output, such as
            # coverage's "Combined 4 files" note on stderr, may follow it.
            figures = re.findall(r"^\d+\.\d+$", output, re.MULTILINE)
            if not figures:
                print(f"[gate:coverage] no total in the coverage report output:\n{output}")
                return 1
            total = figures[-1]
            print(f"[gate:coverage] global line coverage {total}% (reported, not gated)")
            lines += ["## Coverage", "", f"Global line coverage: **{total}%** (reported only).", ""]
    code = 0
    if base is None:
        print("[gate:coverage] no comparison base: changed-line coverage not gated")
        lines.append("Changed-line coverage: not gated (no pull-request base).")
    else:
        report = root / "diff-coverage.md"
        command = [
            *("uv", "run", "diff-cover", "coverage.xml", "--config-file", "pyproject.toml"),
            *("--compare-branch", base, "--format", f"markdown:{report}"),
        ]
        ok, seconds, output = run(command, cwd=root)
        print(f"[gate:coverage] changed lines: {'PASS' if ok else 'FAIL'} ({seconds:.1f}s)")
        print(output)
        lines.append(report.read_text() if report.is_file() else output)
        code = 0 if ok else 1
    if summary is not None:
        with summary.open("a") as stream:
            stream.write("\n".join(lines) + "\n")
    return code
