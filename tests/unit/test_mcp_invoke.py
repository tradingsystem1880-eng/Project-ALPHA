"""The MCP server's subprocess core: run `alpha`, parse the run id, read the manifest.

`run_alpha` is the single seam every action tool uses. These tests monkeypatch ``subprocess.run``
so they exercise arg-building, run-id parsing, manifest reads, and fail-loud behavior without
touching the engine.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from alpha_mcp import _invoke


def _fake_completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> Any:
    return subprocess.CompletedProcess(
        args=["alpha"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _write_manifest(data_dir: Path, run_type: str, run_id: str, payload: dict[str, Any]) -> None:
    rdir = data_dir / run_type / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")


def test_run_alpha_returns_the_runs_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = "0123456789abcdef"
    _write_manifest(tmp_path, "runs", run_id, {"command": "validate", "run_id": run_id})
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: _fake_completed(f"validate SPY -> run {run_id}: PASS"),
    )
    out = _invoke.run_alpha(["validate", "SPY"], data_dir=tmp_path, run_type="runs")
    assert out == {"command": "validate", "run_id": run_id}


def test_run_alpha_reads_from_the_named_run_type_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = "abcdef0123456789"
    _write_manifest(tmp_path, "propfirm", run_id, {"command": "propfirm"})
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: _fake_completed(f"propfirm AAPL -> run {run_id}: topstep"),
    )
    out = _invoke.run_alpha(["propfirm", "run", "AAPL"], data_dir=tmp_path, run_type="propfirm")
    assert out["command"] == "propfirm"


def test_run_alpha_without_run_type_returns_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _fake_completed("pulled 252 bars for AAPL")
    )
    out = _invoke.run_alpha(["data", "pull", "AAPL"], data_dir=tmp_path, run_type=None)
    assert out == {"stdout": "pulled 252 bars for AAPL"}


def test_run_alpha_raises_on_nonzero_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: _fake_completed(stderr="train_size 60 < warmup floor 274", returncode=2),
    )
    with pytest.raises(RuntimeError, match="warmup floor"):
        _invoke.run_alpha(["validate", "SPY"], data_dir=tmp_path, run_type="runs")


def test_run_alpha_raises_when_no_run_id_in_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _fake_completed("something unexpected"))
    with pytest.raises(RuntimeError, match="run id"):
        _invoke.run_alpha(["validate", "SPY"], data_dir=tmp_path, run_type="runs")


def test_run_alpha_invokes_the_cli_with_data_dir_in_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def fake_run(argv: list[str], **kwargs: Any) -> Any:
        captured["argv"] = argv
        captured["env"] = kwargs.get("env")
        return _fake_completed("data pull done")

    monkeypatch.setattr(subprocess, "run", fake_run)
    _invoke.run_alpha(["data", "pull", "AAPL"], data_dir=tmp_path, run_type=None)
    assert captured["argv"][0] == "alpha"
    assert captured["argv"][1:] == ["data", "pull", "AAPL"]
    assert captured["env"]["ALPHA_DATA_DIR"] == str(
        tmp_path
    )  # subprocess shares the server's store
