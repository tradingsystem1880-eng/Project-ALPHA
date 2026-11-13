from __future__ import annotations

import json
from typing import Any

import pytest

from alpha_cli import crypto_data_cmds

from .test_crypto_backfill_resume_cli import _completion, _invoke
from .test_crypto_backfill_resume_cli import environment as environment


def _cost(store: Any, root: Any) -> int:
    _, _, _, entry = _completion(root)
    manifest = store.verify_manifest(entry["manifest_id"])
    return int(manifest["artifact_bytes"]) + 2 * sum(
        int(store.verify_manifest(parent)["artifact_bytes"])
        for parent in manifest["input_manifest_ids"]
    )


def test_cli_exact_cap_counts_recursive_and_repeated_raw_reads(environment: Any) -> None:
    store, root, calls = environment
    assert _invoke().exit_code == 0
    cost = _cost(store, root)
    path, _, _, _ = _completion(root)
    before = path.read_bytes()
    calls.clear()
    result = _invoke(max_verify_artifact_bytes=str(cost))
    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    assert receipt["verification_artifact_byte_limit"] == cost
    assert (
        receipt["verification_artifact_bytes_read"]
        == receipt["verification_artifact_bytes_reserved"]
        == cost
    )
    assert calls == [] and path.read_bytes() == before


@pytest.mark.parametrize("shortfall", [1, 1000000])
def test_cli_insufficient_cap_stops_before_unfinished_acquisition(
    environment: Any, shortfall: int
) -> None:
    store, root, calls = environment
    assert _invoke().exit_code == 0
    cap = max(1, _cost(store, root) - shortfall)
    path, _, _, _ = _completion(root)
    before = path.read_bytes()
    manifests = sorted(p.name for p in store.manifest_root.iterdir())
    calls.clear()
    result = _invoke("BTCUSDT,ETHUSDT", max_verify_artifact_bytes=str(cap))
    assert result.exit_code != 0 and "budget exhausted" in result.output
    assert calls == [] and path.read_bytes() == before
    assert sorted(p.name for p in store.manifest_root.iterdir()) == manifests


def test_cli_one_cap_is_shared_across_completed_windows(environment: Any) -> None:
    store, root, calls = environment
    assert _invoke("ETHUSDT,BTCUSDT").exit_code == 0
    path, ledger, _, _ = _completion(root)
    cost = 0
    for entry in ledger["windows"].values():
        manifest = store.verify_manifest(entry["manifest_id"])
        cost += manifest["artifact_bytes"] + 2 * sum(
            store.verify_manifest(parent)["artifact_bytes"]
            for parent in manifest["input_manifest_ids"]
        )
    before = path.read_bytes()
    calls.clear()
    failed = _invoke("ETHUSDT,BTCUSDT", max_verify_artifact_bytes=str(cost - 1))
    assert failed.exit_code != 0 and calls == [] and path.read_bytes() == before
    exact = _invoke("ETHUSDT,BTCUSDT", max_verify_artifact_bytes=str(cost))
    assert exact.exit_code == 0, exact.output
    assert json.loads(exact.stdout)["verification_artifact_bytes_read"] == cost
    assert calls == [] and path.read_bytes() == before


def test_cli_dry_run_declares_cap_but_performs_zero_verification_reads(
    environment: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, root, calls = environment
    assert _invoke().exit_code == 0
    path, _, _, _ = _completion(root)
    before = path.read_bytes()
    calls.clear()
    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: pytest.fail("no storage probe"))
    result = _invoke(dry_run="", max_verify_artifact_bytes="1")
    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    assert receipt["verification_artifact_byte_limit"] == 1
    assert (
        receipt["verification_artifact_bytes_read"]
        == receipt["verification_artifact_bytes_reserved"]
        == 0
    )
    assert calls == [] and path.read_bytes() == before


@pytest.mark.parametrize("cap", ["0", "-1", "1.5"])
def test_cli_invalid_cap_never_probes_or_acquires(environment: Any, cap: str) -> None:
    _, root, calls = environment
    result = _invoke(max_verify_artifact_bytes=cap)
    assert result.exit_code != 0
    assert calls == [] and not root.exists()


@pytest.mark.bias_guard
def test_future_unrequested_artifacts_do_not_change_frozen_resume_budget(environment: Any) -> None:
    store, root, calls = environment
    assert _invoke().exit_code == 0
    cost = _cost(store, root)
    assert _invoke(ledger="future", start="2025-01-01", end="2025-02-01").exit_code == 0
    calls.clear()
    result = _invoke(max_verify_artifact_bytes=str(cost))
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["verification_artifact_bytes_read"] == cost
    assert calls == []
    # Leaky control: auditing all stored artifacts rather than this exact request exceeds its cap.
    with pytest.raises(AssertionError):
        assert sum(item["artifact_bytes"] for item in store.inventory()) <= cost


def test_uncapped_callers_do_not_report_unknown_reads_as_zero(environment: Any) -> None:
    assert _invoke().exit_code == 0
    result = _invoke()
    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    assert receipt["verified_completed"] == 1
    assert receipt["verification_artifact_byte_limit"] is None
    assert receipt["verification_artifact_bytes_read"] is None
    assert receipt["verification_artifact_bytes_reserved"] is None
