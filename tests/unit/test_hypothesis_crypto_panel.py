"""Provider-native frozen crypto screens; no network or owner database."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import numpy as np
import polars as pl
import pytest

from alpha_cli import _crypto_panel as crypto
from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoQualityReportV1
from alpha_data.crypto.quality import QUALITY_METHOD_VERSION
from tests.fixtures.hypothesis_scan_fixtures import frozen_crypto


def test_freeze_verifies_only_selected_artifacts_and_their_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_data.crypto import storage

    store = frozen_crypto(tmp_path)
    inventory = cast(tuple[dict[str, Any], ...], store.inventory())
    selected = next(
        item
        for item in inventory
        if item.get("dataset", {}).get("instrument") == "AAAUSDT"
        and item.get("dataset", {}).get("family") == "derivative_bars"
    )
    expected_keys = {selected["artifact_key"]}
    for parent_id in selected["input_manifest_ids"]:
        expected_keys.add(store.verify_manifest(parent_id)["artifact_key"])
    original = storage.sha256_file
    reads: list[str] = []

    def record(path: Path) -> str:
        reads.append(str(path.relative_to(store.bulk_root)))
        return original(path)

    monkeypatch.setattr(storage, "sha256_file", record)
    monkeypatch.setattr(crypto, "bulk_store", lambda _: store)
    result = crypto.freeze_crypto_inputs(
        tmp_path,
        {
            "symbols": ["AAAUSDT"],
            "as_of": "2020-03-02",
            "category": "linear",
            "signals": ["mom_30d"],
        },
    )
    assert [item["manifest_id"] for item in result] == [selected["manifest_id"]]
    assert set(reads) == expected_keys


@pytest.mark.parametrize(
    "corruption", ["selected_artifact", "raw_artifact", "raw_parent", "unrelated_metadata"]
)
def test_selective_discovery_preserves_integrity_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corruption: str
) -> None:
    import json

    store = frozen_crypto(tmp_path)
    inventory = cast(tuple[dict[str, Any], ...], store.inventory())
    selected = next(
        item
        for item in inventory
        if item.get("dataset", {}).get("instrument") == "AAAUSDT"
        and item.get("dataset", {}).get("family") == "derivative_bars"
    )
    if corruption == "selected_artifact":
        (store.bulk_root / str(selected["artifact_key"])).write_bytes(b"corrupt")
    elif corruption == "raw_artifact":
        parent = store.verify_manifest(selected["input_manifest_ids"][0])
        raw_path = store.bulk_root / "fixtures/raw-only.bin"
        raw_path.write_bytes((store.bulk_root / str(parent["artifact_key"])).read_bytes())
        distinct_parent = store._publish_manifest(
            {key: value for key, value in parent.items() if key != "manifest_id"}
            | {"artifact_key": "fixtures/raw-only.bin"}
        )
        store._publish_manifest(
            {key: value for key, value in selected.items() if key != "manifest_id"}
            | {"input_manifest_ids": [distinct_parent["manifest_id"]]}
        )
        raw_path.write_bytes(b"corrupt")
    else:
        identity = (
            selected["input_manifest_ids"][0]
            if corruption == "raw_parent"
            else next(
                item["manifest_id"]
                for item in inventory
                if item.get("dataset", {}).get("instrument") == "BBBUSDT"
            )
        )
        path = store.manifest_root / f"{identity}.json"
        changed = json.loads(path.read_text())
        changed["artifact_sha256"] = "0" * 64
        path.write_text(json.dumps(changed))
    monkeypatch.setattr(crypto, "bulk_store", lambda _: store)
    with pytest.raises(DataError, match="integrity failure"):
        crypto.freeze_crypto_inputs(
            tmp_path,
            {
                "symbols": ["AAAUSDT"],
                "as_of": "2020-03-02",
                "category": "linear",
                "signals": ["mom_30d"],
            },
        )


def dataset(family: str = "derivative_bars") -> dict[str, Any]:
    frequency, units, convention, _column = crypto.FAMILIES[family]
    return {
        "provider": "bybit",
        "venue": "bybit",
        "market_type": "linear",
        "family": family,
        "instrument": "BTCUSDT",
        "base_asset": "BTC",
        "quote_asset": "USDT",
        "frequency": frequency,
        "units": units,
        "timestamp_convention": convention,
        "schema_version": 1,
    }


@pytest.mark.bias_guard
def test_crypto_availability_boundaries_and_exact_overlap() -> None:
    midnight = datetime(2020, 2, 1, tzinfo=UTC)
    frame = pl.DataFrame(
        {
            "timestamp": [midnight - timedelta(days=1), midnight],
            "symbol": ["BTCUSDT"] * 2,
            "category": ["linear"] * 2,
            "close": [100.0, 1e9],
        }
    )
    values: dict[datetime, float] = {}
    crypto.merge_rows(values, frame, dataset(), as_of=midnight)
    assert values == {midnight: 100.0}
    crypto.merge_rows(values, frame.head(1), dataset(), as_of=midnight)
    with pytest.raises(DataError, match="overlap"):
        crypto.merge_rows(
            values,
            frame.head(1).with_columns(pl.lit(99.0).alias("close")),
            dataset(),
            as_of=midnight,
        )
    funding = pl.DataFrame(
        {
            "timestamp": [midnight, midnight + timedelta(seconds=1)],
            "symbol": ["BTCUSDT"] * 2,
            "category": ["linear"] * 2,
            "funding_rate": [0.01, 1e9],
        }
    )
    values = {}
    crypto.merge_rows(values, funding, dataset("funding"), as_of=midnight)
    assert values == {midnight: 0.01}


def test_complete_row_overlap_must_agree_even_when_close_agrees() -> None:
    midnight = datetime(2020, 2, 1, tzinfo=UTC)
    frame = pl.DataFrame(
        {
            "timestamp": [midnight - timedelta(days=1)],
            "symbol": ["BTCUSDT"],
            "category": ["linear"],
            "close": [100.0],
            "open": [99.0],
        }
    )
    values: dict[datetime, float] = {}
    signatures: dict[datetime, bytes] = {}
    crypto.merge_rows(values, frame, dataset(), as_of=midnight, row_signatures=signatures)
    with pytest.raises(DataError, match="complete-row overlap"):
        crypto.merge_rows(
            values,
            frame.with_columns(pl.lit(98.0).alias("open")),
            dataset(),
            as_of=midnight,
            row_signatures=signatures,
        )


def test_identity_and_correction_lineage_fail_closed() -> None:
    item: dict[str, Any] = {
        "manifest_id": "a",
        "dataset": dataset(),
        "artifact_sha256": "b" * 64,
        "quality": CryptoQualityReportV1(
            dataset_sha256="b" * 64,
            method_version=QUALITY_METHOD_VERSION,
            state="qualified",
            failures=(),
            warnings=(),
            observed_start=None,
            observed_end=None,
            row_count=1,
            correction_lineage=(),
        ).to_dict(),
    }
    crypto.validate_identity(item, previous=None)
    with pytest.raises(DataError, match="identity"):
        crypto.validate_identity({**item, "dataset": {**dataset(), "units": "USD"}}, previous=item)
    with pytest.raises(DataError, match="correction"):
        crypto.validate_identity(
            {**item, "quality": {**item["quality"], "correction_lineage": ["old"]}}, previous=None
        )


@pytest.mark.bias_guard
def test_crypto_signals_ignore_future_rows() -> None:
    days = [datetime(2020, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(45)]
    closes = np.array([[100 + i] for i in range(45)], dtype=float)
    observations = {
        "BTCUSDT": {
            "funding": {d: float(i + 1) / 100 for i, d in enumerate(days)},
            "open_interest": {d: float(100 + i) for i, d in enumerate(days)},
        }
    }
    before = crypto.daily_signals(
        days, ["BTCUSDT"], closes, observations, ["funding_z_30d", "oi_chg_7d", "mom_30d"]
    )
    observations["BTCUSDT"]["funding"][days[-1] + timedelta(seconds=1)] = 1e9
    after = crypto.daily_signals(days, ["BTCUSDT"], closes, observations, list(before))
    for name in before:
        np.testing.assert_equal(before[name], after[name])
    assert before["oi_chg_7d"][7, 0] == pytest.approx(107 / 100 - 1)


def test_late_raw_fetch_excludes_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Store:
        def metadata_inventory(self) -> tuple[dict[str, Any], ...]:
            return (
                {
                    "artifact_kind": "normalized",
                    "manifest_id": "n",
                    "dataset": dataset(),
                    "quality": {"state": "qualified"},
                    "input_manifest_ids": ["r"],
                },
            )

        def verify_manifest(self, _id: object) -> dict[str, Any]:
            if _id == "n":
                return self.metadata_inventory()[0]
            return {"receipt": {"fetched_at": "2020-02-02T00:00:00Z"}}

    monkeypatch.setattr(crypto, "bulk_store", lambda _: Store())
    with pytest.raises(DataError, match="no qualified"):
        crypto.freeze_crypto_inputs(
            tmp_path,
            {
                "symbols": ["BTCUSDT"],
                "as_of": "2020-02-01",
                "category": "linear",
                "signals": ["mom_30d"],
            },
        )


@pytest.mark.parametrize("defect", ["missing", "identity", "duplicate", "nan", "negative", "naive"])
def test_malformed_crypto_frames_fail_loud(defect: str) -> None:
    midnight = datetime(2020, 2, 1, tzinfo=UTC)
    frame = pl.DataFrame(
        {
            "timestamp": [midnight - timedelta(days=1)],
            "symbol": ["BTCUSDT"],
            "category": ["linear"],
            "close": [100.0],
        }
    )
    if defect == "missing":
        frame = frame.drop("close")
    elif defect == "identity":
        frame = frame.with_columns(pl.lit("inverse").alias("category"))
    elif defect == "duplicate":
        frame = pl.concat([frame, frame])
    elif defect == "naive":
        frame = frame.with_columns(pl.col("timestamp").dt.replace_time_zone(None))
    else:
        frame = frame.with_columns(pl.lit(float("nan") if defect == "nan" else -1.0).alias("close"))
    with pytest.raises(DataError):
        crypto.merge_rows({}, frame, dataset(), as_of=midnight)


def test_crypto_bulk_configuration_and_exact_replay_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_BULK_VOLUME_UUID", "")
    with pytest.raises(DataError, match="UUID"):
        crypto.bulk_store(tmp_path)
    monkeypatch.setenv("ALPHA_BULK_VOLUME_UUID", "fixture")
    monkeypatch.setenv("ALPHA_BULK_DATA_DIR", str(tmp_path / "bulk"))
    assert crypto.bulk_store(tmp_path).bulk_root == tmp_path / "bulk"
    store = frozen_crypto(tmp_path)
    monkeypatch.setattr(crypto, "bulk_store", lambda _: store)
    options = {
        "symbols": ["AAAUSDT", "BBBUSDT", "CCCUSDT"],
        "as_of": "2020-03-01",
        "category": "linear",
        "signals": ["mom_30d"],
    }
    inputs = crypto.freeze_crypto_inputs(tmp_path, options)
    inputs[0]["artifact_sha256"] = "0" * 64
    with pytest.raises(DataError, match="identity changed"):
        crypto.crypto_panel(tmp_path, {"options": options, "crypto_inputs": inputs})


@pytest.mark.parametrize("defect", ["warnings", "failures", "missing", "method", "schema", "rows"])
def test_crypto_quality_contract_is_reverified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    store = frozen_crypto(tmp_path)
    original = next(
        item
        for item in store.inventory()
        if item.get("artifact_kind") == "normalized"
        and isinstance(item.get("dataset"), dict)
        and cast(dict[str, Any], item["dataset"])["family"] == "derivative_bars"
    )
    manifest: dict[str, Any] = dict(original)
    quality = dict(manifest["quality"])
    manifest["quality"] = quality
    if defect in {"warnings", "failures"}:
        quality[defect] = ["not qualified"]
    elif defect == "missing":
        quality.pop("method_version")
    elif defect == "method":
        quality["method_version"] = "unknown"
    elif defect == "schema":
        manifest["dataset"] = {**manifest["dataset"], "schema_version": 9}
    else:
        quality["row_count"] = 1
    if defect != "rows":
        with pytest.raises(DataError):
            crypto.validate_identity(manifest, previous=None)
        return
    wrong = store._publish_manifest(
        {key: value for key, value in manifest.items() if key != "manifest_id"}
    )
    monkeypatch.setattr(crypto, "bulk_store", lambda _: store)
    options = {
        "symbols": [manifest["dataset"]["instrument"]],
        "as_of": "2020-03-01",
        "category": "linear",
        "signals": ["mom_30d"],
    }
    frozen = {key: wrong[key] for key in ("manifest_id", "dataset", "artifact_sha256")}
    with pytest.raises(DataError, match="row_count"):
        crypto.crypto_panel(tmp_path, {"options": options, "crypto_inputs": [frozen]})
