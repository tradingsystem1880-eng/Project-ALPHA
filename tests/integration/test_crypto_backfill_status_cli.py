"""Production CLI status composition with disposable synthetic retained artifacts only."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from alpha_cli import crypto_data_cmds
from alpha_cli.main import app
from alpha_data.crypto.contracts import CryptoDatasetIdentityV1, CryptoQualityReportV1

from .test_crypto_backfill_resume_cli import _completion, _invoke
from .test_crypto_backfill_resume_cli import environment as environment

runner = CliRunner()


def _status(symbols: str = "ETHUSDT", **extra: str) -> Any:
    options = {
        "symbols": symbols,
        "quote": "USDT",
        "start": "2024-01-01",
        "end": "2024-03-01",
        "ledger": "resume",
        "max-ledger-bytes": "100000",
        "max-windows": "20",
        "max-verify-artifact-bytes": "1000000",
        **extra,
    }
    args = ["crypto-data", "backfill-status", "bybit", "funding", "--json"]
    for key, value in options.items():
        args.extend(["--" + key, value])
    return runner.invoke(app, args)


def _fingerprint(root: Path) -> dict[str, tuple[int, str]]:
    return {
        str(p.relative_to(root)): (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
        for p in root.rglob("*")
        if p.is_file()
    }


def _no_effects(monkeypatch: pytest.MonkeyPatch, store: Any) -> None:
    def fail(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("status must not acquire, probe writes, lock, initialize DB or publish")

    for name in ("_backfill_acquire", "_acquire_result", "fetch_bybit_public", "_control_store"):
        monkeypatch.setattr(crypto_data_cmds, name, fail)
    monkeypatch.setattr(store, "verify_ready", fail)
    monkeypatch.setattr(store, "admission_lock", fail)


def test_status_verifies_completion_and_pending_without_writes(
    environment: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, root, calls = environment
    assert _invoke().exit_code == 0
    calls.clear()
    before = _fingerprint(root), _fingerprint(store.bulk_root)
    _no_effects(monkeypatch, store)
    result = _status("ETHUSDT,BTCUSDT")
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert [r["status"] for r in report["windows"]] == ["completed_verified", "pending_unrecorded"]
    assert report["last_verified_checkpoint"]["symbol"] == "ETHUSDT"
    assert report["historical_coverage_complete"] is False
    assert report["historical_quota_usage"] is None
    assert report["execution_authority"] is False
    assert report["artifact_bytes_read"] > 0
    assert calls == []
    assert (_fingerprint(root), _fingerprint(store.bulk_root)) == before
    assert not (root / "control").exists()


@pytest.mark.parametrize(
    "damage", ["raw_changed", "normalized_missing", "manifest_missing", "retired"]
)
def test_status_unverifiable_evidence_never_repairs_or_fetches(
    environment: Any, monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    store, root, calls = environment
    assert _invoke().exit_code == 0
    path, body, key, entry = _completion(root)
    manifest = store.verify_manifest(entry["manifest_id"])
    if damage == "raw_changed":
        raw = store.verify_manifest(manifest["input_manifest_ids"][0])
        (store.bulk_root / raw["artifact_key"]).write_bytes(b"changed")
    elif damage == "normalized_missing":
        (store.bulk_root / manifest["artifact_key"]).unlink()
    elif damage == "manifest_missing":
        (store.manifest_root / (entry["manifest_id"] + ".json")).unlink()
    else:
        changed = store.publish_normalized(
            (store.bulk_root / manifest["artifact_key"]).read_bytes(),
            dataset=CryptoDatasetIdentityV1.from_dict(manifest["dataset"]),
            input_manifest_ids=tuple(manifest["input_manifest_ids"]),
            quality=replace(
                CryptoQualityReportV1.from_dict(manifest["quality"]),
                state="quarantined",
                failures=("synthetic_failure",),
            ),
        )
        entry.update(manifest_id=changed["manifest_id"], quality_state="quarantined")
        path.write_text(json.dumps(body))
        store.retire_manifest(
            changed["manifest_id"],
            reason="inactive_quarantined",
            audit_sha256="a" * 64,
            retired_at=crypto_data_cmds._now(),
        )
    calls.clear()
    before = _fingerprint(root), _fingerprint(store.bulk_root)
    _no_effects(monkeypatch, store)
    result = _status()
    assert result.exit_code == 1, result.output
    report = json.loads(result.stdout)
    assert report["windows"][0]["status"] == "unverifiable"
    assert report["resume_evidence"] == "blocked"
    assert (_fingerprint(root), _fingerprint(store.bulk_root)) == before
    assert calls == [] and path.exists()


def test_status_budget_stop_retains_unknown_remaining_verification(
    environment: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, root, calls = environment
    assert _invoke("ETHUSDT,BTCUSDT").exit_code == 0
    calls.clear()
    before = _fingerprint(root), _fingerprint(store.bulk_root)
    _no_effects(monkeypatch, store)
    result = _status("ETHUSDT,BTCUSDT", **{"max-verify-artifact-bytes": "1"})
    assert result.exit_code == 1
    report = json.loads(result.stdout)
    assert [row["status"] for row in report["windows"]] == ["unverifiable", "not_checked"]
    assert report["artifact_bytes_read"] == 0
    assert (_fingerprint(root), _fingerprint(store.bulk_root)) == before and calls == []


def test_status_unconfigured_storage_is_honest_and_readonly(
    environment: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, root, calls = environment
    assert _invoke().exit_code == 0
    calls.clear()
    before = _fingerprint(root)
    monkeypatch.setattr(
        crypto_data_cmds,
        "_bulk_store",
        lambda: (_ for _ in ()).throw(crypto_data_cmds.BulkVolumeUnconfigured("SECRET_CANARY")),
    )
    result = _status()
    report = json.loads(result.stdout)
    assert report["windows"][0]["status"] == "unavailable"
    assert "SECRET_CANARY" not in result.output
    assert calls == [] and _fingerprint(root) == before


def test_status_missing_progress_does_not_construct_or_create_store(
    environment: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, root, calls = environment
    _no_effects(monkeypatch, store)
    monkeypatch.setattr(
        crypto_data_cmds, "_bulk_store", lambda: pytest.fail("no completions to verify")
    )
    result = _status()
    assert result.exit_code == 1
    assert json.loads(result.stdout)["reason"] == "LEDGER_MISSING"
    assert calls == [] and not root.exists()


def test_operator_status_to_safe_dry_run_preview_keeps_zero_effects(
    environment: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, root, calls = environment
    assert _invoke().exit_code == 0
    calls.clear()
    _no_effects(monkeypatch, store)
    before = _fingerprint(root), _fingerprint(store.bulk_root)
    status = _status("ETHUSDT,BTCUSDT")
    report = json.loads(status.stdout)
    preview = report["safe_next_command_argv"]
    assert preview[:3] == ["alpha", "crypto-data", "backfill"]
    assert "--dry-run" in preview
    planned = runner.invoke(app, preview[1:])
    assert planned.exit_code == 0, planned.output
    assert json.loads(planned.stdout)["dry_run"] is True
    assert calls == [] and (_fingerprint(root), _fingerprint(store.bulk_root)) == before
