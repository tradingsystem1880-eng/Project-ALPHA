"""Quant-rigor sweeps (mutation, semgrep, determinism, raise coverage) —
imported lazily by gate.py.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import sys
import tomllib
from pathlib import Path
from typing import Any

import gate

MUTATION_BASELINE_FILE = Path(".claude") / "mutation-baseline.json"
MUTATION_MIN_KILL = 0.90
MUTATION_TOLERANCE = 0.005  # a mutant flipping on timing must not flap the verdict
_MUTATION_TEST_DIRS = ("unit", "oracles", "bias_guards")
_DETERMINISM_TEST_GLOBS = (
    "tests/**/test_*determinism*.py",
    "tests/**/test_*identity*.py",
    "tests/**/test_*golden*.py",
)
_DETERMINISM_ENVS = (
    {"PYTHONHASHSEED": "0", "TZ": "UTC", "OMP_NUM_THREADS": "1"},
    {"PYTHONHASHSEED": "31337", "TZ": "Pacific/Kiritimati", "OMP_NUM_THREADS": "1"},
)


def _glob_rel(root: Path, globs: tuple[str, ...]) -> list[str]:
    """Repo-relative paths matching any of ``globs``, deduped and sorted."""
    return sorted({str(p.relative_to(root)) for pattern in globs for p in root.glob(pattern)})


def stage_mutation_tree(root: Path, modules: list[str], staging: Path) -> list[str]:
    """Copy each module's package + the tests that mention it into ``staging`` for mutmut.

    mutmut inserts only ``mutants/{.,src,source}`` into ``sys.path``, so the uv-workspace
    layout (``packages/<pkg>/src/<pkg>``) is flattened to ``src/<pkg>``. Test selection is
    textual on purpose (a test that never names the package cannot kill its mutants).
    """
    if staging.exists():
        shutil.rmtree(staging)
    (staging / "src").mkdir(parents=True)
    only: list[str] = []
    packages: set[str] = set()
    for rel in modules:
        pkg_root, _, inner = rel.partition("/src/")
        pkg = inner.split("/")[0]
        packages.add(pkg)
        if not (staging / "src" / pkg).exists():
            shutil.copytree(
                root / pkg_root / "src" / pkg,
                staging / "src" / pkg,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
            # tests that inspect source by repo-relative path (e.g. the figure renderer's
            # "never twinx" AST scan) need the workspace layout mirrored too (unmutated copy)
            shutil.copytree(
                root / pkg_root / "src" / pkg,
                staging / pkg_root / "src" / pkg,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        only.append(f"src/{inner}")
    tests_root = root / "tests"
    (staging / "tests").mkdir()
    for top in tests_root.glob("*.py"):
        shutil.copy2(top, staging / "tests" / top.name)
    if (tests_root / "fixtures").is_dir():
        shutil.copytree(tests_root / "fixtures", staging / "tests" / "fixtures")
    candidates: dict[Path, str] = {}
    for name in _MUTATION_TEST_DIRS:
        source_dir = tests_root / name
        if source_dir.is_dir():
            for path in sorted(source_dir.rglob("*.py")):
                candidates[path.relative_to(tests_root)] = path.read_text(errors="replace")
    keep: set[Path] = {
        rel_path
        for rel_path, text in candidates.items()
        if rel_path.name == "__init__.py"
        or "_reference" in rel_path.parts
        or any(
            re.search(rf"^\s*(from|import)\s+{re.escape(pkg)}\b", text, re.M) for pkg in packages
        )
    }
    # close over intra-``tests`` imports (``from tests.unit.x import helper``) so a kept test
    # never fails on a sibling module that the textual selection left behind
    frontier = list(keep)
    while frontier:
        text = candidates[frontier.pop()]
        for dotted in re.findall(r"^\s*from\s+tests\.([\w.]+)\s+import", text, re.M):
            sibling = Path(*dotted.split(".")).with_suffix(".py")
            if sibling in candidates and sibling not in keep:
                keep.add(sibling)
                frontier.append(sibling)
    for rel_path in sorted(keep):
        target = staging / "tests" / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tests_root / rel_path, target)
    markers: list[str] = []
    try:
        pyproject = tomllib.loads((root / "pyproject.toml").read_text())
        markers = list(pyproject["tool"]["pytest"]["ini_options"].get("markers", []))
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        markers = []
    (staging / "pyproject.toml").write_text(
        "[tool.mutmut]\n"
        f"source_paths = {json.dumps([f'src/{pkg}' for pkg in sorted(packages)])}\n"
        f"only_mutate = {json.dumps(only)}\n"
        'also_copy = ["packages"]\n'
        'pytest_add_cli_args_test_selection = ["tests"]\n'
        f"pytest_add_cli_args = {json.dumps(_MUTATION_PYTEST_ARGS)}\n"
        "use_git_change_detection = false\n"
        "track_dependencies = false\n"
        "\n[tool.pytest.ini_options]\n"
        'addopts = "--strict-markers --import-mode=importlib"\n'
        'pythonpath = [".", "src"]\n'
        f"markers = {json.dumps(markers)}\n"
    )
    return only


_MUTATION_PYTEST_ARGS = ["-p", "no:cacheprovider", "-q", "-x"]


def staging_only_failures(output: str) -> list[str]:
    """pytest ``-rfE`` short-summary lines → deselect/ignore args for tests that fail in staging.

    A test that reads the repo by relative path (a stylesheet, a docs file, ``.claude/``) fails
    in the flattened mutation tree through no fault of the module under test; excluding it is
    conservative (fewer killers) and is recorded in the report, never silent.
    """
    args: list[str] = []
    for line in output.splitlines():
        if line.startswith("FAILED "):
            args += ["--deselect", line[len("FAILED ") :].split(" - ", 1)[0].strip()]
        elif line.startswith("ERROR "):
            args += ["--ignore", line[len("ERROR ") :].split(" - ", 1)[0].split("::", 1)[0]]
    return args


def mutation_kill_rate(stats: dict[str, Any]) -> float:
    denominator = int(stats.get("total", 0)) - int(stats.get("skipped", 0))
    return int(stats.get("killed", 0)) / denominator if denominator > 0 else 0.0


def mutation_required(module: str, baseline: dict[str, float]) -> float:
    """Kill-rate floor: 0.90, or the recorded (lower) baseline so a legacy module cannot regress."""
    recorded = baseline.get(module)
    return MUTATION_MIN_KILL if recorded is None else min(MUTATION_MIN_KILL, float(recorded))


def mutate(
    root: Path,
    modules: list[str] | None = None,
    *,
    runner: gate.EnvRunner | None = None,
    timeout: float = 1800.0,
) -> tuple[int, dict[str, Any]]:
    """Mutation-test each quant module in isolation; block on a kill-rate below its floor.

    Tooling absence (no ``uvx``/network for mutmut, staged clean-run failure) is reported as
    ``unavailable:<reason>`` and never blocks — but it is printed and audited, never silent.
    """
    run = runner or gate._env_runner
    targets = (
        gate.quant_source_modules(root)
        if modules is None
        else gate.quant_source_modules(root, modules)
    )
    baseline_raw = gate.read_json(root / MUTATION_BASELINE_FILE) or {}
    baseline = {k: float(v) for k, v in baseline_raw.get("kill_rates", {}).items()}
    report: dict[str, Any] = {"modules": {}, "min_kill": MUTATION_MIN_KILL}
    blocking = False
    for rel in targets:
        staging = gate._state_dir(root) / "mutation" / Path(rel).stem
        stage_mutation_tree(root, [rel], staging)
        entry: dict[str, Any] = {}
        # staged clean run: exclude tests that fail only because of the flattened layout
        preflight = ["uv", "run", "--project", str(root), "pytest", "-q", "-rfE"]
        preflight += ["-p", "no:cacheprovider", "--continue-on-collection-errors", "tests"]
        pre_ok, pre_seconds, pre_out = run(preflight, cwd=staging, timeout=timeout)
        excluded = [] if pre_ok else staging_only_failures(pre_out)
        if excluded:
            entry["excluded_tests"] = sorted({t.split("[", 1)[0] for t in excluded[1::2]})
            pyproject_path = staging / "pyproject.toml"
            pyproject_path.write_text(
                pyproject_path.read_text().replace(
                    json.dumps(_MUTATION_PYTEST_ARGS),
                    json.dumps([*_MUTATION_PYTEST_ARGS, *excluded]),
                )
            )
        mutmut = ["uv", "run", "--project", str(root), "--with", "mutmut", "mutmut"]
        ok, seconds, output = run([*mutmut, "run"], cwd=staging, timeout=timeout)
        entry["seconds"] = round(seconds + pre_seconds, 1)
        stats_path = staging / "mutants" / "mutmut-cicd-stats.json"
        if ok:
            run([*mutmut, "export-cicd-stats"], cwd=staging, timeout=120)
        stats = gate.read_json(stats_path) if ok else None
        if stats is None:
            entry["status"] = f"unavailable:{output[-300:] or 'mutmut produced no stats'}"
        else:
            rate = mutation_kill_rate(stats)
            required = mutation_required(rel, baseline)
            entry.update(
                {
                    "killed": stats.get("killed"),
                    "survived": stats.get("survived"),
                    "total": stats.get("total"),
                    # module-scope mutants (constants, catalog data) that mutmut's function
                    # tracer cannot attribute to a test; counted as NOT killed (conservative)
                    "no_tests": stats.get("no_tests"),
                    "timeout": stats.get("timeout"),
                    "kill_rate": round(rate, 4),
                    "required": round(required, 4),
                }
            )
            if rate + MUTATION_TOLERANCE < required:
                entry["status"] = "fail"
                blocking = True
            else:
                entry["status"] = "pass"
        report["modules"][rel] = entry
        gate.append_audit(root, "mutation_gate", f"module={rel} status={entry['status']}")
        shutil.rmtree(staging, ignore_errors=True)
    return (1 if blocking else 0), report


def write_mutation_baseline(root: Path, report: dict[str, Any], *, reason: str, by: str) -> None:
    current = gate.read_json(root / MUTATION_BASELINE_FILE) or {}
    rates = dict(current.get("kill_rates", {}))
    for rel, entry in report.get("modules", {}).items():
        if "kill_rate" in entry:
            rates[rel] = entry["kill_rate"]
    gate.write_json_atomic(
        root / MUTATION_BASELINE_FILE,
        {"schema_version": 1, "kill_rates": dict(sorted(rates.items()))},
    )
    gate.append_audit(root, "mutation_baseline_written", f"by={by} reason={reason!r}")


_SEMGREP_BASE = (
    "uvx",
    "semgrep",
    "--config",
    str(gate.SEMGREP_RULES),
    "--metrics=off",
    "--quiet",
    "--error",
)


def semgrep_command(root: Path, paths: list[str]) -> list[str]:
    """``uvx semgrep`` over the given python paths (empty list ⇒ nothing to scan ⇒ ``[]``)."""
    targets = sorted(p for p in paths if p.endswith(".py") and (root / p).is_file())
    return [*_SEMGREP_BASE, *targets] if targets else []


def _scanner_failed_to_launch(output: str) -> bool:
    """True only when the scanner itself could not start (runner exception or a missing ``uvx``).

    Decided on the FIRST line so tokens inside real findings (a matched ``except OSError:``
    line, a message containing "No such file") can never be mistaken for an absent scanner.
    """
    first = output.strip().splitlines()[0] if output.strip() else ""
    return first.startswith(
        ("OSError", "FileNotFoundError", "PermissionError", "TimeoutExpired")
    ) or ("command not found" in first)


def semgrep(root: Path, *, changed_only: bool) -> int:
    if changed_only:
        paths = gate.scoped_changed_paths(root, lambda p: p.endswith(".py"))
        cmd = semgrep_command(root, paths)
    else:
        cmd = [*_SEMGREP_BASE, "packages", "apps", "scripts", "tests"]
    if not cmd:
        print("[semgrep] no python changes to scan")
        return 0
    ok, seconds, output = gate._env_runner(cmd, cwd=root, timeout=600)
    if ok:
        print(f"[semgrep] ok ({seconds:.1f}s)")
        return 0
    if _scanner_failed_to_launch(output):
        print(f"[semgrep] unavailable: {output[-200:]}", file=sys.stderr)
        gate.append_audit(root, "semgrep_unavailable", output[-200:])
        return 0
    print(output[-4000:], file=sys.stderr)
    return 1


def raise_sites(path: Path) -> list[int]:
    """Line numbers of every ``raise`` statement in a module (the fail-loud surface)."""
    tree = ast.parse(path.read_text(errors="replace"))
    return sorted(node.lineno for node in ast.walk(tree) if isinstance(node, ast.Raise))


def uncovered_raise_sites(root: Path, coverage_json: Path, modules: list[str]) -> list[str]:
    data = gate.read_json(coverage_json) or {}
    files = data.get("files", {})
    out: list[str] = []
    for rel in modules:
        entry = files.get(rel) or files.get(str(root / rel)) or {}
        missing = set(entry.get("missing_lines", []))
        out.extend(f"{rel}:{ln}" for ln in raise_sites(root / rel) if ln in missing)
    return out


def raise_cov(root: Path) -> tuple[list[str], int]:
    """Run the quant test tiers with branch coverage; list ``raise`` lines no test reached."""
    modules = gate.all_quant_source_modules(root)
    cov_json = gate._state_dir(root) / "raise-cov.json"
    cov_json.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "uv", "run", "pytest", "-q", "-p", "no:cacheprovider",
        "-m", "not network and not slow_oracle",
        "--cov=alpha_validation", "--cov=alpha_research", "--cov-branch",
        f"--cov-report=json:{cov_json}", "--cov-fail-under=0",
        "tests/unit", "tests/oracles", "tests/bias_guards",
    ]  # fmt: skip
    ok, _, output = gate._env_runner(cmd, cwd=root, timeout=3600)
    if not ok:
        print(output[-4000:], file=sys.stderr)
        return (["<test run failed>"], 0)
    total = sum(len(raise_sites(root / rel)) for rel in modules)
    return uncovered_raise_sites(root, cov_json, modules), total


def determinism(root: Path, *, runner: gate.EnvRunner | None = None) -> tuple[bool, str]:
    """Run the byte-stability / identity / golden tests twice in fresh processes.

    Each pass perturbs ``PYTHONHASHSEED``, ``TZ`` and pins ``OMP_NUM_THREADS=1``; the tests
    themselves compare artifacts against committed goldens, so two green passes under different
    process environments is the cross-process determinism evidence.
    """
    run = runner or gate._env_runner
    files = _glob_rel(root, _DETERMINISM_TEST_GLOBS)
    if not files:
        return (False, "no determinism tests found")
    for i, overrides in enumerate(_DETERMINISM_ENVS, start=1):
        env = {**os.environ, **overrides}
        ok, seconds, output = run(
            ["uv", "run", "pytest", "-q", "-p", "no:cacheprovider", *files],
            cwd=root,
            env=env,
            timeout=3600,
        )
        if not ok:
            return (False, f"pass {i} failed under {overrides}: {output[-1500:]}")
    return (True, f"2 passes green over {len(files)} file(s) under perturbed env")
