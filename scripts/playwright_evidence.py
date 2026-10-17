"""Allocate focused Playwright outputs; optionally copy one stopped run's evidence.

Listing/copy receipts are not authenticated execution or acceptance evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def safe_path(path: Path) -> Path:
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Expected absolute path without traversal: {path}")
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError(f"Links are not permitted: {path}")
    return path


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def selection(
    report: Any,
    native_argv: list[str],
    frontend: Path,
    test_file: Path,
    project: str,
    expected_ids: list[str],
) -> dict[str, Any]:
    if not isinstance(report, dict) or report.get("errors") != []:
        raise ValueError("Invalid listing or listing errors")
    config = report.get("config", {})
    if (
        not isinstance(config, dict)
        or config.get("configFile") != str(frontend / "playwright.config.ts")
        or config.get("rootDir") != str(frontend / "e2e")
        or config.get("argv", [])[1:] != native_argv
    ):
        raise ValueError("Listing config/argv does not match this preflight")
    intended: list[dict[str, str]] = []
    additional: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def visit(suites: Any) -> None:
        if not isinstance(suites, list):
            raise ValueError("Invalid listing suites")
        for suite in suites:
            if not isinstance(suite, dict) or not isinstance(suite.get("specs", []), list):
                raise ValueError("Invalid listing suite")
            for spec in suite.get("specs", []):
                if (
                    not isinstance(spec, dict)
                    or not all(
                        isinstance(spec.get(k), str) and spec[k] for k in ("id", "file", "title")
                    )
                    or not isinstance(spec.get("tests"), list)
                ):
                    raise ValueError("Invalid listing spec")
                file = Path(spec["file"])
                if file.is_absolute() or ".." in file.parts:
                    raise ValueError("Invalid listed file path")
                for test in spec["tests"]:
                    if not isinstance(test, dict) or not isinstance(test.get("projectName"), str):
                        raise ValueError("Invalid listed project")
                    name = test["projectName"]
                    identity = (name, spec["id"])
                    if identity in seen:
                        raise ValueError("Duplicate listed case")
                    seen.add(identity)
                    case = {
                        "project": name,
                        "id": spec["id"],
                        "file": str(file),
                        "title": spec["title"],
                    }
                    if name == project:
                        if safe_path(frontend / "e2e" / file) != test_file:
                            raise ValueError("Requested project selected a different file")
                        intended.append(case)
                    else:
                        additional.append(case)
            visit(suite.get("suites", []))

    visit(report.get("suites"))
    if not intended or not set(expected_ids).issubset({case["id"] for case in intended}):
        raise ValueError("Zero intended cases or missing explicitly requested IDs")
    return {"intended_cases": intended, "additional_cases": additional}


def prepare(
    output_parent: Path,
    project: str,
    file: str,
    grep: str | None,
    expected_ids: list[str],
) -> dict[str, Any]:
    frontend = ROOT / "apps/alpha-web/frontend"
    relative = Path(file)
    if (
        relative.is_absolute()
        or relative.parent != Path("e2e")
        or not relative.name.endswith(".spec.ts")
    ):
        raise ValueError("Select one relative public e2e/*.spec.ts file")
    test_file = safe_path(frontend / relative)
    parent = safe_path(output_parent)
    if not parent.is_dir() or parent.is_relative_to(frontend) or not test_file.is_file():
        raise ValueError("Require an existing test and output parent outside frontend")
    if not project or not expected_ids or any(not item for item in expected_ids):
        raise ValueError("Project and at least one expected ID are required")
    run = Path(tempfile.mkdtemp(prefix="playwright-", dir=parent))
    output = run / "artifacts"
    output.mkdir(mode=0o700)
    native = [
        str(frontend / "node_modules/.bin/playwright"),
        "test",
        "^" + re.escape(str(test_file)) + "$",
        "--config",
        str(frontend / "playwright.config.ts"),
        "--project",
        project,
        "--output",
        str(output),
    ]
    if grep is not None:
        native += ["--grep", grep]
    owner = [sys.executable, str(ROOT / "scripts/run_owned_test.py"), "--"]
    listing_argv = native + ["--list", "--reporter=json"]
    receipt: dict[str, Any] = {
        "run_dir": str(run),
        "output_dir": str(output),
        "stdout_log": str(run / "stdout.log"),
        "stderr_log": str(run / "stderr.log"),
        "cwd": str(frontend),
        "expected_ids": expected_ids,
        "list_argv": owner + listing_argv,
        "test_argv": owner + native,
    }
    try:
        config = safe_path(frontend / "playwright.config.ts")
        receipt.update(
            config_sha256=sha256(config),
            lock_sha256=sha256(safe_path(frontend / "package-lock.json")),
            playwright_version=json.loads(
                (frontend / "node_modules/@playwright/test/package.json").read_text()
            )["version"],
        )
        proc = subprocess.run(owner + listing_argv, cwd=frontend, capture_output=True)
        (run / "listing.json").write_bytes(proc.stdout)
        (run / "listing.stderr.log").write_bytes(proc.stderr)
        receipt["list_exit"] = proc.returncode
        if proc.returncode:
            raise ValueError(f"Listing exited {proc.returncode}")
        receipt.update(
            selection(
                json.loads(proc.stdout), listing_argv, frontend, test_file, project, expected_ids
            )
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        receipt["preflight_error"] = str(exc)
        write_json(run / "run.json", receipt)
        raise ValueError(f"Preflight failed; evidence retained at {run}: {exc}") from exc
    write_json(run / "run.json", receipt)
    return {
        "run_dir": str(run),
        "output_dir": str(output),
        "cwd": str(frontend),
        "stdout_log": str(run / "stdout.log"),
        "stderr_log": str(run / "stderr.log"),
        "test_argv": owner + native,
    }


def copy_file(source: Path, destination: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    size = 0
    with os.fdopen(os.open(source, os.O_RDONLY | os.O_NOFOLLOW), "rb") as src:
        info = os.fstat(src.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError(f"Only regular, unlinked files permitted: {source}")
        with destination.open("xb") as dst:
            while block := src.read(1024 * 1024):
                dst.write(block)
                digest.update(block)
                size += len(block)
    if destination.stat().st_size != size or sha256(destination) != digest.hexdigest():
        raise ValueError(f"Copied size/hash mismatch: {destination}")
    return {"size": size, "sha256": digest.hexdigest()}


def export_run(source: Path, destination: Path, test_exit: int, stopped: bool) -> dict[str, Any]:
    source, destination = safe_path(source), safe_path(destination)
    if not stopped or not source.is_dir():
        raise ValueError("Export requires one stopped prepared run")
    run_record = safe_path(source / "run.json")
    if not run_record.is_file() or run_record.stat().st_nlink != 1:
        raise ValueError("Prepared run metadata must be a regular unlinked file")
    metadata = json.loads(run_record.read_text())
    if not isinstance(metadata, dict) or metadata.get("run_dir") != str(source):
        raise ValueError("Not a prepared run directory")
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError("Source/destination overlap")
    destination.mkdir(mode=0o700)
    try:
        files = []

        def copy_directory(directory: Path) -> None:
            # Scan errors must propagate; glob can silently omit unreadable subtrees.
            with os.scandir(directory) as entries:
                paths = sorted(Path(entry.path) for entry in entries)
            for path in paths:
                safe_path(path)
                target = destination / path.relative_to(source)
                info = path.lstat()
                if stat.S_ISDIR(info.st_mode):
                    target.mkdir(mode=0o700)
                    copy_directory(path)
                elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                    files.append({"path": str(path.relative_to(source)), **copy_file(path, target)})
                else:
                    raise ValueError(f"Links/special files not permitted: {path}")

        copy_directory(source)
        result = {"test_exit": test_exit, "test_result": "passed" if test_exit == 0 else "failed"}
        write_json(destination / "export-manifest.json", {"files": files, **result})
    except (OSError, ValueError) as exc:
        raise type(exc)(
            f"Export failed; originals/partial retained at {destination}: {exc}"
        ) from exc
    return {"destination": str(destination), "copy_result": "verified", **result}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser(
        "prepare", help="Fresh output and listing only; no browser execution"
    )
    prep.add_argument("--output-parent", type=Path, required=True)
    prep.add_argument("--project", required=True)
    prep.add_argument("--file", required=True)
    prep.add_argument("--grep")
    prep.add_argument("--expect-id", action="append", required=True)
    export = commands.add_parser("export", help="Copy one stopped run; status is caller-reported")
    export.add_argument("--run-dir", type=Path, required=True)
    export.add_argument("--destination", type=Path, required=True)
    export.add_argument("--test-exit", type=int, required=True)
    export.add_argument("--stopped", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare(args.output_parent, args.project, args.file, args.grep, args.expect_id)
        else:
            result = export_run(args.run_dir, args.destination, args.test_exit, args.stopped)
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
