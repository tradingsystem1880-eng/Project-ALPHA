"""Acquisition orchestration tests: durable reservations and bounded child ownership."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from alpha_cli import comparison_acquisition as module
from alpha_cli import comparison_acquisition_worker as worker
from alpha_core import DataError
from alpha_data.adapters.base import FetchResult
from tests.unit.test_comparison_acquisition import (
    fixture_dispatch,
    parent_case,
    provider_result,
    series,
)


def test_interrupted_reservation_is_never_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = parent_case(tmp_path)
    plan = module.draft_acquisition(case, series())
    monkeypatch.setenv("ALPHA_TIINGO_API_KEY", "fixture")
    dispatch = Mock(side_effect=KeyboardInterrupt)
    monkeypatch.setattr(module, "_dispatch", dispatch)
    with pytest.raises(KeyboardInterrupt):
        module.acquire_comparisons(case, plan)
    with pytest.raises(DataError, match="ambiguous"):
        module.acquire_comparisons(case, plan)
    assert dispatch.call_count == 1
    assert (case.path / "comparison-acquisition/request.json").is_file()


@pytest.mark.parametrize("mode", ["success", "timeout", "interrupt", "missing"])
def test_dispatch_deadline_and_process_group_reaping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    from alpha_cli import durable_lease

    process = Mock(pid=100, returncode=0)
    if mode == "timeout":
        process.wait.side_effect = subprocess.TimeoutExpired("worker", 90)
    elif mode == "interrupt":
        process.wait.side_effect = KeyboardInterrupt
    if mode == "success":
        module._write(tmp_path / "attempt-0.json", {"status": "failed", "message": "fixture"})
    popen = Mock(return_value=process)
    reap = Mock()
    monkeypatch.setenv("ALPHA_TIINGO_API_KEY", "fixture")
    monkeypatch.setenv("UNRELATED_PRIVATE_TOKEN", "excluded")
    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(durable_lease, "terminate_and_reap", reap)
    if mode == "interrupt":
        with pytest.raises(KeyboardInterrupt):
            module._dispatch(tmp_path, 0)
    else:
        assert module._dispatch(tmp_path, 0)["status"] == "failed"
    process.wait.assert_called_once_with(timeout=90)
    reap.assert_called_once_with(process, process_group_id=100)
    assert popen.call_args.kwargs["start_new_session"] is True
    assert "UNRELATED_PRIVATE_TOKEN" not in popen.call_args.kwargs["env"]


def test_missing_credential_does_not_spend_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = parent_case(tmp_path)
    plan = module.draft_acquisition(case, series())
    monkeypatch.delenv("ALPHA_TIINGO_API_KEY", raising=False)
    with pytest.raises(DataError, match="process-injected"):
        module.acquire_comparisons(case, plan)
    assert not (case.path / "comparison-acquisition").exists()


def test_symlinked_root_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    case = parent_case(tmp_path)
    plan = module.draft_acquisition(case, series())
    (case.path / "comparison-acquisition").symlink_to(tmp_path / "other")
    monkeypatch.setenv("ALPHA_TIINGO_API_KEY", "fixture")
    with pytest.raises(DataError, match="symlinked"):
        module.acquire_comparisons(case, plan)


def test_replay_checks_snapshot_against_raw_even_with_updated_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polars as pl

    from alpha_cli.comparison_acquisition_evidence import _inventory

    case = parent_case(tmp_path)
    plan = module.draft_acquisition(case, series())
    monkeypatch.setenv("ALPHA_TIINGO_API_KEY", "fixture")
    monkeypatch.setattr(worker, "_fetch", provider_result)
    monkeypatch.setattr(module, "_dispatch", fixture_dispatch)
    result = module.acquire_comparisons(case, plan)
    root = case.path / "comparison-acquisition"
    snap = (
        Path(result["data_root"]) / "snapshots" / result["comparisons"]["series"][0]["snapshot_id"]
    )
    frame = pl.read_parquet(snap / "bars/SPY.parquet").with_columns(pl.col("volume") + 1)
    frame.write_parquet(snap / "bars/SPY.parquet")
    import hashlib
    import json

    manifest = module._read(snap / "manifest.json")
    manifest["symbols"]["SPY"]["bars_sha256"] = hashlib.sha256(
        (snap / "bars/SPY.parquet").read_bytes()
    ).hexdigest()
    (snap / "manifest.json").write_text(json.dumps(manifest))
    record = module._read(root / "result.json")
    record["artifacts"] = _inventory(root)
    (root / "result.json").write_text(json.dumps(record))
    with pytest.raises(DataError, match="snapshot differs"):
        module.acquire_comparisons(case, plan)


def test_parent_directory_and_request_fsynced_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    case = parent_case(tmp_path)
    plan = module.draft_acquisition(case, series())
    synced: list[int] = []
    original = os.fsync

    def fsync(descriptor: int) -> None:
        synced.append(os.fstat(descriptor).st_ino)
        original(descriptor)

    def dispatch(root: Path, index: int) -> dict[str, Any]:
        assert case.path.stat().st_ino in synced
        assert (root / "request.json").stat().st_ino in synced
        assert root.stat().st_ino in synced
        return {"status": "failed", "message": "fixture"}

    monkeypatch.setenv("ALPHA_TIINGO_API_KEY", "fixture")
    monkeypatch.setattr(os, "fsync", fsync)
    monkeypatch.setattr(module, "_dispatch", dispatch)
    assert module.acquire_comparisons(case, plan)["status"] == "failed"


def test_quarantine_failure_is_replayed_without_refetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from alpha_data.adapters.tiingo_adapter import parse_tiingo_eod

    case = parent_case(tmp_path)
    plan = module.draft_acquisition(case, series())

    def missing_session(plan: module.AcquisitionPlan, index: int, limit: int) -> FetchResult:
        result = provider_result(plan, index, limit)
        assert result.raw_response is not None and result.receipt is not None
        raw = json.dumps(json.loads(result.raw_response)[:1]).encode()
        item = plan.series[index]
        return parse_tiingo_eod(
            raw,
            symbol=item.symbol,
            provider_symbol=item.symbol,
            asset_class=item.asset_class,
            venue=item.venue,
            calendar=item.calendar,
            currency=item.currency,
            start=plan.start,
            end=plan.end,
            fetched_at=result.receipt.fetched_at,
        )

    monkeypatch.setenv("ALPHA_TIINGO_API_KEY", "fixture")
    monkeypatch.setattr(worker, "_fetch", missing_session)
    monkeypatch.setattr(module, "_dispatch", fixture_dispatch)
    result = module.acquire_comparisons(case, plan)
    assert result["status"] == "failed"
    assert "comparisons" not in result
    assert list(
        (case.path / "comparison-acquisition/data/store/quarantine").glob("*/*/quality.json")
    )
    monkeypatch.setattr(module, "_dispatch", lambda *a: pytest.fail("failure replay fetched"))
    assert module.acquire_comparisons(case, plan) == result


def test_worker_sanitizes_failure_and_arms_own_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import signal
    import sys

    alarm = Mock()
    monkeypatch.setattr(signal, "alarm", alarm)
    monkeypatch.setattr(sys, "argv", ["worker", str(tmp_path), "0"])
    monkeypatch.setattr(worker, "perform_request", Mock(side_effect=DataError("secret-token")))
    worker.main()
    receipt = module._read(tmp_path / "attempt-0.json")
    assert receipt["status"] == "failed"
    assert "secret-token" not in str(receipt)
    assert [call.args[0] for call in alarm.call_args_list] == [90, 0]
