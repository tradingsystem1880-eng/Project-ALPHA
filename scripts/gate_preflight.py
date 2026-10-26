"""Read-only qualification checks ahead of the canonical gate."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import gate
import gate_components

MANUAL_SIZE_LIMIT = 6_000
MANUAL_FILES = ("CLAUDE.md", "AGENTS.md")
PUBLIC_TRACKED_ROOTS = (".semgrep", ".githooks", ".github/workflows", "tools/alpha-eval")
EXPECTED_PUBLIC_FILES = (
    ".semgrep/alpha.yml",
    ".semgrep/fixtures/float_contract.py.txt",
    ".githooks/commit-msg",
    ".githooks/pre-commit",
    ".github/workflows/ci.yml",
    ".github/workflows/nightly.yml",
    ".github/workflows/mutation-weekly.yml",
    "pyproject.toml",
    "uv.lock",
    "scripts/check_openapi_operations.py",
    "scripts/generate_web_openapi.py",
    "scripts/gate.py",
    "scripts/gate_components.py",
    "scripts/wheel_smoke.py",
    "tests/unit/test_claude_md_relocation.py",
    "tools/alpha-eval/pyproject.toml",
    "tools/alpha-eval/uv.lock",
)

Runner = Callable[..., subprocess.CompletedProcess[str]]


def manual_size_check(root: Path) -> tuple[bool, int]:
    """Shared predicate used by the existing manual-size unit test and this preflight."""
    paths = [root / name for name in MANUAL_FILES]
    if any(path.is_symlink() for path in paths):
        raise OSError("manual files must be regular files")
    total = sum(path.lstat().st_size for path in paths)
    return total <= MANUAL_SIZE_LIMIT, total


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    command = ["git", "-C", str(root), *args]
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return subprocess.CompletedProcess(command, 127, "", f"{type(exc).__name__}")


def _has_symlink_component(root: Path, relative: str) -> bool:
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def public_prerequisites(root: Path) -> dict[str, Any]:
    pathspecs = (*PUBLIC_TRACKED_ROOTS, *EXPECTED_PUBLIC_FILES, *gate.HARNESS_SCRIPTS)
    result = _git(root, "ls-files", "-z", "--", *pathspecs)
    if result.returncode:
        return {
            "name": "public_prerequisites",
            "mode": "metadata",
            "status": "blocked",
            "detail": "could not list the allowlisted public tracked paths",
            "tracked_file_count": 0,
            "missing": list(EXPECTED_PUBLIC_FILES),
        }
    tracked = set(filter(None, result.stdout.split("\0")))
    expected = set(EXPECTED_PUBLIC_FILES) | set(gate.HARNESS_SCRIPTS)
    expected.update(tracked)
    missing = sorted(
        path
        for path in expected
        if _has_symlink_component(root, path) or not (root / path).is_file()
    )
    return {
        "name": "public_prerequisites",
        "mode": "metadata",
        "status": "blocked" if missing else "passed",
        "detail": (
            f"{len(missing)} required public tracked file(s) missing"
            if missing
            else f"{len(expected)} required public tracked file(s) present"
        ),
        "tracked_file_count": len(expected),
        "missing": missing,
    }


def _is_temporary(path: Path) -> bool:
    candidate = path.resolve()
    roots = {Path("/tmp"), Path("/var/tmp"), Path("/private/tmp")}
    roots.update(
        Path(os.environ[name]) for name in ("TMPDIR", "TEMP", "TMP") if os.environ.get(name)
    )
    for root in roots:
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            continue
        return True
    return False


def git_object_storage(root: Path) -> dict[str, Any]:
    objects_result = _git(root, "rev-parse", "--git-path", "objects")
    if objects_result.returncode:
        return {
            "name": "git_object_storage",
            "mode": "metadata",
            "status": "blocked",
            "detail": "Git could not locate the candidate object store",
        }
    objects = Path(objects_result.stdout.strip())
    if not objects.is_absolute():
        objects = root / objects
    alternate_file = objects / "info" / "alternates"
    if alternate_file.is_symlink():
        return {
            "name": "git_object_storage",
            "mode": "metadata",
            "status": "blocked",
            "detail": "Git alternates metadata is a symlink; its target was not read",
        }
    alternates: list[Path] = []
    if alternate_file.is_file():
        try:
            if alternate_file.stat().st_size > 65_536:
                return {
                    "name": "git_object_storage",
                    "mode": "metadata",
                    "status": "blocked",
                    "detail": "Git alternates metadata exceeds 64 KiB; its contents were not read",
                }
            alternates = [
                Path(line.strip())
                for line in alternate_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except (OSError, UnicodeError):
            return {
                "name": "git_object_storage",
                "mode": "metadata",
                "status": "blocked",
                "detail": "Git alternates metadata is unreadable",
            }
    alternates = [path if path.is_absolute() else objects / path for path in alternates]
    alternates = list(dict.fromkeys(alternates))
    try:
        temporary = sum(_is_temporary(path) for path in alternates)
        invalid = sum(not path.is_dir() for path in alternates)
    except (OSError, RuntimeError):
        return {
            "name": "git_object_storage",
            "mode": "metadata",
            "status": "blocked",
            "detail": "could not verify Git alternate object directories",
        }
    environment_override = bool(os.environ.get("GIT_ALTERNATE_OBJECT_DIRECTORIES"))
    ok = temporary == 0 and invalid == 0 and not environment_override
    detail = (
        "no object alternates"
        if not alternates and not environment_override
        else (
            f"{len(alternates)} alternate(s): {temporary} temporary, "
            f"{invalid} missing or not object directories"
        )
    )
    if environment_override:
        detail += "; alternate-object environment override is set"
    return {
        "name": "git_object_storage",
        "mode": "metadata",
        "status": "passed" if ok else "blocked",
        "detail": detail,
    }


def local_venv(root: Path) -> dict[str, Any]:
    venv = root / ".venv"
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    ready = (
        venv.is_dir()
        and not venv.is_symlink()
        and (venv / "pyvenv.cfg").is_file()
        and python.is_file()
        and (os.name == "nt" or os.access(python, os.X_OK))
    )
    return {
        "name": "candidate_venv",
        "mode": "metadata",
        "status": "passed" if ready else "blocked",
        "detail": (
            "candidate-local .venv is present"
            if ready
            else "candidate-local .venv is missing or incomplete"
        ),
    }


def local_mypy(root: Path) -> dict[str, Any]:
    executable = root / ".venv" / ("Scripts/mypy.exe" if os.name == "nt" else "bin/mypy")
    ready = executable.is_file() and (os.name == "nt" or os.access(executable, os.X_OK))
    return {
        "name": "candidate_mypy",
        "mode": "metadata",
        "status": "passed" if ready else "blocked",
        "detail": (
            "candidate-local mypy executable is present"
            if ready
            else "candidate-local mypy executable is missing or not executable"
        ),
    }


def frontend_tools() -> dict[str, Any]:
    missing = [name for name in ("node", "npm") if shutil.which(name) is None]
    return {
        "name": "frontend_tools",
        "mode": "metadata",
        "status": "blocked" if missing else "passed",
        "detail": (
            "missing required full-gate frontend tool(s): " + ", ".join(missing)
            if missing
            else "node and npm are available"
        ),
        "missing": missing,
    }


def python_312_available() -> bool:
    return sys.version_info[:2] == (3, 12)


def mypy_covers_tests(command: tuple[str, ...]) -> bool:
    try:
        mypy = command.index("mypy")
    except ValueError:
        return False
    return "tests" in command[mypy + 1 :]


def mutation_selection(root: Path) -> dict[str, Any]:
    """Describe the canonical backend mutation scope without changing gate selection."""
    environment_ref = os.environ.get("ALPHA_GATE_BASE")
    base_source = "environment" if environment_ref is not None else "default"
    requested_ref = environment_ref if environment_ref is not None else "origin/main"
    ref_result = _git(
        root,
        "rev-parse",
        "--verify",
        "--quiet",
        "--end-of-options",
        f"{requested_ref}^{{commit}}",
    )
    resolved_ref = ref_result.stdout.strip() if ref_result.returncode == 0 else None
    if ref_result.returncode == 0 and resolved_ref:
        ref_status = "available"
    elif ref_result.returncode == 1:
        ref_status = "unavailable"
    else:
        ref_status = "unknown"

    git_results: list[tuple[tuple[str, ...], subprocess.CompletedProcess[str]]] = []

    def bounded_git(git_root: Path, *args: str, check: bool = False) -> str:
        result = _git(git_root, *args)
        git_results.append((args, result))
        if check and result.returncode:
            raise RuntimeError("bounded Git check failed")
        return result.stdout

    try:
        paths = gate_components.changed_paths(root, git_runner=bounded_git)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        paths = None
        selection_error = True
    else:
        selection_error = False

    merge_result = next(
        (result for args, result in git_results if args and args[0] == "merge-base"),
        None,
    )
    merge_base = (
        merge_result.stdout.strip()
        if merge_result is not None and merge_result.returncode == 0
        else None
    )
    if merge_result is not None and merge_result.returncode == 0 and merge_base:
        merge_status = "available"
    elif merge_result is not None and (merge_result.returncode == 1 or ref_status == "unavailable"):
        merge_status = "unavailable"
    else:
        merge_status = "unknown"
    path_checks_failed = any(
        result.returncode != 0
        for args, result in git_results
        if args and args[0] in {"diff", "ls-files"}
    )

    unknown = (
        selection_error
        or ref_status == "unknown"
        or merge_status == "unknown"
        or path_checks_failed
        or (merge_status == "available" and paths is None)
        or (ref_status == "unavailable" and merge_status == "available")
    )
    if unknown:
        selection_mode = "unknown"
        selected_targets: list[str] | None = None
    elif paths is None:
        selection_mode = "conservative_fallback"
        selected_targets = gate_components.mutation_targets(root, None)
    else:
        selection_mode = "exact_diff"
        selected_targets = gate_components.mutation_targets(root, paths)

    if selected_targets is None:
        status = "unverified"
        selection_scope = "unknown"
        all_quant_selection = None
        warning_type = "mutation_selection_unknown"
        detail = "Git could not establish the canonical mutation target set"
    else:
        selected_count = len(selected_targets)
        if selection_mode == "conservative_fallback":
            status = "warning"
            selection_scope = "all_quant_modules"
            all_quant_selection = True
            warning_type = (
                "missing_default_base"
                if base_source == "default" and ref_status == "unavailable"
                else (
                    "invalid_explicit_base"
                    if base_source == "environment" and ref_status == "unavailable"
                    else "missing_merge_base"
                )
            )
            requested = "the empty ALPHA_GATE_BASE" if not requested_ref else repr(requested_ref)
            reason = (
                f"requested ref {requested} is unavailable"
                if ref_status == "unavailable"
                else "the requested ref has no merge base with HEAD"
            )
            detail = (
                f"{reason}; canonical mutation selection conservatively falls back to all "
                f"{selected_count} quant source module(s)"
            )
        else:
            all_targets = gate.all_quant_source_modules(root)
            all_quant_selection = bool(all_targets) and selected_count == len(all_targets)
            selection_scope = (
                "all_quant_modules"
                if all_quant_selection
                else "changed_quant_modules"
                if selected_count
                else "none"
            )
            status = "passed"
            warning_type = None
            if all_quant_selection:
                detail = (
                    f"exact diff selects all {selected_count} quant source modules; "
                    "this is an exact all-quant selection, not a missing-base fallback"
                )
            else:
                detail = f"exact diff selects {selected_count} quant source module(s)"

    result: dict[str, Any] = {
        "name": "mutation_selection",
        "mode": "metadata",
        "status": status,
        "detail": detail,
        "base_source": base_source,
        "requested_ref": requested_ref,
        "ref_status": ref_status,
        "resolved_ref": resolved_ref,
        "merge_base_status": merge_status,
        "merge_base": merge_base,
        "selection_mode": selection_mode,
        "selection_scope": selection_scope,
        "selected_target_count": None if selected_targets is None else len(selected_targets),
        "all_quant_selection": all_quant_selection,
    }
    if warning_type:
        result["warning_type"] = warning_type
    if selection_mode in {"conservative_fallback", "unknown"}:
        result["blocks_preflight"] = True
    return result


def freshness_index_alignment(root: Path) -> dict[str, Any]:
    """Check only the index alignment of the canonical frontend freshness pathspecs."""
    freshness_names = {"API freshness", "SPA freshness"}
    try:
        steps = gate_components.component_steps(root, "frontend")
    except (OSError, RuntimeError, ValueError):
        steps = []
    targets: list[dict[str, str]] = []
    seen_steps: set[str] = set()
    for name, cwd, command in steps:
        if name not in freshness_names:
            continue
        if name in seen_steps:
            return {
                "name": "freshness_index_alignment",
                "mode": "metadata",
                "status": "unverified",
                "issue_type": "freshness_scope_unknown",
                "blocks_preflight": True,
                "detail": f"canonical {name} freshness step is configured more than once",
            }
        seen_steps.add(name)
        if command[:3] != ["git", "diff", "--exit-code"] or "--" not in command:
            return {
                "name": "freshness_index_alignment",
                "mode": "metadata",
                "status": "unverified",
                "issue_type": "freshness_scope_unknown",
                "blocks_preflight": True,
                "detail": f"canonical {name} step does not expose a bounded Git pathspec",
            }
        try:
            cwd_relative = cwd.resolve().relative_to(root.resolve())
        except ValueError:
            return {
                "name": "freshness_index_alignment",
                "mode": "metadata",
                "status": "unverified",
                "issue_type": "freshness_scope_unknown",
                "blocks_preflight": True,
                "detail": f"canonical {name} step is outside the candidate root",
            }
        separator = command.index("--")
        for pathspec in command[separator + 1 :]:
            relative = (cwd_relative / pathspec).as_posix()
            targets.append({"step": name, "pathspec": relative})

    missing_steps = sorted(freshness_names - seen_steps)
    if missing_steps:
        return {
            "name": "freshness_index_alignment",
            "mode": "metadata",
            "status": "unverified",
            "issue_type": "freshness_scope_unknown",
            "blocks_preflight": True,
            "missing_steps": missing_steps,
            "detail": "canonical frontend freshness step(s) unavailable: "
            + ", ".join(missing_steps),
        }
    if not targets:
        return {
            "name": "freshness_index_alignment",
            "mode": "metadata",
            "status": "unverified",
            "issue_type": "freshness_scope_unknown",
            "blocks_preflight": True,
            "detail": "canonical frontend freshness pathspecs are unavailable",
        }

    pathspecs = list(dict.fromkeys(target["pathspec"] for target in targets))
    tracked = _git(root, "ls-files", "-z", "--", *pathspecs)
    if tracked.returncode:
        return {
            "name": "freshness_index_alignment",
            "mode": "metadata",
            "status": "unverified",
            "issue_type": "freshness_scope_unknown",
            "blocks_preflight": True,
            "pathspecs": pathspecs,
            "detail": "could not list tracked files under canonical freshness paths",
        }
    tracked_paths = sorted(set(filter(None, tracked.stdout.split("\0"))))
    missing_pathspecs = [
        pathspec
        for pathspec in pathspecs
        if not any(
            path == pathspec or path.startswith(f"{pathspec.rstrip('/')}/")
            for path in tracked_paths
        )
    ]
    missing_paths = [
        path
        for path in tracked_paths
        if _has_symlink_component(root, path) or not (root / path).is_file()
    ]
    if missing_pathspecs or missing_paths:
        missing = sorted(set(missing_pathspecs) | set(missing_paths))
        return {
            "name": "freshness_index_alignment",
            "mode": "metadata",
            "status": "blocked",
            "issue_type": "missing_freshness_target",
            "blocks_preflight": True,
            "pathspecs": pathspecs,
            "missing_paths": missing,
            "detail": (
                "canonical frontend freshness targets are absent from the candidate checkout: "
                + ", ".join(missing)
            ),
        }

    changed = _git(root, "diff", "--name-only", "-z", "--", *pathspecs)
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "-z", "--", *pathspecs)
    if changed.returncode or untracked.returncode:
        return {
            "name": "freshness_index_alignment",
            "mode": "metadata",
            "status": "unverified",
            "issue_type": "freshness_scope_unknown",
            "blocks_preflight": True,
            "pathspecs": pathspecs,
            "detail": "could not compare canonical freshness paths with the Git index",
        }
    changed_paths = sorted(set(filter(None, changed.stdout.split("\0"))))
    untracked_paths = sorted(set(filter(None, untracked.stdout.split("\0"))))
    mismatches = sorted(set(changed_paths) | set(untracked_paths))
    if mismatches:
        return {
            "name": "freshness_index_alignment",
            "mode": "metadata",
            "status": "warning",
            "issue_type": "index_setup",
            "blocks_preflight": True,
            "pathspecs": pathspecs,
            "tracked_path_count": len(tracked_paths),
            "changed_paths": changed_paths,
            "untracked_paths": untracked_paths,
            "detail": (
                "canonical freshness compares the working tree with the Git index; "
                "stage intended generated outputs before gating. This index-setup warning "
                "is not evidence of stale generated output"
            ),
        }
    return {
        "name": "freshness_index_alignment",
        "mode": "metadata",
        "status": "passed",
        "issue_type": None,
        "blocks_preflight": False,
        "pathspecs": pathspecs,
        "tracked_path_count": len(tracked_paths),
        "changed_paths": [],
        "untracked_paths": [],
        "detail": (
            "working tree matches the Git index for canonical frontend freshness paths; "
            "this does not verify generated output bytes"
        ),
    }


def atlas_freshness(
    root: Path,
    *,
    python_executable: str = sys.executable,
    python_version: tuple[int, int] = sys.version_info[:2],
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    step = next(
        (step for step in gate_components.component_steps(root, "atlas") if step[0] == "freshness"),
        None,
    )
    if step is None:
        return {
            "name": "atlas_freshness",
            "mode": "executed",
            "status": "blocked",
            "issue_type": "freshness_step_missing",
            "detail": "Atlas freshness step is not configured",
        }
    _, cwd, canonical = step
    if python_version != (3, 12):
        return {
            "name": "atlas_freshness",
            "mode": "executed",
            "status": "unverified",
            "issue_type": "environment_unavailable",
            "detail": "Atlas freshness needs an already available Python 3.12 interpreter",
        }
    command = [python_executable, "-B", *canonical[3:]]
    env = {
        "PATH": os.environ.get("PATH", os.defpath),
        "PYTHONPATH": str(cwd / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
    }
    try:
        result = runner(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "name": "atlas_freshness",
            "mode": "executed",
            "status": "unverified",
            "issue_type": "freshness_execution_unknown",
            "detail": f"Atlas freshness could not run ({type(exc).__name__})",
        }
    if result.returncode == 0:
        return {
            "name": "atlas_freshness",
            "mode": "executed",
            "status": "passed",
            "issue_type": None,
            "detail": "generated Atlas outputs are fresh",
        }
    output = result.stdout + result.stderr
    stale = "stale generated atlas output" in output
    detail = (
        "generated Atlas outputs are stale"
        if stale
        else f"Atlas freshness failed (exit {result.returncode})"
    )
    return {
        "name": "atlas_freshness",
        "mode": "executed",
        "status": "blocked",
        "issue_type": "generated_drift" if stale else "freshness_execution",
        "detail": detail,
    }


def _candidate_identity(root: Path) -> dict[str, Any]:
    head = _git(root, "rev-parse", "--verify", "HEAD")
    branch = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    return {
        "root": str(root),
        "head": head.stdout.strip() if head.returncode == 0 else None,
        "branch": branch.stdout.strip() if branch.returncode == 0 else "detached",
    }


def root_resolution_failure_report(start: Path, error: Exception) -> tuple[int, dict[str, Any]]:
    root = start.resolve()
    report = {
        "schema_version": 1,
        "ok": False,
        "candidate": {"root": str(root), "head": None, "branch": "unknown"},
        "resources": _resources(root),
        "checks": [
            {
                "name": "candidate_root",
                "mode": "metadata",
                "status": "blocked",
                "detail": f"Git could not resolve the candidate root ({type(error).__name__})",
            }
        ],
        "blockers": ["candidate_root"],
    }
    return 1, report


def _resources(root: Path) -> dict[str, int | None]:
    total_memory = available_memory = None
    if hasattr(os, "sysconf"):
        try:
            page_size = int(os.sysconf("SC_PAGE_SIZE"))
            total_memory = page_size * int(os.sysconf("SC_PHYS_PAGES"))
            available_memory = page_size * int(os.sysconf("SC_AVPHYS_PAGES"))
        except (OSError, ValueError):
            total_memory = available_memory = None
    disk_free: int | None = None
    disk_total: int | None = None
    try:
        disk = shutil.disk_usage(root)
        disk_free = disk.free
        disk_total = disk.total
    except OSError:
        pass
    return {
        "logical_cpus": os.cpu_count(),
        "memory_total_bytes": total_memory,
        "memory_available_bytes": available_memory,
        "disk_free_bytes": disk_free,
        "disk_total_bytes": disk_total,
    }


def run_preflight(root: Path) -> tuple[int, dict[str, Any]]:
    root = root.resolve()
    checks: list[dict[str, Any]] = []
    try:
        valid_size, total = manual_size_check(root)
        checks.append(
            {
                "name": "manual_size",
                "mode": "metadata",
                "status": "passed" if valid_size else "blocked",
                "detail": f"CLAUDE.md + AGENTS.md: {total}/{MANUAL_SIZE_LIMIT} bytes",
            }
        )
    except OSError:
        checks.append(
            {
                "name": "manual_size",
                "mode": "metadata",
                "status": "blocked",
                "detail": "manual files are missing or not regular files",
            }
        )
    checks.append(public_prerequisites(root))
    checks.append(git_object_storage(root))
    checks.append(local_venv(root))
    checks.append(local_mypy(root))
    checks.append(frontend_tools())
    checks.append(
        {
            "name": "python_runtime",
            "mode": "metadata",
            "status": "passed" if python_312_available() else "blocked",
            "detail": (
                f"Python {sys.version_info.major}.{sys.version_info.minor} ({sys.executable})"
            ),
        }
    )
    uv = shutil.which("uv")
    checks.append(
        {
            "name": "uv",
            "mode": "metadata",
            "status": "passed" if uv else "blocked",
            "detail": "uv is available" if uv else "uv is not available on PATH",
        }
    )
    checks.append(
        {
            "name": "full_gate_mypy_scope",
            "mode": "scope_only",
            "status": (
                "scope_only" if mypy_covers_tests(gate.FULL_GATE_MYPY_COMMAND) else "blocked"
            ),
            "detail": (
                "canonical full-gate mypy command includes tests; this check does not run mypy"
                if mypy_covers_tests(gate.FULL_GATE_MYPY_COMMAND)
                else "canonical full-gate mypy does not cover tests"
            ),
        }
    )
    checks.append(
        {
            "name": "full_gate_mypy_execution",
            "mode": "not_run",
            "status": "not_run",
            "detail": "read-only preflight does not execute mypy",
        }
    )
    try:
        harness_problems = gate.lint_harness(root)
    except (OSError, UnicodeError):
        harness_problems = ["canonical harness lint could not read its public inputs"]
    checks.append(
        {
            "name": "harness_lint",
            "mode": "executed",
            "status": "blocked" if harness_problems else "passed",
            "detail": (
                "; ".join(harness_problems) if harness_problems else "canonical harness lint passed"
            ),
        }
    )
    checks.append(mutation_selection(root))
    checks.append(freshness_index_alignment(root))
    checks.append(atlas_freshness(root))
    blockers = [
        check["name"]
        for check in checks
        if check["status"] in {"blocked", "unverified"} or check.get("blocks_preflight")
    ]
    warnings = [
        {
            "name": check["name"],
            "issue_type": check.get("issue_type", check.get("warning_type")),
            "detail": check["detail"],
        }
        for check in checks
        if check["status"] == "warning"
    ]
    report = {
        "schema_version": 1,
        "ok": not blockers,
        "candidate": _candidate_identity(root),
        "resources": _resources(root),
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
    }
    return (0 if not blockers else 1), report


def render_report(report: dict[str, Any]) -> str:
    candidate = report["candidate"]
    state = "READY" if report["ok"] else "BLOCKED"
    lines = [
        f"Qualification preflight: {state}",
        f"Candidate: {candidate['branch']} @ {candidate['head'] or 'unknown'} "
        f"({candidate['root']})",
    ]
    for check in report["checks"]:
        status = str(check["status"]).upper()
        mode = str(check.get("mode", "unknown")).upper()
        lines.append(f"{status} [{mode}]: {check['name']}: {check['detail']}")
        missing = check.get("missing", [])
        if missing:
            lines.append("  missing: " + ", ".join(missing))
    resources = report["resources"]
    lines.append(
        "Resources: "
        f"CPU={resources['logical_cpus']}, "
        f"RAM available={resources['memory_available_bytes']}, "
        f"disk free={resources['disk_free_bytes']} bytes"
    )
    return "\n".join(lines)
