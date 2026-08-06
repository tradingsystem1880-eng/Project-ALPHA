"""Manifest-v3 artifact contracts and immutable publication."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from alpha_backtest.results import BacktestResult, FillTrace, OrderTrace
from alpha_cli import _artifacts
from alpha_cli.run_projection import chart_bundle
from alpha_core import (
    ChartAnchor,
    ChartAnnotationTrace,
    DataError,
    DecisionTrace,
    IndicatorTrace,
)


def _identity() -> dict[str, object]:
    return {
        "run_identity_version": 3,
        "execution_fingerprint": "a" * 64,
        "strategy_fingerprint": "b" * 64,
        "source_fingerprint": "c" * 64,
        "snapshot_hash": None,
    }


def _write_equity(path: Path, values: list[float]) -> None:
    frame = pl.DataFrame({"step": list(range(len(values))), "equity": values})
    _artifacts.publish_artifact(path, frame.write_parquet)


def test_v3_manifest_pins_schema_hash_size_and_rows(tmp_path: Path) -> None:
    rdir = tmp_path / "runs" / "0123456789abcdef"
    artifact = rdir / "equity_curve.parquet"
    _write_equity(artifact, [1.0, 1.1, 1.2])

    _artifacts.write_manifest(
        rdir,
        {
            "run_id": rdir.name,
            "command": "test_fixture",
            **_identity(),
        },
    )

    manifest = json.loads((rdir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 3
    assert manifest["run_identity_version"] == 3
    assert manifest["artifact_contract_version"] == 3
    assert set(manifest["artifacts"]) == {"equity_curve.parquet"}
    entry = manifest["artifacts"]["equity_curve.parquet"]
    assert entry["sha256"] == hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert entry["size_bytes"] == artifact.stat().st_size
    assert entry["rows"] == 3
    assert entry["schema"] == [
        {"name": "step", "dtype": "Int64"},
        {"name": "equity", "dtype": "Float64"},
    ]
    assert _artifacts.read_manifest(rdir) == manifest


def test_v3_reader_detects_artifact_tampering(tmp_path: Path) -> None:
    rdir = tmp_path / "runs" / "0123456789abcdef"
    artifact = rdir / "equity_curve.parquet"
    _write_equity(artifact, [1.0, 1.1])
    _artifacts.write_manifest(
        rdir,
        {"run_id": rdir.name, "command": "test_fixture", **_identity()},
    )
    artifact.write_bytes(artifact.read_bytes() + b"tampered")

    with pytest.raises(DataError, match="artifact .* (hash|size) mismatch"):
        _artifacts.read_manifest(rdir)


def test_v3_contract_hashes_non_parquet_exports_and_prevents_replacement(tmp_path: Path) -> None:
    rdir = tmp_path / "runs" / "0123456789abcdef"
    report = rdir / "tearsheet.html"
    _artifacts.publish_artifact(report, lambda path: path.write_text("<html>v1</html>"))
    _artifacts.write_manifest(
        rdir,
        {"run_id": rdir.name, "command": "test_fixture", **_identity()},
    )

    manifest = _artifacts.read_manifest(rdir)
    entry = manifest["artifacts"]["tearsheet.html"]
    assert entry["media_type"] == "text/html"
    assert entry["schema"] is None and entry["rows"] is None
    with pytest.raises(DataError, match="immutable artifact"):
        _artifacts.publish_artifact(report, lambda path: path.write_text("<html>v2</html>"))


def test_published_artifact_is_idempotent_but_never_replaced(tmp_path: Path) -> None:
    rdir = tmp_path / "runs" / "0123456789abcdef"
    artifact = rdir / "equity_curve.parquet"
    _write_equity(artifact, [1.0, 1.1])
    _artifacts.write_manifest(
        rdir,
        {"run_id": rdir.name, "command": "test_fixture", **_identity()},
    )
    original_artifact = artifact.read_bytes()
    original_manifest = (rdir / "manifest.json").read_bytes()

    _write_equity(artifact, [1.0, 1.1])
    _artifacts.write_manifest(
        rdir,
        {"run_id": rdir.name, "command": "test_fixture", **_identity()},
    )
    assert artifact.read_bytes() == original_artifact
    assert (rdir / "manifest.json").read_bytes() == original_manifest

    with pytest.raises(DataError, match="immutable artifact"):
        _write_equity(artifact, [1.0, 9.9])
    assert artifact.read_bytes() == original_artifact


def test_manifest_rejects_replacement_and_incomplete_required_contract(tmp_path: Path) -> None:
    rdir = tmp_path / "runs" / "0123456789abcdef"
    rdir.mkdir(parents=True)
    original = {
        "run_id": rdir.name,
        "command": "test_fixture",
        "label": "original",
        **_identity(),
    }
    _artifacts.write_manifest(rdir, original)

    with pytest.raises(DataError, match="immutable manifest"):
        _artifacts.write_manifest(rdir, {**original, "label": "replacement"})

    incomplete = tmp_path / "runs" / "fedcba9876543210"
    incomplete.mkdir(parents=True)
    with pytest.raises(DataError, match="missing artifacts"):
        _artifacts.write_manifest(
            incomplete,
            {"run_id": incomplete.name, "command": "backtest_run", **_identity()},
        )


def test_research_pilot_requires_typed_acceptance_at_publication_and_read(tmp_path: Path) -> None:
    incomplete = tmp_path / "runs" / "1111111111111111"
    for filename in (
        "events.json",
        "topology.json",
        "power.json",
        "chart-data.json",
        "detector-validity.png",
        "report.md",
    ):

        def write_required(path: Path, *, body: bytes = filename.encode("utf-8")) -> None:
            path.write_bytes(body)

        _artifacts.publish_artifact(incomplete / filename, write_required)
    with pytest.raises(DataError, match="missing artifacts.*d0_acceptance.json"):
        _artifacts.write_manifest(
            incomplete,
            {"run_id": incomplete.name, "command": "research_pilot", **_identity()},
        )

    forged = tmp_path / "runs" / "2222222222222222"
    forged.mkdir(parents=True)
    manifest = {
        "schema_version": 3,
        "artifact_contract_version": 3,
        "run_id": forged.name,
        "command": "research_pilot",
        "artifacts": {},
        **_identity(),
    }
    (forged / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(DataError, match="research_pilot artifact set mismatch"):
        _artifacts.read_manifest(forged)


def test_manifest_rejects_a_different_concurrent_winner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rdir = tmp_path / "runs" / "0123456789abcdef"
    rdir.mkdir(parents=True)

    def collide(source: Path, destination: Path) -> None:
        winner = json.loads(source.read_text(encoding="utf-8"))
        winner["label"] = "concurrent-winner"
        destination.write_text(json.dumps(winner), encoding="utf-8")
        raise FileExistsError

    monkeypatch.setattr("alpha_cli._artifacts.os.link", collide)
    with pytest.raises(DataError, match="concurrently published with different content"):
        _artifacts.write_manifest(
            rdir,
            {"run_id": rdir.name, "command": "test_fixture", **_identity()},
        )
    assert not list(rdir.glob(".manifest.json.*.tmp"))


def test_manifest_reader_rejects_corrupt_and_non_object_json(tmp_path: Path) -> None:
    rdir = tmp_path / "runs" / "0123456789abcdef"
    rdir.mkdir(parents=True)
    manifest = rdir / "manifest.json"

    manifest.write_text("{", encoding="utf-8")
    with pytest.raises(DataError, match="corrupt run manifest"):
        _artifacts.read_manifest(rdir)

    manifest.write_text("[]", encoding="utf-8")
    with pytest.raises(DataError, match="expected a JSON object"):
        _artifacts.read_manifest(rdir)


@pytest.mark.parametrize("schema_version", [1, 2])
def test_v1_v2_manifests_remain_readable(tmp_path: Path, schema_version: int) -> None:
    rdir = tmp_path / "runs" / f"{schema_version:016x}"
    rdir.mkdir(parents=True)
    legacy = {"schema_version": schema_version, "run_id": rdir.name, "command": "legacy"}
    (rdir / "manifest.json").write_text(json.dumps(legacy), encoding="utf-8")
    assert _artifacts.read_manifest(rdir) == legacy


def test_v3_manifest_requires_identity_fields(tmp_path: Path) -> None:
    rdir = tmp_path / "runs" / "0123456789abcdef"
    with pytest.raises(DataError, match="run_identity_version"):
        _artifacts.write_manifest(rdir, {"run_id": rdir.name, "command": "test_fixture"})


def test_later_decision_keeps_one_global_id_across_trace_evidence_and_projection(
    tmp_path: Path,
) -> None:
    """A fill before decision two must not make its sidecars point at event two (the order)."""
    first_close = datetime(2026, 1, 5, 23, tzinfo=UTC)
    next_open = datetime(2026, 1, 6, tzinfo=UTC)
    second_close = datetime(2026, 1, 6, 23, tzinfo=UTC)
    instrument = "AAPL.SIM"
    result = BacktestResult(
        orders=1,
        fills=1,
        trades=[],
        equity_curve=[],
        decision_trace=(
            DecisionTrace(
                ts=first_close,
                instrument_id=instrument,
                signal=1,
                target_quantity=10.0,
                reason="first decision",
            ),
            DecisionTrace(
                ts=second_close,
                instrument_id=instrument,
                signal=0,
                target_quantity=10.0,
                reason="second decision",
            ),
        ),
        indicator_trace=(
            IndicatorTrace(
                ts=first_close,
                instrument_id=instrument,
                name="close",
                value=100.0,
                unit="price",
            ),
            IndicatorTrace(
                ts=second_close,
                instrument_id=instrument,
                name="close",
                value=101.0,
                unit="price",
            ),
        ),
        chart_annotations=(
            ChartAnnotationTrace(
                decision_ts=second_close,
                instrument_id=instrument,
                kind="line",
                label="second channel",
                unit="price",
                reason="second decision evidence",
                anchors=(
                    ChartAnchor(ts=first_close, value=99.0),
                    ChartAnchor(ts=second_close, value=101.0),
                ),
            ),
        ),
        order_trace=(
            OrderTrace(
                sequence_id=1,
                ts=next_open,
                instrument_id=instrument,
                side="BUY",
                quantity=10.0,
                filled_quantity=10.0,
                status="FILLED",
            ),
        ),
        fill_trace=(
            FillTrace(
                sequence_id=1,
                order_sequence_id=1,
                ts=next_open,
                instrument_id=instrument,
                side="BUY",
                quantity=10.0,
                price=100.5,
            ),
        ),
    )
    rdir = tmp_path / "runs" / "0123456789abcdef"
    _artifacts.write_execution_trace(rdir, result)
    _artifacts.write_manifest(
        rdir,
        {"run_id": rdir.name, "command": "test_fixture", **_identity()},
    )

    decisions = pl.read_parquet(rdir / "decision_trace.parquet")
    consolidated = pl.read_parquet(rdir / "execution_trace.parquet")
    indicators = pl.read_parquet(rdir / "indicator_series.parquet")
    annotations = pl.read_parquet(rdir / "chart_annotations.parquet")
    orders = pl.read_parquet(rdir / "orders.parquet")

    assert decisions["sequence_id"].to_list() == [1, 4]
    assert consolidated.filter(pl.col("event_type") == "decision")["sequence_id"].to_list() == [
        1,
        4,
    ]
    assert orders["decision_sequence_id"].to_list() == [1]
    assert indicators["decision_sequence_id"].to_list() == [1, 4]
    assert annotations["decision_sequence_id"].unique().to_list() == [4]

    projection = chart_bundle(rdir.name, data_dir=tmp_path)
    selected_decision = next(row for row in projection["decisions"] if row["sequence_id"] == 4)
    assert selected_decision["decision_reason"] == "second decision"
    assert [
        row["value"]
        for row in projection["indicators"]
        if row["decision_sequence_id"] == selected_decision["sequence_id"]
    ] == [101.0]
    assert [
        row["label"]
        for row in projection["annotations"]
        if row["decision_sequence_id"] == selected_decision["sequence_id"]
    ] == ["second channel"]


def test_trace_rejects_ambiguous_or_orphaned_decision_evidence(tmp_path: Path) -> None:
    ts = datetime(2026, 1, 5, 23, tzinfo=UTC)
    decision = DecisionTrace(
        ts=ts,
        instrument_id="AAPL.SIM",
        signal=1,
        target_quantity=10.0,
        reason="decision",
    )
    with pytest.raises(DataError, match="duplicate decision timestamp/instrument"):
        _artifacts.write_execution_trace(
            tmp_path / "duplicate",
            BacktestResult(
                orders=0,
                fills=0,
                trades=[],
                equity_curve=[],
                decision_trace=(decision, decision),
            ),
        )

    with pytest.raises(DataError, match="evidence has no matching decision"):
        _artifacts.write_execution_trace(
            tmp_path / "orphaned",
            BacktestResult(
                orders=0,
                fills=0,
                trades=[],
                equity_curve=[],
                indicator_trace=(
                    IndicatorTrace(
                        ts=ts,
                        instrument_id="AAPL.SIM",
                        name="close",
                        value=100.0,
                        unit="price",
                    ),
                ),
            ),
        )
