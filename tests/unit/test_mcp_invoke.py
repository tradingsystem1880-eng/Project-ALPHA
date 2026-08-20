"""The MCP server's subprocess core: run `alpha`, parse the run id, read the manifest.

`run_alpha` is the single seam every action tool uses. These tests monkeypatch ``subprocess.run``
so they exercise arg-building, run-id parsing, manifest reads, and fail-loud behavior without
touching the engine.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from alpha_cli.artifact_contract import artifact_contract
from alpha_cli.durable_lease import DurableLeaseError
from alpha_core import DataError
from alpha_mcp import _invoke, _runs


def _fake_completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> Any:
    return subprocess.CompletedProcess(
        args=["alpha"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _write_manifest(data_dir: Path, run_type: str, run_id: str, payload: dict[str, Any]) -> None:
    rdir = data_dir / run_type / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_v3_manifest(data_dir: Path, run_type: str, run_id: str) -> Path:
    rdir = data_dir / run_type / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "evidence.txt").write_text("good", encoding="utf-8")
    _write_manifest(
        data_dir,
        run_type,
        run_id,
        {
            "schema_version": 3,
            "artifact_contract_version": 3,
            "run_identity_version": 3,
            "run_id": run_id,
            "command": "test_run",
            "execution_fingerprint": "a" * 64,
            "strategy_fingerprint": None,
            "source_fingerprint": "b" * 64,
            "snapshot_id": None,
            "snapshot_hash": None,
            "artifacts": artifact_contract(rdir),
        },
    )
    return rdir


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


def test_mcp_cli_environment_excludes_parent_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_TIINGO_API_KEY", "secret-tiingo")
    monkeypatch.setenv("ALPHA_COINGECKO_API_KEY", "secret-coingecko")
    monkeypatch.setenv("QUANTPAD_API_KEY", "secret-quantpad")
    monkeypatch.setenv("ALPHA_IBKR_PAPER_ACCOUNT", "DU1234567")
    monkeypatch.setenv("ALPHA_BULK_DATA_DIR", "/Volumes/Expansion/Project-ALPHA/crypto-data")
    monkeypatch.setenv("ALPHA_BULK_VOLUME_UUID", "volume-uuid")
    monkeypatch.setenv("UNRELATED_SHELL_STATE", "must-not-cross")

    environment = _invoke._cli_environment(tmp_path)

    assert environment["ALPHA_DATA_DIR"] == str(tmp_path)
    assert environment["ALPHA_BULK_DATA_DIR"].endswith("/crypto-data")
    assert environment["ALPHA_BULK_VOLUME_UUID"] == "volume-uuid"
    assert "PATH" in environment
    assert "ALPHA_TIINGO_API_KEY" not in environment
    assert "ALPHA_COINGECKO_API_KEY" not in environment
    assert "QUANTPAD_API_KEY" not in environment
    assert "ALPHA_IBKR_PAPER_ACCOUNT" not in environment
    assert "UNRELATED_SHELL_STATE" not in environment


def test_run_alpha_uses_bounded_verified_manifest_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = "abababababababab"
    rdir = _write_v3_manifest(tmp_path, "runs", run_id)
    (rdir / "evidence.txt").write_text("evil", encoding="utf-8")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: _fake_completed(f"backtest SPY -> run {run_id}: done"),
    )
    with pytest.raises(DataError, match="hash mismatch"):
        _invoke.run_alpha(["backtest", "run", "SPY"], data_dir=tmp_path, run_type="runs")

    oversized_id = "cdcdcdcdcdcdcdcd"
    _write_manifest(
        tmp_path,
        "runs",
        oversized_id,
        {"payload": "x" * _runs.MAX_MANIFEST_BYTES},
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: _fake_completed(f"backtest SPY -> run {oversized_id}: done"),
    )
    with pytest.raises(ValueError, match="manifest exceeds"):
        _invoke.run_alpha(["backtest", "run", "SPY"], data_dir=tmp_path, run_type="runs")


def test_run_json_is_bounded_cli_projection_and_fails_on_invalid_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def fake_run(argv: list[str], **kwargs: Any) -> Any:
        captured["argv"] = argv
        captured["timeout"] = kwargs["timeout"]
        return _fake_completed('{"items":[]}')

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert _invoke.run_json(["project", "list", "--json"], data_dir=tmp_path) == {"items": []}
    assert captured["argv"] == ["alpha", "project", "list", "--json"]
    assert captured["timeout"] == 30.0

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _fake_completed("not-json"))
    with pytest.raises(RuntimeError, match="invalid JSON"):
        _invoke.run_json(["project", "list", "--json"], data_dir=tmp_path)


def test_run_json_reports_projection_timeout_and_cli_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def timeout(*args: object, **kwargs: object) -> Any:
        del args, kwargs
        raise subprocess.TimeoutExpired(["alpha"], 30)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(RuntimeError, match="projection exceeded 30s"):
        _invoke.run_json(["project", "list", "--json"], data_dir=tmp_path)

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _fake_completed(stderr="capacity denied", returncode=2),
    )
    with pytest.raises(RuntimeError, match="capacity denied"):
        _invoke.run_json(["project", "job-create", "ml_train"], data_dir=tmp_path)


def test_heavyweight_reservation_and_status_contracts_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_invoke, "run_json", lambda *args, **kwargs: [])
    with pytest.raises(RuntimeError, match="omitted its durable job id"):
        _invoke._reserve_heavyweight_job(["forecast", "run", "SPY"], data_dir=tmp_path)

    monkeypatch.setattr(_invoke, "run_json", lambda *args, **kwargs: {})
    with pytest.raises(RuntimeError, match="omitted its durable job id"):
        _invoke._reserve_heavyweight_job(["forecast", "run", "SPY"], data_dir=tmp_path)

    calls: list[list[str]] = []

    def projection(args: list[str], **kwargs: object) -> dict[str, object]:
        del kwargs
        calls.append(args)
        return {"job_id": "00000000-0000-4000-8000-000000000001"}

    monkeypatch.setattr(_invoke, "run_json", projection)
    job_id = _invoke._reserve_heavyweight_job(["forecast", "run", "SPY"], data_dir=tmp_path)
    assert job_id == "00000000-0000-4000-8000-000000000001"
    _invoke._set_heavyweight_job_status(
        job_id,
        "failed",
        data_dir=tmp_path,
        terminal_error="x" * 5000,
    )
    status_call = calls[-1]
    assert "--terminal-error" in status_call
    assert len(status_call[status_call.index("--terminal-error") + 1]) == 4096


def test_mcp_silent_heavyweight_child_heartbeats_independently_of_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    captured: dict[str, object] = {}
    original_popen = subprocess.Popen

    def popen(command: list[str], **kwargs: Any) -> subprocess.Popen[str]:
        captured["command"] = command
        captured["start_new_session"] = kwargs.get("start_new_session")
        return original_popen(
            [sys.executable, "-c", "import time; time.sleep(0.15)"],
            **kwargs,
        )

    def projection(args: list[str], **kwargs: object) -> dict[str, object]:
        del kwargs
        calls.append(args)
        if args[1:4] == ["job-event", job_id, "heartbeat"]:
            return {"job_id": job_id, "cancel_requested": False}
        return {"status": "ok"}

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(_invoke, "run_json", projection)
    monkeypatch.setattr(_invoke, "_DURABLE_HEARTBEAT_INTERVAL_S", 0.02)
    job_id = "66666666-6666-4666-8666-666666666666"

    completed = _invoke._run_action_process(
        ["forecast", "run", "SPY"],
        data_dir=tmp_path,
        durable_job_id=job_id,
    )

    assert completed.returncode == 0
    assert captured["command"] == ["alpha", "forecast", "run", "SPY"]
    assert captured["start_new_session"] is True
    heartbeats = [args for args in calls if args[1:4] == ["job-event", job_id, "heartbeat"]]
    assert len(heartbeats) >= 2
    assert all("--json" in args for args in heartbeats)


def test_mcp_heavyweight_cancellation_reaps_without_later_terminal_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    original_popen = subprocess.Popen
    job_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"

    def popen(command: list[str], **kwargs: Any) -> subprocess.Popen[str]:
        del command
        return original_popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            **kwargs,
        )

    def projection(args: list[str], **kwargs: object) -> dict[str, object]:
        del kwargs
        calls.append(args)
        if args[1:4] == ["job-event", job_id, "heartbeat"]:
            return {"job_id": job_id, "cancel_requested": True}
        return {"status": "ok"}

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(_invoke, "run_json", projection)
    monkeypatch.setattr(_invoke, "_DURABLE_HEARTBEAT_INTERVAL_S", 0.02)

    with pytest.raises(RuntimeError, match="was cancelled"):
        _invoke._run_action_process(
            ["forecast", "run", "SPY"],
            data_dir=tmp_path,
            durable_job_id=job_id,
        )

    terminal = [args[3] for args in calls if args[1:3] == ["job-status", job_id]]
    assert terminal == ["cancelled"]


def test_mcp_communicate_error_prioritizes_verified_child_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    captured: list[subprocess.Popen[str]] = []
    original_popen = subprocess.Popen
    job_id = "abababab-abab-4bab-8bab-abababababab"

    def popen(_command: list[str], **kwargs: Any) -> subprocess.Popen[str]:
        process = original_popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            **kwargs,
        )

        def communicate(*_args: object, **_kwargs: object) -> tuple[str, str]:
            raise OSError("pipe state unavailable")

        process.communicate = communicate  # type: ignore[method-assign]
        captured.append(process)
        return process

    def projection(args: list[str], **kwargs: object) -> dict[str, object]:
        del kwargs
        calls.append(args)
        if args[1:4] == ["job-event", job_id, "heartbeat"]:
            return {"job_id": job_id, "cancel_requested": False}
        return {"status": "ok"}

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(_invoke, "run_json", projection)

    with pytest.raises(DurableLeaseError, match="lease stopped while child was still alive"):
        _invoke._run_action_process(
            ["forecast", "run", "SPY"],
            data_dir=tmp_path,
            durable_job_id=job_id,
        )

    process = captured[0]
    assert process.poll() is not None
    assert [args[3] for args in calls if args[1:3] == ["job-status", job_id]] == ["failed"]
    if process.stdout is not None:
        process.stdout.close()
    if process.stderr is not None:
        process.stderr.close()


def test_heavyweight_run_failures_write_terminal_journal_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    statuses: list[tuple[str, str | None]] = []
    monkeypatch.setattr(
        _invoke,
        "_reserve_heavyweight_job",
        lambda *args, **kwargs: "00000000-0000-4000-8000-000000000001",
    )

    def status(
        job_id: str | None,
        state: str,
        *,
        data_dir: Path,
        result_run_id: str | None = None,
        terminal_error: str | None = None,
    ) -> None:
        del job_id, data_dir, result_run_id
        statuses.append((state, terminal_error))

    monkeypatch.setattr(_invoke, "_set_heavyweight_job_status", status)

    monkeypatch.setattr(
        _invoke,
        "_run_action_process",
        lambda *args, **kwargs: _fake_completed(stderr="worker failed", returncode=2),
    )
    with pytest.raises(RuntimeError, match="worker failed"):
        _invoke.run_alpha(["ml", "train", "opaque"], data_dir=tmp_path, run_type=None)
    assert statuses[-1] == ("failed", "worker failed")

    def timeout(*args: object, **kwargs: object) -> Any:
        del args, kwargs
        raise subprocess.TimeoutExpired(["alpha"], 3600)

    monkeypatch.setattr(_invoke, "_run_action_process", timeout)
    with pytest.raises(RuntimeError, match="exceeded 3600s"):
        _invoke.run_alpha(["forecast", "run", "SPY"], data_dir=tmp_path, run_type="forecast")
    assert statuses[-1][0] == "failed"

    def os_error(*args: object, **kwargs: object) -> Any:
        del args, kwargs
        raise OSError("spawn unavailable")

    monkeypatch.setattr(_invoke, "_run_action_process", os_error)
    with pytest.raises(OSError, match="spawn unavailable"):
        _invoke.run_alpha(["forecast", "eval", "SPY"], data_dir=tmp_path, run_type="forecast")
    assert statuses[-1] == ("failed", "spawn unavailable")

    monkeypatch.setattr(
        _invoke,
        "_run_action_process",
        lambda *args, **kwargs: _fake_completed("x" * (_invoke._MAX_STDOUT_CHARS + 1)),
    )
    with pytest.raises(ValueError, match="output exceeds"):
        _invoke.run_alpha(["ml", "train", "opaque"], data_dir=tmp_path, run_type=None)
    assert statuses[-1][0] == "failed"

    monkeypatch.setattr(
        _invoke, "_run_action_process", lambda *args, **kwargs: _fake_completed("done")
    )
    with pytest.raises(ValueError, match="unsupported run type"):
        _invoke.run_alpha(["forecast", "run", "SPY"], data_dir=tmp_path, run_type="unknown")
    assert statuses[-1][0] == "failed"

    with pytest.raises(RuntimeError, match="could not parse a run id"):
        _invoke.run_alpha(["forecast", "run", "SPY"], data_dir=tmp_path, run_type="forecast")
    assert statuses[-1][0] == "failed"

    run_id = "1212121212121212"
    monkeypatch.setattr(
        _invoke,
        "_run_action_process",
        lambda *args, **kwargs: _fake_completed(f"forecast SPY -> run {run_id}: done"),
    )
    with pytest.raises(RuntimeError, match="produced no manifest"):
        _invoke.run_alpha(["forecast", "run", "SPY"], data_dir=tmp_path, run_type="forecast")
    assert statuses[-1][0] == "failed"


def test_heavyweight_journal_transition_failures_abort_the_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        _invoke,
        "_reserve_heavyweight_job",
        lambda *args, **kwargs: "00000000-0000-4000-8000-000000000001",
    )
    transitions: list[str] = []

    def fail_start(
        job_id: str | None,
        status: str,
        **kwargs: object,
    ) -> None:
        del job_id, kwargs
        transitions.append(status)
        raise RuntimeError("journal unavailable")

    monkeypatch.setattr(_invoke, "_set_heavyweight_job_status", fail_start)
    with pytest.raises(RuntimeError, match="journal unavailable"):
        _invoke.run_alpha(["forecast", "run", "SPY"], data_dir=tmp_path, run_type="forecast")
    assert transitions == ["running", "failed"]

    def fail_completion(
        job_id: str | None,
        status: str,
        **kwargs: object,
    ) -> None:
        del job_id, kwargs
        transitions.append(status)
        if status == "succeeded":
            raise RuntimeError("terminal journal unavailable")

    transitions.clear()
    monkeypatch.setattr(_invoke, "_set_heavyweight_job_status", fail_completion)
    monkeypatch.setattr(
        _invoke, "_run_action_process", lambda *args, **kwargs: _fake_completed("done")
    )
    with pytest.raises(RuntimeError, match="terminal journal unavailable"):
        _invoke.run_alpha(["ml", "train", "opaque"], data_dir=tmp_path, run_type=None)
    assert transitions == ["running", "succeeded", "failed"]

    run_id = "3434343434343434"
    _write_manifest(tmp_path, "forecast", run_id, {"run_id": run_id, "command": "forecast_run"})
    monkeypatch.setattr(
        _invoke,
        "_run_action_process",
        lambda *args, **kwargs: _fake_completed(f"forecast SPY -> run {run_id}: done"),
    )
    transitions.clear()
    with pytest.raises(RuntimeError, match="terminal journal unavailable"):
        _invoke.run_alpha(["forecast", "run", "SPY"], data_dir=tmp_path, run_type="forecast")
    assert transitions == ["running", "succeeded", "failed"]


def test_heavyweight_manifest_validation_failure_marks_the_job_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = "5656565656565656"
    statuses: list[str] = []
    monkeypatch.setattr(
        _invoke,
        "_reserve_heavyweight_job",
        lambda *args, **kwargs: "00000000-0000-4000-8000-000000000001",
    )
    monkeypatch.setattr(
        _invoke,
        "_set_heavyweight_job_status",
        lambda job_id, status, **kwargs: statuses.append(status),
    )
    monkeypatch.setattr(
        _invoke,
        "_run_action_process",
        lambda *args, **kwargs: _fake_completed(f"forecast SPY -> run {run_id}: done"),
    )
    monkeypatch.setattr(
        _invoke,
        "read_bounded_manifest",
        lambda *args, **kwargs: (_ for _ in ()).throw(DataError("artifact hash mismatch")),
    )

    with pytest.raises(DataError, match="artifact hash mismatch"):
        _invoke.run_alpha(["forecast", "run", "SPY"], data_dir=tmp_path, run_type="forecast")
    assert statuses == ["running", "failed"]


def test_legacy_run_reads_are_deterministically_paged_and_payload_bounded(tmp_path: Path) -> None:
    for run_id in ("0000000000000001", "0000000000000002", "0000000000000003"):
        _write_manifest(
            tmp_path,
            "runs",
            run_id,
            {"run_id": run_id, "command": "backtest_run", "symbol": "SPY"},
        )
    page = _runs.list_runs(data_dir=tmp_path, limit=1, offset=1)
    assert page == [{"run_id": "0000000000000002", "command": "backtest_run", "label": "SPY"}]
    with pytest.raises(ValueError, match="limit"):
        _runs.list_runs(data_dir=tmp_path, limit=501)
    with pytest.raises(ValueError, match="offset"):
        _runs.list_runs(data_dir=tmp_path, offset=-1)

    oversized = "ffffffffffffffff"
    run_dir = tmp_path / "runs" / oversized
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        '{"payload":"' + "x" * _runs.MAX_MANIFEST_BYTES + '"}', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="exceeds"):
        _runs.get_run(oversized, data_dir=tmp_path)


def test_legacy_get_run_rejects_nonfinite_or_overdeep_json(tmp_path: Path) -> None:
    nonfinite = "eeeeeeeeeeeeeeee"
    run_dir = tmp_path / "runs" / nonfinite
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text('{"metric":NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite"):
        _runs.get_run(nonfinite, data_dir=tmp_path)

    overdeep = "dddddddddddddddd"
    nested: object = "leaf"
    for _ in range(_runs.MAX_MANIFEST_DEPTH + 2):
        nested = {"next": nested}
    _write_manifest(tmp_path, "runs", overdeep, {"payload": nested})
    with pytest.raises(ValueError, match="levels"):
        _runs.get_run(overdeep, data_dir=tmp_path)
