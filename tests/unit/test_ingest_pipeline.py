from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import polars as pl
import pytest

from alpha_core import ActionType, CorporateAction, DataError
from alpha_data import pipeline
from alpha_data.adapters.base import DatasetIdentity, FetchReceipt, FetchResult
from alpha_data.pipeline import (
    promote_quarantined,
    rollback_interrupted_promotion,
    stage_and_promote,
)
from alpha_data.store import ParquetStore


def _bars(rows: list[tuple[str, float]]) -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "ts": datetime.fromisoformat(day).replace(tzinfo=UTC),
                "open": close,
                "high": close + 1,
                "low": close - 1,
                "close": close,
                "volume": 1_000.0,
            }
            for day, close in rows
        ],
        schema={
            "ts": pl.Datetime(time_zone="UTC"),
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Float64,
        },
    )


def _result(
    rows: list[tuple[str, float]],
    *,
    start: date,
    end: date,
    raw: bytes = b"payload",
) -> FetchResult:
    fetched_at = datetime(2026, 8, 3, 10, 15, tzinfo=UTC)
    identity = DatasetIdentity(
        symbol="AAPL",
        provider="tiingo",
        provider_symbol="AAPL",
        venue="XNAS",
        asset_class="stock",
        timeframe="1D",
        calendar="XNAS",
        currency="USD",
        price_basis="raw",
    )
    receipt = FetchReceipt.create(
        identity=identity,
        requested_start=start,
        requested_end=end,
        fetched_at=fetched_at,
        adapter_version="1",
        parser_version="1",
        response_sha256=hashlib.sha256(raw).hexdigest(),
        response_bytes=len(raw),
        row_count=len(rows),
        action_count=0,
        request_metadata={"endpoint": "/tiingo/daily/AAPL/prices"},
    )
    return FetchResult(
        symbol="AAPL",
        bars=_bars(rows),
        actions=[],
        identity=identity,
        receipt=receipt,
        raw_response=raw,
    )


def _legacy_store(root: Path) -> ParquetStore:
    store = ParquetStore(root)
    store.write_bars("AAPL", _bars([("2026-07-31", 100.0), ("2026-08-03", 101.0)]))
    store.write_actions("AAPL", [])
    store.write_provenance("AAPL", source="yfinance", adapter_version="1", parser_version="2")
    return store


def test_stage_and_promote_merges_corrections_and_writes_v2_provenance(tmp_path: Path) -> None:
    store = _legacy_store(tmp_path)
    result = _result(
        [("2026-08-03", 101.5), ("2026-08-04", 102.0)],
        start=date(2026, 8, 3),
        end=date(2026, 8, 4),
    )

    outcome = stage_and_promote(store, result, authoritative_source="tiingo")

    assert outcome.status == "promoted"
    assert store.read_bars("AAPL")["close"].to_list() == [100.0, 101.5, 102.0]
    provenance = store.read_provenance("AAPL")
    assert provenance is not None
    assert provenance["schema_version"] == 2
    assert provenance["source"] == "tiingo"
    dataset = provenance["dataset"]
    assert isinstance(dataset, dict) and dataset["venue"] == "XNAS"
    assert result.receipt is not None
    receipt_dir = tmp_path / "receipts" / "tiingo" / result.receipt.receipt_id
    assert (receipt_dir / "response.bin").read_bytes() == b"payload"
    assert (receipt_dir / "receipt.json").exists()
    assert not store.promotion_pending("AAPL")
    quality = json.loads(outcome.quality_path.read_text(encoding="utf-8"))
    correction = quality["corrections"][0]
    assert correction["timestamp"] == "2026-08-03T00:00:00+00:00"
    assert correction["old_sha256"] != correction["new_sha256"]
    assert stage_and_promote(store, result, authoritative_source="tiingo") == outcome


