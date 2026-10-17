"""Synthetic selection and file-isolation checks; no browser or private artifacts."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest


@pytest.fixture
def helper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    script = Path(__file__).parents[2] / "scripts/playwright_evidence.py"
    spec = importlib.util.spec_from_file_location("playwright_evidence_test", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path / "checkout"
    frontend = root / "apps/alpha-web/frontend"
    (frontend / "e2e").mkdir(parents=True)
    (frontend / "e2e/dialog.spec.ts").write_text("// synthetic public test\n")
    (frontend / "playwright.config.ts").write_text("// synthetic config\n")
    (frontend / "package-lock.json").write_text("{}\n")
    package = frontend / "node_modules/@playwright/test/package.json"
    package.parent.mkdir(parents=True)
    package.write_text('{"version": "1.61.1"}\n')
    monkeypatch.setattr(module, "ROOT", root)
    return module


@pytest.fixture
def listing(helper: ModuleType, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    frontend = helper.ROOT / "apps/alpha-web/frontend"
    report: dict[str, Any] = {
        "config": {
            "configFile": str(frontend / "playwright.config.ts"),
            "rootDir": str(frontend / "e2e"),
        },
        "errors": [],
        "suites": [
            {
                "specs": [
                    {
                        "id": "case-one",
                        "file": "dialog.spec.ts",
                        "title": "case",
                        "tests": [{"projectName": "chromium-minimum"}],
                    }
                ]
            }
        ],
        "stats": {"expected": 0, "skipped": 1},
    }

    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        assert kwargs["cwd"] == frontend
        assert argv[1] == str(helper.ROOT / "scripts/run_owned_test.py")
        native = argv[3:]
        assert native[-2:] == ["--list", "--reporter=json"]
        assert native[2].startswith("^") and native[2].endswith("$")
        report["config"].setdefault("argv", ["node", *native])
        return subprocess.CompletedProcess(argv, 0, json.dumps(report).encode(), b"")

    monkeypatch.setattr(helper.subprocess, "run", run)
    return report


def prepare(helper: ModuleType, parent: Path) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        helper.prepare(parent, "chromium-minimum", "e2e/dialog.spec.ts", "case", ["case-one"]),
    )


def test_prepare_keeps_dependency_cases_separate_and_counts_specs(
    helper: ModuleType, listing: dict[str, Any], tmp_path: Path
) -> None:
    listing["suites"][0]["specs"][0]["tests"].append({"projectName": "dependency"})
    result = prepare(helper, tmp_path)
    receipt = json.loads((Path(result["run_dir"]) / "run.json").read_text())
    assert len(receipt["intended_cases"]) == len(receipt["additional_cases"]) == 1
    assert receipt["intended_cases"][0]["id"] == "case-one"
    assert receipt["list_exit"] == 0
    assert "--list" not in result["test_argv"]


@pytest.mark.parametrize(
    "problem", ["missing-id", "zero-intended", "errors", "config", "argv", "file"]
)
def test_prepare_rejects_wrong_selection_and_retains_listing(
    helper: ModuleType, listing: dict[str, Any], tmp_path: Path, problem: str
) -> None:
    spec = listing["suites"][0]["specs"][0]
    if problem == "missing-id":
        spec["id"] = "wrong-case"
    elif problem == "zero-intended":
        spec["tests"] = [{"projectName": "dependency"}]
    elif problem == "errors":
        listing["errors"] = [{"message": "synthetic error"}]
    elif problem == "config":
        listing["config"]["configFile"] = "/different/config.ts"
    elif problem == "argv":
        listing["config"]["argv"] = ["node", "different"]
    else:
        spec["file"] = "dialogXspec.ts"
    with pytest.raises(ValueError):
        prepare(helper, tmp_path)
    runs = list(tmp_path.glob("playwright-*"))
    assert len(runs) == 1
    assert (runs[0] / "listing.json").is_file()
    assert json.loads((runs[0] / "run.json").read_text())["preflight_error"]


def test_prepare_new_invocation_never_overwrites_earlier_trace(
    helper: ModuleType, listing: dict[str, Any], tmp_path: Path
) -> None:
    first = prepare(helper, tmp_path)
    trace = Path(first["output_dir"]) / "trace.zip"
    trace.write_bytes(b"first synthetic trace")
    # Each native invocation has a different output argument in its listing receipt.
    listing["config"].pop("argv")
    second = prepare(helper, tmp_path)
    (Path(second["output_dir"]) / "trace.zip").write_bytes(b"second synthetic trace")
    assert first["output_dir"] != second["output_dir"]
    assert trace.read_bytes() == b"first synthetic trace"


def test_prepare_nonzero_listing_is_not_success(
    helper: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        helper.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a, 1, b"{}", b"failure"),
    )
    with pytest.raises(ValueError):
        prepare(helper, tmp_path)
    assert next(tmp_path.glob("playwright-*/listing.stderr.log")).read_bytes() == b"failure"


@pytest.fixture
def stopped_run(tmp_path: Path) -> Path:
    run = tmp_path / "playwright-synthetic"
    (run / "artifacts").mkdir(parents=True)
    (run / "run.json").write_text(json.dumps({"run_dir": str(run)}))
    (run / "artifacts/trace.zip").write_bytes(b"synthetic trace bytes")
    return run


def test_export_verified_bytes_keep_failed_test_status(
    helper: ModuleType, stopped_run: Path, tmp_path: Path
) -> None:
    destination = tmp_path / "export"
    result = helper.export_run(stopped_run, destination, 1, True)
    assert result["test_exit"] == 1 and result["test_result"] == "failed"
    manifest = json.loads((destination / "export-manifest.json").read_text())
    assert manifest["test_result"] == "failed"
    for item in manifest["files"]:
        copied = destination / item["path"]
        assert copied.read_bytes() == (stopped_run / item["path"]).read_bytes()
        assert copied.stat().st_size == item["size"]
        assert helper.sha256(copied) == item["sha256"]
    with pytest.raises((ValueError, OSError)):
        helper.export_run(stopped_run, destination, 1, True)


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo", "linked-parent"])
def test_export_rejects_links_and_special_files(
    helper: ModuleType, stopped_run: Path, tmp_path: Path, kind: str
) -> None:
    destination = tmp_path / "export"
    if kind == "symlink":
        (stopped_run / "link").symlink_to(stopped_run / "artifacts/trace.zip")
    elif kind == "hardlink":
        os.link(stopped_run / "artifacts/trace.zip", stopped_run / "link")
    elif kind == "fifo":
        os.mkfifo(stopped_run / "pipe")
    else:
        (tmp_path / "linked").symlink_to(tmp_path, target_is_directory=True)
        destination = tmp_path / "linked/export"
    with pytest.raises((ValueError, OSError)):
        helper.export_run(stopped_run, destination, 1, True)
    assert (stopped_run / "artifacts/trace.zip").read_bytes() == b"synthetic trace bytes"


def test_export_copy_failure_retains_source_and_partial(
    helper: ModuleType, stopped_run: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = helper.copy_file
    count = 0

    def fail_second(source: Path, target: Path) -> dict[str, Any]:
        nonlocal count
        count += 1
        if count == 2:
            target.write_bytes(b"partial bytes")
            raise OSError("synthetic copy interruption")
        return cast(dict[str, Any], original(source, target))

    monkeypatch.setattr(helper, "copy_file", fail_second)
    destination = tmp_path / "export"
    before = {
        p.relative_to(stopped_run): p.read_bytes() for p in stopped_run.rglob("*") if p.is_file()
    }
    with pytest.raises(OSError, match="retained"):
        helper.export_run(stopped_run, destination, 1, True)
    assert {
        p.relative_to(stopped_run): p.read_bytes() for p in stopped_run.rglob("*") if p.is_file()
    } == before
    assert (destination / "artifacts/trace.zip").read_bytes() == b"synthetic trace bytes"
    assert (destination / "run.json").read_bytes() == b"partial bytes"
    assert not (destination / "export-manifest.json").exists()


def test_export_hash_mismatch_and_active_writer_attestation_fail(
    helper: ModuleType, stopped_run: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ValueError):
        helper.export_run(stopped_run, tmp_path / "active", 1, False)
    monkeypatch.setattr(helper, "sha256", lambda path: "wrong hash")
    with pytest.raises(ValueError, match="retained"):
        helper.export_run(stopped_run, tmp_path / "export", 1, True)
    assert (stopped_run / "artifacts/trace.zip").read_bytes() == b"synthetic trace bytes"


def test_export_cli_separates_copy_exit_from_failed_test(
    helper: ModuleType, stopped_run: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = [
        "export",
        "--run-dir",
        str(stopped_run),
        "--destination",
        str(tmp_path / "export"),
        "--test-exit",
        "1",
        "--stopped",
    ]
    assert helper.main(argv) == 0
    assert json.loads(capsys.readouterr().out)["test_result"] == "failed"
    assert helper.main(argv) == 1
    assert capsys.readouterr().err


def test_export_traversal_error_is_visible_and_keeps_partial(
    helper: ModuleType, stopped_run: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (stopped_run / "000-log").write_bytes(b"already retained")
    original = os.scandir

    def unreadable(path: Any) -> Any:
        if Path(path) == stopped_run / "artifacts":
            raise PermissionError("synthetic unreadable subtree")
        return original(path)

    monkeypatch.setattr(os, "scandir", unreadable)
    destination = tmp_path / "export"
    with pytest.raises(PermissionError, match="retained"):
        helper.export_run(stopped_run, destination, 1, True)
    assert (destination / "000-log").read_bytes() == b"already retained"
    assert (stopped_run / "artifacts/trace.zip").read_bytes() == b"synthetic trace bytes"
    assert not (destination / "export-manifest.json").exists()
