"""Snapshot comparisons distinguish descriptive measurements from missing evidence."""

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from alpha_cli.investigation_comparisons import ComparisonPlan, comparison_evidence
from alpha_core import DataError
from alpha_data.adapters.base import DatasetIdentity, FetchReceipt
from alpha_data.snapshot import create_snapshot, snapshot_manifest_hash
from alpha_data.source import PointInTimeSource
from alpha_data.store import ParquetStore


def snapshot(root: Path, *, provenance: bool = True) -> Path:
    store = ParquetStore(root / "store")
    ts = [datetime(2020, 1, day, tzinfo=UTC) for day in (1, 2, 3)]
    store.write_bars(
        "SPY",
        pl.DataFrame(
            {
                "ts": ts,
                **dict.fromkeys(("open", "high", "low", "close"), [100.0, 80.0, 900.0]),
                "volume": [1.0] * 3,
            }
        ),
    )
    if provenance:
        identity = DatasetIdentity(
            "SPY", "fixture", "SPY", "TEST", "etf", "1D", "XNYS", "USD", "raw"
        )
        receipt = FetchReceipt.create(
            identity=identity,
            requested_start=date(2020, 1, 1),
            requested_end=date(2020, 1, 3),
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            adapter_version="1",
            parser_version="1",
            response_sha256="a" * 64,
            response_bytes=10,
            row_count=3,
            action_count=0,
            request_metadata={},
        )
        store.write_provenance(
            "SPY",
            source="fixture",
            adapter_version="1",
            parser_version="1",
            identity=identity,
            receipt=receipt,
        )
    create_snapshot(
        store,
        root / "snapshots",
        "frozen",
        ["SPY"],
        source="fixture",
        adapter_version="1",
        parser_version="1",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    return root / "snapshots" / "frozen"


def plan(snap: Path, **updates: Any) -> ComparisonPlan:
    item = dict(
        snapshot_id="frozen",
        snapshot_sha256=snapshot_manifest_hash(snap),
        symbol="SPY",
        role="market",
    )
    item.update(updates)
    return ComparisonPlan.model_validate({"schema_version": 1, "series": [item]})


def packet() -> dict[str, Any]:
    return {
        "observations": {
            "execution": {"research_cutoff": "2020-01-02"},
            "drawdown_episodes": [
                {
                    "peak": "2020-01-01T00:00:00+00:00",
                    "trough": "2020-01-02T00:00:00+00:00",
                    "depth": 0.6,
                }
            ],
        }
    }


def test_exact_endpoint_prices_are_retrospective_not_causal(tmp_path: Path) -> None:
    snap = snapshot(tmp_path)
    result = comparison_evidence(packet(), plan(snap), tmp_path)
    series = result["series"][0]
    assert series["dataset"]["currency"] == "USD"
    assert series["historical_vintage"] == "unverified"
    window = series["windows"][0]
    assert window["status"] == "measured"
    assert window["price_change"] == pytest.approx(-0.2)
    assert window["observed_rows"] == 2
    assert window["schedule_coverage"] == "unverified"
    assert result["causal_attribution"] == "not_tested"
    assert result["quality_certification"] == "not_established"


def test_missing_provenance_is_blocked_not_a_price_claim(tmp_path: Path) -> None:
    snap = snapshot(tmp_path, provenance=False)
    result = comparison_evidence(packet(), plan(snap), tmp_path)
    assert result["series"][0]["blockers"] == ["versioned_provenance_required"]
    assert result["series"][0]["windows"] == []


def test_changed_snapshot_fails_loud(tmp_path: Path) -> None:
    snap = snapshot(tmp_path)
    frozen = plan(snap)
    (snap / "bars/SPY.parquet").write_bytes(b"corrupt")
    with pytest.raises(DataError, match="integrity"):
        comparison_evidence(packet(), frozen, tmp_path)


def rehash(snap: Path, kind: str = "bars") -> None:
    path = snap / "manifest.json"
    manifest = json.loads(path.read_text())
    entry = manifest["symbols"]["SPY"]
    entry[f"{kind}_sha256"] = hashlib.sha256(
        (snap / entry[f"{kind}_file"]).read_bytes()
    ).hexdigest()
    path.write_text(json.dumps(manifest))


@pytest.mark.bias_guard
def test_future_price_poison_has_discriminating_leaky_control(tmp_path: Path) -> None:
    snap = snapshot(tmp_path)
    before = comparison_evidence(packet(), plan(snap), tmp_path)["series"][0]["windows"]
    path = snap / "bars/SPY.parquet"
    frame = pl.read_parquet(path)
    poisoned = frame.with_columns(
        [
            pl.when(pl.col("ts").dt.day() == 3).then(1e6).otherwise(pl.col(c)).alias(c)
            for c in ("open", "high", "low", "close")
        ]
    )
    poisoned.write_parquet(path)
    rehash(snap)
    after = comparison_evidence(packet(), plan(snap), tmp_path)["series"][0]["windows"]
    assert before == after
    # The deliberately leaky whole-file endpoint changes, so the poison has discriminatory power.
    assert frame["close"][-1] / frame["close"][0] != poisoned["close"][-1] / poisoned["close"][0]


def test_sparse_input_blocks_endpoint_without_filling(tmp_path: Path) -> None:
    snap = snapshot(tmp_path)
    path = snap / "bars/SPY.parquet"
    pl.read_parquet(path).slice(0, 1).write_parquet(path)
    rehash(snap)
    window = comparison_evidence(packet(), plan(snap), tmp_path)["series"][0]["windows"][0]
    assert window["status"] == "blocked"
    assert window["blockers"] == ["missing_trough_session:2020-01-02"]
    assert "price_change" not in window


@pytest.mark.parametrize(
    "problem",
    [
        "manifest_path",
        "undeclared_actions",
        "symlink",
        "duplicate",
        "disordered",
        "intraday",
        "nonpositive",
    ],
)
def test_hash_valid_but_unsafe_inputs_rejected(tmp_path: Path, problem: str) -> None:
    snap = snapshot(tmp_path)
    path = snap / "bars/SPY.parquet"
    manifest = json.loads((snap / "manifest.json").read_text())
    if problem == "manifest_path":
        (snap / "bars/OTHER.parquet").write_bytes(path.read_bytes())
        manifest["symbols"]["SPY"]["bars_file"] = "bars/OTHER.parquet"
        (snap / "manifest.json").write_text(json.dumps(manifest))
    elif problem == "undeclared_actions":
        (snap / "actions/SPY.json").write_text("[]")
    elif problem == "symlink":
        target = tmp_path / "external.parquet"
        target.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(target)
    else:
        frame = pl.read_parquet(path)
        if problem == "duplicate":
            frame = pl.concat([frame, frame.slice(0, 1)])
        elif problem == "disordered":
            frame = frame.reverse()
        elif problem == "intraday":
            frame = frame.with_columns(pl.col("ts") + pl.duration(hours=1))
        else:
            frame = frame.with_columns(pl.lit(0.0).alias("close"))
        frame.write_parquet(path)
        rehash(snap)
    with pytest.raises((DataError, ValueError)):
        comparison_evidence(packet(), plan(snap), tmp_path)


@pytest.mark.parametrize(
    "updates",
    [
        {"symbol": "A/../B"},
        {"symbol": "A//B"},
        {"snapshot_id": "../other"},
        {"snapshot_sha256": "bad"},
        {"role": "causal"},
        {"extra": True},
    ],
)
def test_bad_selectors_rejected(tmp_path: Path, updates: dict[str, Any]) -> None:
    snap = snapshot(tmp_path)
    with pytest.raises(ValueError):
        plan(snap, **updates)


def test_duplicate_unbounded_or_empty_plan_rejected(tmp_path: Path) -> None:
    item = plan(snapshot(tmp_path)).model_dump()["series"][0]
    for series in ([], [item, item], [dict(item, symbol=f"S{i}") for i in range(5)]):
        with pytest.raises(ValueError):
            ComparisonPlan.model_validate({"series": series})


def test_missing_member_and_no_episodes_are_explicit(tmp_path: Path) -> None:
    snap = snapshot(tmp_path)
    result = comparison_evidence(packet(), plan(snap, symbol="QQQ"), tmp_path)
    assert result["series"][0]["blockers"] == ["snapshot_member_missing"]
    empty = packet()
    empty["observations"]["drawdown_episodes"] = []
    assert comparison_evidence(empty, plan(snap), tmp_path)["series"][0]["windows"] == []


def test_large_unselected_file_rejected_before_full_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import alpha_cli.investigation_comparisons as module

    snap = snapshot(tmp_path)
    frozen = plan(snap)
    huge = snap / "bars/HUGE.parquet"
    with huge.open("wb") as stream:
        stream.truncate(33 * 1024 * 1024)
    manifest = json.loads((snap / "manifest.json").read_text())
    manifest["symbols"]["HUGE"] = {"bars_file": "bars/HUGE.parquet", "bars_sha256": "f" * 64}
    (snap / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(module, "snapshot_manifest_hash", lambda _: pytest.fail("payload hashed"))
    with pytest.raises(DataError, match="size limit"):
        comparison_evidence(packet(), frozen, tmp_path)


def test_compressed_row_limit_precedes_pit_materialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snap = snapshot(tmp_path)
    path = snap / "bars/SPY.parquet"
    pl.concat([pl.read_parquet(path)] * 16_667).write_parquet(path)
    rehash(snap)
    monkeypatch.setattr(PointInTimeSource, "as_of", lambda *args: pytest.fail("bars materialized"))
    with pytest.raises(DataError, match="row limit"):
        comparison_evidence(packet(), plan(snap), tmp_path)


@pytest.mark.parametrize(
    "problem",
    [
        "wrong_hash",
        "wrong_identity",
        "source",
        "schema",
        "many_episodes",
        "future_episode",
        "nonfinite_ratio",
    ],
)
def test_contract_errors_are_not_missing_data(tmp_path: Path, problem: str) -> None:
    snap = snapshot(tmp_path)
    evidence = packet()
    frozen = plan(snap)
    path = snap / "manifest.json"
    manifest = json.loads(path.read_text())
    if problem == "wrong_hash":
        frozen = plan(snap, snapshot_sha256="0" * 64)
    elif problem in {"wrong_identity", "source"}:
        manifest["snapshot_id" if problem == "wrong_identity" else "source"] = "OTHER"
        path.write_text(json.dumps(manifest))
        frozen = plan(snap)
    elif problem in {"schema", "nonfinite_ratio"}:
        bars_path = snap / "bars/SPY.parquet"
        frame = pl.read_parquet(bars_path)
        if problem == "schema":
            frame = frame.with_columns(pl.lit("extra").alias("unbound"))
        else:
            frame = frame.with_columns(
                [
                    pl.when(pl.col("ts").dt.day() == 1).then(1e-300).otherwise(1e300).alias(c)
                    for c in ("open", "high", "low", "close")
                ]
            )
        frame.write_parquet(bars_path)
        rehash(snap)
        frozen = plan(snap)
    elif problem == "many_episodes":
        evidence["observations"]["drawdown_episodes"] *= 4
    else:
        evidence["observations"]["drawdown_episodes"][0]["trough"] = "2020-01-03T00:00:00+00:00"
    with pytest.raises(DataError):
        comparison_evidence(evidence, frozen, tmp_path)


@pytest.mark.parametrize(
    "problem",
    [
        "manifest_size",
        "member_count",
        "entry",
        "file_type",
        "escape",
        "missing_file",
        "total_size",
        "root_symlink",
    ],
)
def test_snapshot_preflight_bounds_and_paths(tmp_path: Path, problem: str) -> None:
    snap = snapshot(tmp_path)
    frozen = plan(snap)
    path = snap / "manifest.json"
    manifest = json.loads(path.read_text())
    if problem == "manifest_size":
        path.write_text(" " * (1024 * 1024 + 1))
    elif problem == "root_symlink":
        target = tmp_path / "redirected"
        snap.rename(target)
        snap.symlink_to(target, target_is_directory=True)
    else:
        entry = manifest["symbols"]["SPY"]
        if problem == "member_count":
            manifest["symbols"] = dict.fromkeys(map(str, range(129)), entry)
        elif problem == "entry":
            manifest["symbols"]["SPY"] = []
        elif problem == "file_type":
            entry["bars_file"] = 123
        elif problem == "escape":
            entry["bars_file"] = "../outside"
        elif problem == "missing_file":
            entry["bars_file"] = "bars/missing.parquet"
        else:
            for i in range(5):
                relative = f"bars/BIG{i}.parquet"
                with (snap / relative).open("wb") as stream:
                    stream.truncate(27 * 1024 * 1024)
                manifest["symbols"][f"BIG{i}"] = {"bars_file": relative, "bars_sha256": "0" * 64}
        path.write_text(json.dumps(manifest))
    with pytest.raises(DataError):
        comparison_evidence(packet(), frozen, tmp_path)


def test_source_drift_during_read_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import alpha_cli.investigation_comparisons as module

    frozen = plan(snapshot(tmp_path))
    hashes = iter([frozen.series[0].snapshot_sha256, "0" * 64])
    monkeypatch.setattr(module, "_snapshot_hash", lambda _: next(hashes))
    with pytest.raises(DataError, match="changed during read"):
        comparison_evidence(packet(), frozen, tmp_path)


def test_one_missing_proxy_does_not_hide_other_measurements(tmp_path: Path) -> None:
    frozen = plan(snapshot(tmp_path)).model_dump()
    frozen["series"].append(dict(frozen["series"][0], symbol="QQQ", role="sector"))
    result = comparison_evidence(packet(), ComparisonPlan.model_validate(frozen), tmp_path)
    assert result["series"][0]["windows"][0]["status"] == "measured"
    assert result["series"][1]["blockers"] == ["snapshot_member_missing"]


@pytest.mark.parametrize("dtype", [pl.Int64, pl.Datetime("us")])
def test_timestamp_storage_contract_is_not_coerced(tmp_path: Path, dtype: pl.DataType) -> None:
    snap = snapshot(tmp_path)
    path = snap / "bars/SPY.parquet"
    pl.read_parquet(path).with_columns(pl.col("ts").cast(dtype)).write_parquet(path)
    rehash(snap)
    with pytest.raises(DataError, match="timezone-aware"):
        comparison_evidence(packet(), plan(snap), tmp_path)