def test_cross_source_difference_quarantines_and_preserves_canonical(tmp_path: Path) -> None:
    store = _legacy_store(tmp_path)
    result = _result(
        [("2026-08-03", 120.0)],
        start=date(2026, 8, 3),
        end=date(2026, 8, 3),
    )

    with pytest.raises(DataError, match="quarantined"):
        stage_and_promote(store, result, authoritative_source="tiingo")

    assert store.read_bars("AAPL")["close"].to_list() == [100.0, 101.0]
    assert result.receipt is not None
    quarantine = tmp_path / "quarantine" / "tiingo" / result.receipt.receipt_id
    report = json.loads((quarantine / "quality.json").read_text())
    assert report["status"] == "quarantined"
    assert any("price_difference" in item for item in report["critical_errors"])


def test_missing_existing_session_quarantines(tmp_path: Path) -> None:
    store = _legacy_store(tmp_path)
    result = _result(
        [("2026-08-03", 101.0)],
        start=date(2026, 7, 31),
        end=date(2026, 8, 3),
    )
    with pytest.raises(DataError, match="missing_existing_session"):
        stage_and_promote(store, result, authoritative_source="tiingo")


def test_initial_calendar_gap_quarantines_without_canonical_history(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    result = _result(
        [("2026-08-03", 101.0), ("2026-08-05", 103.0)],
        start=date(2026, 8, 3),
        end=date(2026, 8, 5),
    )
    with pytest.raises(DataError, match="calendar_gap:2026-08-04"):
        stage_and_promote(store, result, authoritative_source="tiingo")


def test_invalid_ohlc_and_duplicates_are_quarantined(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    result = _result(
        [("2026-08-03", 101.0), ("2026-08-03", 101.0)],
        start=date(2026, 8, 3),
        end=date(2026, 8, 3),
    )
    result.bars[0, "low"] = 200.0
    with pytest.raises(DataError, match="duplicate_timestamps"):
        stage_and_promote(store, result, authoritative_source="tiingo")
    assert result.receipt is not None
    report = json.loads(
        (
            tmp_path / "quarantine" / "tiingo" / result.receipt.receipt_id / "quality.json"
        ).read_text()
    )
    assert "duplicate_timestamps" in report["critical_errors"]
    assert "invalid_ohlcv:0" in report["critical_errors"]


@pytest.mark.parametrize("bad_close", [0.0, float("nan")])
def test_nonpositive_or_nonfinite_candidate_prices_quarantine(
    tmp_path: Path, bad_close: float
) -> None:
    store = ParquetStore(tmp_path)
    result = _result([("2026-08-03", 101.0)], start=date(2026, 8, 3), end=date(2026, 8, 3))
    result.bars[0, "open"] = bad_close
    with pytest.raises(DataError, match="invalid_ohlcv"):
        stage_and_promote(store, result, authoritative_source="tiingo")


def test_explicit_repair_promotes_exact_quarantined_receipt(tmp_path: Path) -> None:
    store = _legacy_store(tmp_path)
    result = _result(
        [("2026-08-03", 120.0)],
        start=date(2026, 8, 3),
        end=date(2026, 8, 3),
    )
    with pytest.raises(DataError):
        stage_and_promote(store, result, authoritative_source="tiingo")

    assert result.receipt is not None
    outcome = promote_quarantined(
        store,
        provider="tiingo",
        receipt_id=result.receipt.receipt_id,
        approve_differences=True,
    )
    assert outcome.status == "promoted"
    assert store.read_bars("AAPL")["close"].to_list() == [100.0, 120.0]
    assert stage_and_promote(store, result, authoritative_source="tiingo") == outcome


def test_repair_rejects_candidate_identity_tampering(tmp_path: Path) -> None:
    store = _legacy_store(tmp_path)
    result = _result(
        [("2026-08-03", 120.0)],
        start=date(2026, 8, 3),
        end=date(2026, 8, 3),
    )
    with pytest.raises(DataError):
        stage_and_promote(store, result, authoritative_source="tiingo")
    assert result.receipt is not None
    quality_path = tmp_path / "quarantine" / "tiingo" / result.receipt.receipt_id / "quality.json"
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    quality["provider"] = "yfinance"
    quality_path.write_text(json.dumps(quality), encoding="utf-8")

    with pytest.raises(DataError, match="candidate identity does not match"):
        promote_quarantined(
            store,
            provider="tiingo",
            receipt_id=result.receipt.receipt_id,
            approve_differences=True,
        )


def test_repair_rejects_tampered_stored_receipt_bytes(tmp_path: Path) -> None:
    store = _legacy_store(tmp_path)
    result = _result(
        [("2026-08-03", 120.0)],
        start=date(2026, 8, 3),
        end=date(2026, 8, 3),
    )
    with pytest.raises(DataError):
        stage_and_promote(store, result, authoritative_source="tiingo")
    assert result.receipt is not None
    receipt_root = tmp_path / "receipts" / "tiingo" / result.receipt.receipt_id
    (receipt_root / "response.bin").write_bytes(b"tampered")

    with pytest.raises(DataError, match="stored receipt response hash/length"):
        promote_quarantined(
            store,
            provider="tiingo",
            receipt_id=result.receipt.receipt_id,
            approve_differences=True,
        )


def test_receipt_bytes_are_content_verified(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    result = _result(
        [("2026-08-03", 101.0)],
        start=date(2026, 8, 3),
        end=date(2026, 8, 3),
    )
    bad = FetchResult(
        symbol=result.symbol,
        bars=result.bars,
        actions=result.actions,
        identity=result.identity,
        receipt=result.receipt,
        raw_response=b"different",
    )
    with pytest.raises(DataError, match="response hash"):
        stage_and_promote(store, bad, authoritative_source="tiingo")


def test_non_authoritative_source_can_stage_but_not_promote(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    result = _result(
        [("2026-08-03", 101.0)],
        start=date(2026, 8, 3),
        end=date(2026, 8, 3),
    )
    with pytest.raises(DataError, match="not authoritative"):
        stage_and_promote(store, result, authoritative_source="yfinance")


@pytest.mark.parametrize("threshold", [-0.01, float("nan"), float("inf")])
def test_cross_source_threshold_must_be_finite_and_nonnegative(
    tmp_path: Path, threshold: float
) -> None:
    result = _result(
        [("2026-08-03", 101.0)],
        start=date(2026, 8, 3),
        end=date(2026, 8, 3),
    )
    with pytest.raises(DataError, match="price-difference threshold"):
        stage_and_promote(
            ParquetStore(tmp_path),
            result,
            authoritative_source="tiingo",
            max_cross_source_price_difference=threshold,
        )


def test_cross_source_comparison_rejects_corrupt_canonical_close(tmp_path: Path) -> None:
    store = _legacy_store(tmp_path)
    corrupt = store.read_bars("AAPL")
    corrupt[1, "close"] = 0.0
    store.write_bars("AAPL", corrupt)
    result = _result(
        [("2026-08-03", 101.0)],
        start=date(2026, 8, 3),
        end=date(2026, 8, 3),
    )
    with pytest.raises(DataError, match="canonical comparison requires a finite positive close"):
        stage_and_promote(store, result, authoritative_source="tiingo")


def test_failed_promotion_restores_exact_previous_canonical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _legacy_store(tmp_path)
    before_bars = store._bars_path("AAPL").read_bytes()  # noqa: SLF001
    before_actions = store._actions_path("AAPL").read_bytes()  # noqa: SLF001
    before_provenance = store._provenance_path("AAPL").read_bytes()  # noqa: SLF001
    result = _result(
        [("2026-08-03", 101.5), ("2026-08-04", 102.0)],
        start=date(2026, 8, 3),
        end=date(2026, 8, 4),
    )

    def fail_actions(symbol: str, actions: list[object]) -> Path:
        del symbol, actions
        raise OSError("injected promotion failure")

    monkeypatch.setattr(store, "write_actions", fail_actions)
    with pytest.raises(OSError, match="injected promotion failure"):
        stage_and_promote(store, result, authoritative_source="tiingo")

    assert store._bars_path("AAPL").read_bytes() == before_bars  # noqa: SLF001
    assert store._actions_path("AAPL").read_bytes() == before_actions  # noqa: SLF001
    assert store._provenance_path("AAPL").read_bytes() == before_provenance  # noqa: SLF001
    assert not store.promotion_pending("AAPL")


def test_explicit_rollback_recovers_after_interrupted_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _legacy_store(tmp_path)
    before = store._bars_path("AAPL").read_bytes()  # noqa: SLF001
    result = _result(
        [("2026-08-03", 101.5), ("2026-08-04", 102.0)],
        start=date(2026, 8, 3),
        end=date(2026, 8, 4),
    )
    restore = pipeline._restore_promotion_backup  # noqa: SLF001

    def interrupted(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise OSError("simulated process interruption")

    def fail_write(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise OSError("write failed")

    monkeypatch.setattr(pipeline, "_restore_promotion_backup", interrupted)
    monkeypatch.setattr(store, "write_actions", fail_write)
    with pytest.raises(OSError, match="simulated process interruption"):
        stage_and_promote(store, result, authoritative_source="tiingo")
    assert store.promotion_pending("AAPL")

    monkeypatch.setattr(pipeline, "_restore_promotion_backup", restore)
    rollback_interrupted_promotion(store, symbol="AAPL", acknowledge=True)
    assert store._bars_path("AAPL").read_bytes() == before  # noqa: SLF001
    assert not store.promotion_pending("AAPL")


@pytest.mark.parametrize("missing", ["identity", "receipt", "raw_response"])
def test_ingestion_requires_complete_receipt_backing(tmp_path: Path, missing: str) -> None:
    result = _result([("2026-08-03", 101.0)], start=date(2026, 8, 3), end=date(2026, 8, 3))
    with pytest.raises(DataError, match="receipt-backed"):
        stage_and_promote(
            ParquetStore(tmp_path),
            replace(result, **cast(Any, {missing: None})),
            authoritative_source="tiingo",
        )


def test_ingestion_rejects_identity_and_count_mismatches(tmp_path: Path) -> None:
    result = _result([("2026-08-03", 101.0)], start=date(2026, 8, 3), end=date(2026, 8, 3))
    assert result.identity is not None and result.receipt is not None
    with pytest.raises(DataError, match="symbol does not match"):
        stage_and_promote(
            ParquetStore(tmp_path / "identity"),
            replace(result, identity=replace(result.identity, symbol="MSFT")),
            authoritative_source="tiingo",
        )
    with pytest.raises(DataError, match="counts do not match"):
        stage_and_promote(
            ParquetStore(tmp_path / "counts"),
            replace(result, receipt=replace(result.receipt, row_count=2)),
            authoritative_source="tiingo",
        )


def test_corrupt_or_conflicting_immutable_receipt_is_rejected(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    result = _result([("2026-08-03", 101.0)], start=date(2026, 8, 3), end=date(2026, 8, 3))
    stage_and_promote(store, result, authoritative_source="tiingo")
    assert result.receipt is not None
    root = tmp_path / "receipts" / "tiingo" / result.receipt.receipt_id
    (root / "receipt.json").write_text("not-json", encoding="utf-8")
    with pytest.raises(DataError, match="corrupt immutable receipt"):
        stage_and_promote(store, result, authoritative_source="tiingo")
    (root / "receipt.json").write_text("{}", encoding="utf-8")
    with pytest.raises(DataError, match="immutable receipt conflict"):
        stage_and_promote(store, result, authoritative_source="tiingo")


def test_quality_gate_rejects_invalid_calendar_and_conflicting_actions(tmp_path: Path) -> None:
    result = _result([("2026-08-03", 101.0)], start=date(2026, 8, 3), end=date(2026, 8, 3))
    assert result.identity is not None
    invalid_calendar = replace(result, identity=replace(result.identity, calendar="NOPE"))
    with pytest.raises(DataError, match="invalid_exchange_calendar"):
        stage_and_promote(
            ParquetStore(tmp_path / "calendar"), invalid_calendar, authoritative_source="tiingo"
        )

    store = _legacy_store(tmp_path / "actions")
    old = CorporateAction(
        symbol="AAPL", action_type=ActionType.DIVIDEND, ex_date=date(2026, 8, 3), amount=0.5
    )
    new = CorporateAction(
        symbol="AAPL", action_type=ActionType.DIVIDEND, ex_date=date(2026, 8, 3), amount=0.6
    )
    store.write_actions("AAPL", [old])
    assert result.receipt is not None
    conflict = replace(result, actions=[new], receipt=replace(result.receipt, action_count=1))
    with pytest.raises(DataError, match="corporate_action_conflict"):
        stage_and_promote(store, conflict, authoritative_source="tiingo")


def test_canonical_history_without_provenance_records_warning(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    store.write_bars("AAPL", _bars([("2026-08-03", 101.0)]))
    result = _result([("2026-08-03", 101.0)], start=date(2026, 8, 3), end=date(2026, 8, 3))
    outcome = stage_and_promote(store, result, authoritative_source="tiingo")
    quality = json.loads(outcome.quality_path.read_text(encoding="utf-8"))
    assert quality["warnings"] == ["canonical_source_unknown"]


@pytest.mark.parametrize(
    ("quality", "match"),
    [
        ("not-json", "corrupt candidate quality"),
        ("[]", "invalid candidate quality"),
        ("{}", "invalid candidate symbol"),
        ('{"symbol":"AAPL"}', "invalid candidate provider"),
        ('{"symbol":"AAPL","provider":"tiingo"}', "invalid candidate identity"),
    ],
)
def test_candidate_promotion_rejects_malformed_quality_documents(
    tmp_path: Path, quality: str, match: str
) -> None:
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "quality.json").write_text(quality, encoding="utf-8")
    with pytest.raises(DataError, match=match):
        pipeline._promote_candidate(  # noqa: SLF001
            ParquetStore(tmp_path / "store"), candidate, approved_repair=False
        )


def test_rollback_requires_acknowledgement_valid_marker_and_safe_reference(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    with pytest.raises(DataError, match="acknowledge"):
        rollback_interrupted_promotion(store, symbol="AAPL", acknowledge=False)
    with pytest.raises(DataError, match="no interrupted"):
        rollback_interrupted_promotion(store, symbol="AAPL", acknowledge=True)
    marker = store._promotion_path("AAPL")  # noqa: SLF001
    marker.parent.mkdir(parents=True)
    marker.write_text("not-json", encoding="utf-8")
    with pytest.raises(DataError, match="corrupt promotion marker"):
        rollback_interrupted_promotion(store, symbol="AAPL", acknowledge=True)
    marker.write_text(json.dumps({"backup": "../outside"}), encoding="utf-8")
    with pytest.raises(DataError, match="invalid promotion backup reference"):
        rollback_interrupted_promotion(store, symbol="AAPL", acknowledge=True)


@pytest.mark.parametrize(
    ("manifest", "filename", "contents", "match"),
    [
        ("not-json", None, None, "corrupt promotion backup"),
        ("[]", None, None, "invalid promotion backup"),
        ('{"schema_version":1,"symbol":"MSFT","files":{}}', None, None, "does not match"),
        (
            '{"schema_version":1,"symbol":"AAPL","files":{"bars":{}}}',
            None,
            None,
            "invalid bars entry",
        ),
        (
            '{"schema_version":1,"symbol":"AAPL","files":{"bars":{"present":true,"filename":"../bars.parquet","sha256":"x"}}}',
            None,
            None,
            "invalid bars filename",
        ),
        (
            '{"schema_version":1,"symbol":"AAPL","files":{"bars":{"present":true,"filename":"bars.parquet","sha256":"x"}}}',
            None,
            None,
            "missing bars bytes",
        ),
        (
            '{"schema_version":1,"symbol":"AAPL","files":{"bars":{"present":true,"filename":"bars.parquet","sha256":"x"}}}',
            "bars.parquet",
            "bytes",
            "hash mismatch",
        ),
    ],
)
def test_promotion_backup_validation_fails_closed(
    tmp_path: Path,
    manifest: str,
    filename: str | None,
    contents: str | None,
    match: str,
) -> None:
    backup = tmp_path / "backup"
    backup.mkdir()
    (backup / "manifest.json").write_text(manifest, encoding="utf-8")
    if filename is not None and contents is not None:
        (backup / filename).write_text(contents, encoding="utf-8")
    with pytest.raises(DataError, match=match):
        pipeline._restore_promotion_backup(  # noqa: SLF001
            ParquetStore(tmp_path / "store"), symbol="AAPL", backup_root=backup
        )
