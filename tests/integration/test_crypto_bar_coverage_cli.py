"""Retained native daily bar audit through actual quality CLI; synthetic roots only."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli import crypto_data_cmds
from alpha_cli.main import app
from alpha_data.crypto.contracts import CryptoDatasetIdentityV1, CryptoQualityReportV1
from alpha_data.crypto.ingestion import ingest_provider_payload

from .test_crypto_backfill_resume_cli import environment as environment
from .test_crypto_backfill_status_cli import _fingerprint, _no_effects

START = datetime(2024, 1, 1, tzinfo=UTC)
DATASET = CryptoDatasetIdentityV1(
    provider="binance",
    venue="binance",
    market_type="spot",
    family="market_bars",
    instrument="BTCUSDT",
    base_asset="BTC",
    quote_asset="USDT",
    frequency="1d",
    units="provider_native_ohlcv",
    timestamp_convention="interval_start_utc",
)


def _frame(days: list[int]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "open_time": [START + timedelta(days=d) for d in days],
            "open": [100.0] * len(days),
            "high": [105.0] * len(days),
            "low": [95.0] * len(days),
            "close": [101.0] * len(days),
            "base_volume": [20.0] * len(days),
            "close_time": [START + timedelta(days=d + 1, milliseconds=-1) for d in days],
            "quote_volume": [2020.0] * len(days),
            "trade_count": [10] * len(days),
            "taker_buy_base_volume": [10.0] * len(days),
            "taker_buy_quote_volume": [1010.0] * len(days),
        }
    )


def _retain(store: Any, data: pl.DataFrame) -> str:
    normal = ingest_provider_payload(
        store,
        dataset=DATASET,
        payload=b"synthetic-native-bar-fixture",
        request=(("symbol", "BTCUSDT"), ("interval", "1d")),
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        provider_schema="synthetic.binance.klines",
        parser_version="synthetic.v1",
        logical_name="bars.json",
        parser=lambda _: data,
        observed_column="open_time",
        key_columns=("open_time",),
        expected_cadence=timedelta(days=1),
        period_start_timestamps=True,
    )
    return str(normal.normalized_manifest["manifest_id"])


def _invoke(identity: str, **options: str) -> Any:
    args = ["crypto-data", "quality", identity, "--json"]
    defaults = {
        "coverage-start": "2024-01-01T00:00:00Z",
        "coverage-end": "2024-01-05T00:00:00Z",
        "as-of": "2024-01-05T00:00:00Z",
        "expected-cadence-seconds": "86400",
        "max-verify-artifact-bytes": "1000000",
        **options,
    }
    for key, value in defaults.items():
        args.extend(["--" + key, value])
    return CliRunner().invoke(app, args)


def _guard(monkeypatch: pytest.MonkeyPatch, store: Any) -> None:
    _no_effects(monkeypatch, store)

    def fail(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("retained audit must not fetch")

    for name in ("fetch_binance_archive", "fetch_binance_checksum", "fetch_binance_public_api"):
        monkeypatch.setattr(crypto_data_cmds, name, fail)


def test_quality_audit_finds_edge_gaps_hidden_by_stored_qualified_report(
    environment: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, root, calls = environment
    identity = _retain(store, _frame([1, 2]))
    legacy = CliRunner().invoke(app, ["crypto-data", "quality", identity, "--json"])
    assert legacy.exit_code == 0 and '"state": "qualified"' in legacy.stdout
    before = _fingerprint(root), _fingerprint(store.bulk_root)
    _guard(monkeypatch, store)
    result = _invoke(identity)
    report = json.loads(result.stdout)
    assert result.exit_code == 1 and report["audit_state"] == "inspected"
    assert report["stored_quality"]["state"] == "qualified"
    assert report["row_audit"]["missing_slots"] == 2
    assert report["provider_history_complete"] is False and report["execution_authority"] is False
    assert report["source_retrieved_after_as_of"] is True
    assert (_fingerprint(root), _fingerprint(store.bulk_root)) == before and calls == []
    assert (
        CliRunner().invoke(app, ["crypto-data", "quality", identity, "--json"]).stdout
        == legacy.stdout
    )


def test_quality_audit_full_grid_is_only_an_advisory_result(
    environment: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, root, calls = environment
    identity = _retain(store, _frame([0, 1, 2, 3]))
    before = _fingerprint(root), _fingerprint(store.bulk_root)
    _guard(monkeypatch, store)
    result = _invoke(identity)
    report = json.loads(result.stdout)
    assert result.exit_code == 0 and report["row_audit"]["declared_grid_satisfied"] is True
    assert report["point_in_time_eligibility"] is False
    assert (_fingerprint(root), _fingerprint(store.bulk_root)) == before and calls == []


@pytest.mark.parametrize("case", ["conflict", "invalid_numeric", "offgrid", "outoforder"])
def test_retained_row_findings_are_not_hidden_by_byte_integrity(
    environment: Any, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    store, root, calls = environment
    if case == "conflict":
        frame = _frame([0, 1, 1, 2, 3]).with_columns(
            pl.Series("quote_volume", [2020.0, 2020.0, 2040.0, 2020.0, 2020.0])
        )
    elif case == "invalid_numeric":
        frame = _frame([0, 1, 2, 3]).with_columns(
            pl.Series("base_volume", [20.0, float("nan"), 20.0, 20.0])
        )
    elif case == "outoforder":
        frame = _frame([0, 2, 1, 3])
    else:
        frame = _frame([0, 1, 2, 3]).with_columns(
            (pl.col("open_time") + pl.duration(hours=1)),
            (pl.col("close_time") + pl.duration(hours=1)),
        )
    identity = _retain(store, frame)
    before = _fingerprint(root), _fingerprint(store.bulk_root)
    _guard(monkeypatch, store)
    result = _invoke(identity)
    report = json.loads(result.stdout)
    assert result.exit_code == 1 and report["audit_state"] == "inspected"
    findings = report["row_audit"]
    assert findings["declared_grid_satisfied"] is False
    if case == "conflict":
        assert findings["conflicting_duplicate_groups"] == 1
    elif case == "invalid_numeric":
        assert findings["invalid_numeric_rows"] == 1
    elif case == "outoforder":
        assert "non_monotonic_time" in findings["failures"]
    else:
        assert findings["off_grid_rows"] == 4
    assert (_fingerprint(root), _fingerprint(store.bulk_root)) == before and calls == []


@pytest.mark.parametrize(
    "options",
    [
        {"max-rows": "1"},
        {"max-input-bytes": "1"},
        {"max-verify-artifact-bytes": "1"},
        {"max-verify-metadata-bytes": "1"},
        {"expected-cadence-seconds": "3600"},
        {"as-of": "2024-01-04T12:00:00Z"},
    ],
)
def test_limits_and_unsupported_request_never_produce_prefix_success(
    environment: Any, monkeypatch: pytest.MonkeyPatch, options: dict[str, str]
) -> None:
    store, root, calls = environment
    identity = _retain(store, _frame([0, 1, 2, 3]))
    before = _fingerprint(root), _fingerprint(store.bulk_root)
    _guard(monkeypatch, store)
    result = _invoke(identity, **options)
    report = json.loads(result.stdout)
    assert result.exit_code == 1 and report["audit_state"] == "unavailable"
    assert report.get("row_audit") is None
    assert (_fingerprint(root), _fingerprint(store.bulk_root)) == before and calls == []


@pytest.mark.parametrize("damage", ["raw_changed", "normalized_missing", "manifest_truncated"])
def test_changed_or_missing_retained_evidence_is_unavailable_without_repair(
    environment: Any, monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    store, root, calls = environment
    identity = _retain(store, _frame([0, 1, 2, 3]))
    manifest = store.verify_manifest(identity)
    if damage == "raw_changed":
        raw = store.verify_manifest(manifest["input_manifest_ids"][0])
        (store.bulk_root / raw["artifact_key"]).write_bytes(b"changed")
    elif damage == "normalized_missing":
        (store.bulk_root / manifest["artifact_key"]).unlink()
    else:
        (store.manifest_root / (identity + ".json")).write_bytes(b"{")
    before = _fingerprint(root), _fingerprint(store.bulk_root)
    _guard(monkeypatch, store)
    result = _invoke(identity)
    report = json.loads(result.stdout)
    assert result.exit_code == 1 and report["audit_state"] == "unavailable"
    assert report["row_audit"] is None
    assert (_fingerprint(root), _fingerprint(store.bulk_root)) == before and calls == []


def test_resource_flag_alone_cannot_silently_use_legacy_unbounded_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail() -> Any:
        pytest.fail("incomplete audit options must fail before opening storage")

    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", fail)
    result = CliRunner().invoke(
        app, ["crypto-data", "quality", "a" * 64, "--max-rows", "1", "--json"]
    )
    assert result.exit_code != 0
    assert "grid audit requires" in result.output


@pytest.mark.parametrize(
    "case", ["row_count_mismatch", "actual_row_overflow", "retired", "nanosecond"]
)
def test_retained_bounds_and_retirement_refuse_without_prefix_or_mutation(
    environment: Any, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    store, root, calls = environment
    data = _frame([0, 1, 2, 3])
    if case == "nanosecond":
        data = data.with_columns(
            (pl.col("open_time").dt.cast_time_unit("ns") + pl.duration(nanoseconds=1)).alias(
                "open_time"
            )
        )
    identity = _retain(store, data)
    if case != "nanosecond":
        manifest = store.verify_manifest(identity)
        original = CryptoQualityReportV1.from_dict(manifest["quality"])
        quality = (
            replace(original, row_count=1)
            if case != "retired"
            else replace(original, state="quarantined", failures=("synthetic_failure",))
        )
        changed = store.publish_normalized(
            (store.bulk_root / manifest["artifact_key"]).read_bytes(),
            dataset=DATASET,
            input_manifest_ids=tuple(manifest["input_manifest_ids"]),
            quality=quality,
        )
        identity = changed["manifest_id"]
        if case == "retired":
            store.retire_manifest(
                identity,
                reason="inactive_quarantined",
                audit_sha256="a" * 64,
                retired_at=crypto_data_cmds._now(),
            )
    before = _fingerprint(root), _fingerprint(store.bulk_root)
    _guard(monkeypatch, store)
    options = {"max-rows": "2"} if case == "actual_row_overflow" else {}
    result = _invoke(identity, **options)
    report = json.loads(result.stdout)
    assert result.exit_code == 1 and report["audit_state"] == "unavailable"
    assert report["row_audit"] is None
    assert (_fingerprint(root), _fingerprint(store.bulk_root)) == before and calls == []
