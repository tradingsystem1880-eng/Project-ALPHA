"""Actual CLI/acquisition/storage composition with synthetic bytes and temporary roots only."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

import pytest
from typer.testing import CliRunner

from alpha_cli import crypto_data_cmds
from alpha_cli.main import app
from alpha_data.crypto.contracts import CryptoDatasetIdentityV1, CryptoQualityReportV1
from alpha_data.crypto.storage import Capacity, CryptoBulkStore

runner = CliRunner()
NOW = datetime(2026, 9, 10, tzinfo=UTC)


def _funding_response(endpoint: str, params: dict[str, Any], calls: list[str]) -> bytes:
    assert endpoint == "funding"
    calls.append(str(params["symbol"]))
    return json.dumps(
        {
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "category": "linear",
                "list": [
                    {
                        "symbol": params["symbol"],
                        "fundingRate": "0.0001",
                        "fundingRateTimestamp": str(int(params["startTime"]) + 86_400_000),
                    }
                ],
            },
        }
    ).encode()


@pytest.fixture
def environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[CryptoBulkStore, Path, list[str]]:
    bulk = tmp_path / "bulk"
    bulk.mkdir()
    root = tmp_path / "data"
    store = CryptoBulkStore(
        bulk_root=bulk,
        manifest_root=root / "crypto" / "manifests",
        expected_volume_uuid="SYNTHETIC",
        volume_uuid=lambda _: "SYNTHETIC",
        # Synthetic capacity/identity only. Production reserve defaults remain unchanged.
        capacity=lambda _: Capacity(total_bytes=2_000_000_000_000, free_bytes=1_500_000_000_000),
    )
    monkeypatch.setenv("ALPHA_DATA_DIR", str(root))
    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: store)
    monkeypatch.setattr(crypto_data_cmds, "_now", lambda: NOW)
    calls: list[str] = []

    def fetch(endpoint: str, params: dict[str, Any]) -> bytes:
        return _funding_response(endpoint, params, calls)

    monkeypatch.setattr(crypto_data_cmds, "fetch_bybit_public", fetch)
    return store, root, calls


def _invoke(symbols: str = "ETHUSDT", **options: str) -> Any:
    flags = {"start": "2024-01-01", "end": "2024-03-01", "ledger": "resume", **options}
    args = [
        "crypto-data",
        "backfill",
        "bybit",
        "funding",
        "--symbols",
        symbols,
        "--quote",
        "USDT",
        "--category",
        "linear",
        "--frequency",
        "1h",
        "--json",
    ]
    for key, value in flags.items():
        args += ["--" + key.replace("_", "-")]
        if value:
            args.append(value)
    return runner.invoke(app, args)


def _completion(root: Path) -> tuple[Path, dict[str, Any], str, dict[str, Any]]:
    path = root / "crypto" / "backfill" / "resume.json"
    ledger = json.loads(path.read_text())
    key, entry = next(iter(ledger["windows"].items()))
    return path, ledger, key, entry


def test_cli_reopens_completed_bytes_and_retries_only_unfinished_instrument(
    environment: Any,
) -> None:
    store, root, calls = environment
    first = _invoke()
    assert first.exit_code == 0, first.output
    path, ledger, key, entry = _completion(root)
    old = dict(entry)
    calls.clear()
    resumed = _invoke("BTCUSDT,ETHUSDT")
    assert resumed.exit_code == 0, resumed.output
    receipt = json.loads(resumed.stdout)
    assert receipt["done"] == receipt["skipped"] == receipt["verified_completed"] == 1
    assert receipt["resume_verification"] == "verified"
    assert calls == ["BTCUSDT"]
    assert json.loads(path.read_text())["windows"][key] == old
    assert store.verify_manifest(entry["manifest_id"])["dataset"]["frequency"] == "funding_interval"
    assert not (root / "control").exists()
    assert not (root / "crypto" / "snapshots").exists()


@pytest.mark.parametrize(
    "damage",
    [
        "normalized_missing",
        "normalized_changed",
        "raw_missing",
        "raw_changed",
        "manifest_missing",
        "manifest_changed",
        "wrong_root",
        "missing_manifest_id",
        "wrong_quality",
        "raw_as_normalized",
    ],
)
def test_cli_bad_completed_evidence_stops_before_all_new_effects(
    environment: Any, damage: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, root, calls = environment
    first = _invoke()
    assert first.exit_code == 0, first.output
    path, ledger, key, entry = _completion(root)
    manifest = store.verify_manifest(entry["manifest_id"])
    raw = store.verify_manifest(manifest["input_manifest_ids"][0])
    if damage in {"normalized_missing", "normalized_changed", "raw_missing", "raw_changed"}:
        selected = raw if damage.startswith("raw") else manifest
        target = store.bulk_root / selected["artifact_key"]
        if damage.endswith("missing"):
            target.unlink()
        else:
            target.write_bytes(b"changed synthetic evidence")
    elif damage.startswith("manifest_"):
        target = store.manifest_root / (entry["manifest_id"] + ".json")
        if damage.endswith("missing"):
            target.unlink()
        else:
            target.write_text("{}")
    elif damage == "wrong_root":
        monkeypatch.setattr(store, "_volume_uuid", lambda _: "ANOTHER-ROOT")
    else:
        if damage == "missing_manifest_id":
            entry.pop("manifest_id")
        elif damage == "wrong_quality":
            entry["quality_state"] = "quarantined"
        else:
            entry["manifest_id"] = raw["manifest_id"]
        path.write_text(json.dumps(ledger))
    before = path.read_bytes()
    retained_manifest_names = sorted(p.name for p in store.manifest_root.iterdir())
    calls.clear()
    resumed = _invoke("BTCUSDT,ETHUSDT")
    assert resumed.exit_code != 0
    assert calls == []
    assert path.read_bytes() == before
    assert sorted(p.name for p in store.manifest_root.iterdir()) == retained_manifest_names
    assert not (root / "crypto" / "snapshots").exists()


@pytest.mark.parametrize("other_symbol", [False, True])
def test_cli_valid_but_unrelated_manifest_cannot_satisfy_completed_window(
    environment: Any, other_symbol: bool
) -> None:
    store, root, calls = environment
    assert _invoke().exit_code == 0
    result = _invoke(
        "BTCUSDT" if other_symbol else "ETHUSDT",
        ledger="other",
        start="2024-04-01",
        end="2024-05-01",
    )
    assert result.exit_code == 0, result.output
    other = json.loads((root / "crypto" / "backfill" / "other.json").read_text())
    path, ledger, key, entry = _completion(root)
    entry["manifest_id"] = next(iter(other["windows"].values()))["manifest_id"]
    path.write_text(json.dumps(ledger))
    before = path.read_bytes()
    calls.clear()
    result = _invoke("BTCUSDT,ETHUSDT")
    assert result.exit_code != 0
    assert ("identity differs" if other_symbol else "raw receipt") in result.output, result.output
    assert calls == [] and path.read_bytes() == before


@pytest.mark.parametrize("state", ["warning", "quarantined"])
def test_cli_verified_capture_keeps_quality_and_retirement_blocks_reuse(
    environment: Any, state: Literal["warning", "quarantined"]
) -> None:
    store, root, calls = environment
    assert _invoke().exit_code == 0
    path, ledger, key, entry = _completion(root)
    manifest = store.verify_manifest(entry["manifest_id"])
    quality = replace(
        CryptoQualityReportV1.from_dict(manifest["quality"]),
        state=state,
        warnings=("synthetic_warning",) if state == "warning" else (),
        failures=("synthetic_failure",) if state == "quarantined" else (),
    )
    changed = store.publish_normalized(
        (store.bulk_root / manifest["artifact_key"]).read_bytes(),
        dataset=CryptoDatasetIdentityV1.from_dict(manifest["dataset"]),
        input_manifest_ids=tuple(manifest["input_manifest_ids"]),
        quality=quality,
    )
    entry.update(manifest_id=changed["manifest_id"], quality_state=state)
    path.write_text(json.dumps(ledger))
    before = path.read_bytes()
    calls.clear()
    result = _invoke()
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["verified_completed"] == 1
    assert calls == [] and path.read_bytes() == before
    if state == "quarantined":
        store.retire_manifest(
            changed["manifest_id"],
            reason="inactive_quarantined",
            audit_sha256="a" * 64,
            retired_at=NOW,
        )
        result = _invoke()
        assert result.exit_code != 0 and "retired" in result.output
        assert calls == [] and path.read_bytes() == before


def test_cli_dry_run_never_opens_storage_or_writes_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "not-created"
    monkeypatch.setenv("ALPHA_DATA_DIR", str(root))
    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: pytest.fail("no storage probe"))
    monkeypatch.setattr(
        crypto_data_cmds, "fetch_bybit_public", lambda *a: pytest.fail("no provider")
    )
    result = _invoke(dry_run="")
    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    assert receipt["dry_run"] is True and receipt["verified_completed"] == 0
    assert receipt["resume_verification"] == "not_run_dry_run"
    assert not root.exists()


def test_cli_cap_failure_publishes_no_completion_and_failed_window_can_retry(
    environment: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, root, calls = environment

    def cap(*args: Any) -> bytes:
        from alpha_core import DataError

        raise DataError("total request budget exhausted")

    with monkeypatch.context() as patched:
        patched.setattr(crypto_data_cmds, "fetch_bybit_public", cap)
        failed = _invoke()
    assert failed.exit_code != 0
    path, ledger, key, entry = _completion(root)
    assert entry["state"] == "failed" and "manifest_id" not in entry
    assert not store.manifest_root.exists()
    retried = _invoke()
    assert retried.exit_code == 0, retried.output
    assert calls == ["ETHUSDT"]
    assert json.loads(path.read_text())["windows"][key]["state"] == "done"
    assert not (root / "crypto" / "snapshots").exists()


@pytest.mark.parametrize("parent_failed", [False, True])
def test_cli_legacy_orphan_with_corrupt_retained_raw_stops_every_new_fetch(
    environment: Any, parent_failed: bool
) -> None:
    store, root, calls = environment
    result = _invoke(end="2024-01-31")
    assert result.exit_code == 0, result.output
    path, ledger, key, entry = _completion(root)
    manifest = store.verify_manifest(entry["manifest_id"])
    raw = store.verify_manifest(manifest["input_manifest_ids"][0])
    (store.bulk_root / raw["artifact_key"]).write_bytes(b"corrupt synthetic retained child")
    if parent_failed:
        ledger["windows"]["ETHUSDT|2024-01-01T00:00:00Z|2024-03-01T00:00:00Z|None"] = {
            "state": "failed",
            "error": "legacy retry overwrote split state",
        }
        path.write_text(json.dumps(ledger))
    before = path.read_bytes()
    calls.clear()
    result = _invoke("BTCUSDT,ETHUSDT")
    assert result.exit_code != 0 and "topology" in result.output
    assert calls == [] and path.read_bytes() == before


def test_cli_interrupted_publication_is_not_a_completed_window_and_raw_survives(
    environment: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_core import DataError

    store, root, calls = environment
    original = store._publish_manifest

    def fail_normalized(body: dict[str, object]) -> dict[str, object]:
        if body.get("artifact_kind") == "normalized":
            raise DataError("synthetic interruption before normalized manifest publication")
        return cast(dict[str, object], original(body))

    monkeypatch.setattr(store, "_publish_manifest", fail_normalized)
    failed = _invoke()
    assert failed.exit_code != 0
    path, ledger, key, entry = _completion(root)
    assert entry["state"] == "failed"
    retained = store.inventory()
    assert len(retained) == 1 and retained[0].get("artifact_kind") != "normalized"
    raw_path = store.bulk_root / retained[0]["artifact_key"]
    raw_bytes = raw_path.read_bytes()
    monkeypatch.setattr(store, "_publish_manifest", original)
    calls.clear()
    result = _invoke()
    assert result.exit_code == 0, result.output
    assert calls == ["ETHUSDT"]
    assert raw_path.read_bytes() == raw_bytes
    assert len(store.inventory()) == 2
    assert json.loads(path.read_text())["windows"][key]["state"] == "done"
    assert not (root / "crypto" / "snapshots").exists()


def test_cli_cancel_resume_verifies_prior_capture_and_fetches_only_unfinished(
    environment: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, root, calls = environment

    def interrupt(endpoint: str, params: dict[str, Any]) -> bytes:
        if params["symbol"] == "BTCUSDT":
            raise KeyboardInterrupt
        return _funding_response(endpoint, params, calls)

    with monkeypatch.context() as patched:
        patched.setattr(crypto_data_cmds, "fetch_bybit_public", interrupt)
        result = _invoke("ETHUSDT,BTCUSDT")
    assert result.exit_code != 0
    path, ledger, key, entry = _completion(root)
    assert entry["state"] == "done" and len(ledger["windows"]) == 1
    old = dict(entry)
    calls.clear()
    result = _invoke("ETHUSDT,BTCUSDT")
    assert result.exit_code == 0, result.output
    assert calls == ["BTCUSDT"]
    assert json.loads(result.stdout)["verified_completed"] == 1
    assert json.loads(path.read_text())["windows"][key] == old


@pytest.mark.parametrize("wrong_period", [False, True])
def test_binance_archive_resume_verifies_native_period_without_new_fetch(
    environment: Any, monkeypatch: pytest.MonkeyPatch, wrong_period: bool
) -> None:
    store, root, calls = environment
    zipped = io.BytesIO()
    with zipfile.ZipFile(zipped, "w") as archive:
        archive.writestr(
            "BTCUSDT-1d-2024-01.csv",
            "1704067200000,100,105,95,101,20,1704153599999,2020,10,10,1010,0\n",
        )
    payload = zipped.getvalue()
    archive_calls: list[str] = []

    def archive_fetch(url: str, *args: Any) -> bytes:
        archive_calls.append(url)
        return payload

    monkeypatch.setattr(crypto_data_cmds, "fetch_binance_archive", archive_fetch)
    monkeypatch.setattr(
        crypto_data_cmds,
        "fetch_binance_checksum",
        lambda *args: (hashlib.sha256(payload).hexdigest() + " archive.zip\n").encode(),
    )
    args = [
        "crypto-data",
        "backfill",
        "binance",
        "market_bars",
        "--symbols",
        "BTCUSDT",
        "--quote",
        "USDT",
        "--category",
        "spot",
        "--frequency",
        "1d",
        "--start",
        "2024-01-01",
        "--end",
        "2024-01-31",
        "--ledger",
        "binance",
        "--json",
    ]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    path = root / "crypto" / "backfill" / "binance.json"
    ledger = json.loads(path.read_text())
    if wrong_period:
        ledger["windows"]["BTCUSDT|None|None|2024-02"] = next(iter(ledger["windows"].values()))
        path.write_text(json.dumps(ledger))
        args[args.index("2024-01-01")] = "2024-02-01"
        args[args.index("2024-01-31")] = "2024-02-28"
    before = path.read_bytes()
    archive_calls.clear()
    result = runner.invoke(app, args)
    if wrong_period:
        assert result.exit_code != 0 and "raw receipt" in result.output
    else:
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["verified_completed"] == 1
        assert json.loads(result.stdout)["skipped"] == 1
    assert archive_calls == [] and calls == [] and path.read_bytes() == before
