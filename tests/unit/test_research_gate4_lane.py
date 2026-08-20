"""The Gate-4 Tiingo-daily fallback lane (spec §9, ADR-0025; data authority ADR-0023).

Registered daily datasets load into research bars only after fail-closed origin
verification and ADR-0020 session/equal-duration acceptance; the D1 executor then runs
the frozen plan on real-data-shaped daily bars end to end.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from alpha_cli.control_store import ControlStore
from alpha_cli.research_d1 import (
    load_registered_research_bars,
    run_deep_research,
)
from alpha_core import DataError
from alpha_data.snapshot import create_snapshot
from alpha_data.store import ParquetStore

PROJECT_ID = "9e4908b1-a9cd-4c13-a47e-740d92175680"
CONTRACT_ID = "rc_" + "a" * 64
_MOTIF = (105.0, 103.0, 100.0, 95.0, 99.0, 101.0, 100.0, 95.5, 99.0, 101.0)


def _daily_lows(blocks: int = 20) -> list[float]:
    """Planted daily motifs: 10-day pattern, 4-day rise, 16 flat days per block."""
    lows: list[float] = []
    for _block in range(blocks):
        lows.extend(_MOTIF)
        level = _MOTIF[-1]
        for day in range(14):
            level = level + 1.5 if day < 4 else level
            lows.append(level)
        lows.extend([100.0] * 6)
    return lows


def _daily_frame(lows: list[float]) -> pl.DataFrame:
    start = datetime(2020, 1, 6, tzinfo=UTC)
    rows = [
        {
            "ts": start + timedelta(days=index),
            "open": low + 1.0,
            "high": low + 6.0,
            "low": low,
            "close": low + 2.0,
            "volume": 1_000.0 + index,
        }
        for index, low in enumerate(lows)
    ]
    return pl.DataFrame(rows)


def _registered_daily_ref(tmp_path: Path, lows: list[float]) -> dict[str, object]:
    store = ParquetStore(tmp_path / "store")
    store.write_bars("SPY", _daily_frame(lows))
    create_snapshot(
        store,
        tmp_path / "snapshots",
        "gate4",
        ["SPY"],
        source="tiingo",
        adapter_version="1",
        parser_version="1",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    manifest_sha = hashlib.sha256(
        (tmp_path / "snapshots" / "gate4" / "manifest.json").read_bytes()
    ).hexdigest()
    control = ControlStore(tmp_path)
    end_day = datetime(2020, 1, 6, tzinfo=UTC) + timedelta(days=len(lows) - 1)
    return control.register_research_dataset(
        dataset_kind="snapshot",
        instrument="SPY",
        provider="tiingo",
        start_ts="2020-01-06",
        end_ts=end_day.date().isoformat(),
        bar_duration_minutes=1_440,
        origin={"snapshot_id": "gate4", "manifest_sha256": manifest_sha},
        registered_by="owner",
    )


def test_registered_daily_dataset_loads_with_session_acceptance(tmp_path: Path) -> None:
    lows = _daily_lows()
    ref = _registered_daily_ref(tmp_path, lows)
    bars = load_registered_research_bars(tmp_path, ref=ref)
    assert len(bars.bars) == len(lows)
    assert bars.duration.total_seconds() == 1_440 * 60  # equal session-daily duration
    assert bars.dataset.session == "regular_session_daily"
    assert bars.dataset.scope == "research_only"
    first = bars.bars[0]
    assert first.start.weekday() == 0  # the session day owns the bar
    assert first.available_at == first.end


def test_daily_loader_fails_closed_on_drifted_or_unqualified_origins(tmp_path: Path) -> None:
    lows = _daily_lows(blocks=3)
    ref = _registered_daily_ref(tmp_path, lows)
    manifest_path = tmp_path / "snapshots" / "gate4" / "manifest.json"
    manifest_path.write_text(manifest_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(DataError, match="manifest hash"):
        load_registered_research_bars(tmp_path, ref=ref)

    with pytest.raises(DataError, match="Tiingo-daily fallback"):
        load_registered_research_bars(tmp_path, ref={**ref, "bar_duration_minutes": 60})
    with pytest.raises(DataError, match="retention and.*licensing|licensing"):
        load_registered_research_bars(tmp_path, ref={**ref, "dataset_kind": "quantpad_receipt"})


def test_daily_loader_fails_closed_on_tampered_snapshot_payload_bytes(tmp_path: Path) -> None:
    """Corrupted payload bytes behind an intact manifest are a typed integrity failure.

    The registered manifest hash covers manifest.json only; every payload file must be
    re-hashed at load time so drift surfaces as DataError, never a raw parquet crash.
    """
    ref = _registered_daily_ref(tmp_path, _daily_lows(blocks=3))
    parquets = sorted((tmp_path / "snapshots" / "gate4").rglob("*.parquet"))
    assert parquets
    parquets[0].write_bytes(parquets[0].read_bytes() + b"tampered")
    with pytest.raises(DataError, match="snapshot integrity failure"):
        load_registered_research_bars(tmp_path, ref=ref)


def test_daily_loader_rejects_disordered_registered_bars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lows = _daily_lows(blocks=3)
    ref = _registered_daily_ref(tmp_path, lows)
    frame = _daily_frame(lows[:5])
    duplicated = pl.concat([frame, frame.tail(1)])

    import alpha_cli.research_data_audit as audit_module

    monkeypatch.setattr(audit_module, "load_registered_dataset_frame", lambda *a, **k: duplicated)
    with pytest.raises(DataError, match="strictly ordered"):
        load_registered_research_bars(tmp_path, ref=ref)


def test_d1_executor_runs_end_to_end_on_the_daily_fallback_lane(tmp_path: Path) -> None:
    from tests.unit.test_research_d1_executor import _contract

    lows = _daily_lows()
    ref = _registered_daily_ref(tmp_path, lows)
    bars = load_registered_research_bars(tmp_path, ref=ref)
    contract: dict[str, Any] = _contract(horizon_bars=1)
    manifest = run_deep_research(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        bars=bars,
    )
    assert manifest["command"] == "research_deep"
    assert manifest["evidence_zone"] == "D1"
    assert manifest["dataset_hash"] == bars.dataset.content_sha256
    evidence = json.loads(
        (tmp_path / "runs" / str(manifest["run_id"]) / "research_gate_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    primary = evidence["primary_result"]
    assert primary["status"] == "TESTED"
    assert int(primary["sample_size"]) >= 10  # ~12 planted events reach the discovery share


def _empirical_contract(ref: Mapping[str, object], bars: Any) -> dict[str, Any]:
    """The real R6a approval payload: an empirical daily exploration contract."""
    from alpha_cli.research_cmds import _approval_payload, _EmpiricalDataset
    from alpha_cli.research_intake import draft_exploration_contract

    preview = draft_exploration_contract(
        "SPY bounces after double bottoms on the daily chart",
        resolutions={
            "chart_construction": "tiingo_daily_fallback",
            "event_availability": "second_trough_confirmable",
            "primary_outcome": "next_regular_session_return_50bp",
        },
    )
    return _approval_payload(
        preview,
        source_pack_id="sp_" + "b" * 64,
        empirical_dataset=_EmpiricalDataset(ref=dict(ref), bars=bars),
    )


def _sealed_boundary(contract: Mapping[str, object]) -> Any:
    from alpha_research import research_d2_boundary_from_dict

    protocol = contract["protocol"]
    assert isinstance(protocol, dict)
    topology = protocol["evidence_topology"]
    assert isinstance(topology, dict)
    boundary_value = topology["boundary"]
    assert isinstance(boundary_value, dict)
    return research_d2_boundary_from_dict(boundary_value)


def test_deep_run_verifies_the_sealed_empirical_boundary_end_to_end(tmp_path: Path) -> None:
    """R6b (ADR-0026): the empirical lane runs against its own sealed group boundary."""
    lows = _daily_lows()
    ref = _registered_daily_ref(tmp_path, lows)
    bars = load_registered_research_bars(tmp_path, ref=ref)
    contract = _empirical_contract(ref, bars)
    boundary = _sealed_boundary(contract)
    manifest = run_deep_research(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        bars=bars,
        boundary=boundary,
    )
    assert manifest["real_market_evidence"] is True
    assert manifest["watermark"] == "EXPLORATORY"
    assert manifest["eligible_for_holdout_or_execution"] is False
    hashes = contract["hashes"]
    assert isinstance(hashes, dict)
    assert manifest["dataset_hash"] == bars.dataset.content_sha256 == hashes["data"]
    evidence = json.loads(
        (tmp_path / "runs" / str(manifest["run_id"]) / "research_gate_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    assert evidence["primary_result"]["status"] == "TESTED"


def test_deep_run_rejects_misaligned_or_foreign_boundaries(tmp_path: Path) -> None:
    from alpha_research import ResearchD2BoundaryV1, ResearchEvidenceSharesV1

    lows = _daily_lows()
    ref = _registered_daily_ref(tmp_path, lows)
    bars = load_registered_research_bars(tmp_path, ref=ref)
    contract = _empirical_contract(ref, bars)
    real = _sealed_boundary(contract)
    groups = [bar.start.date().isoformat() for bar in bars.bars]

    def _variant(**overrides: Any) -> Any:
        arguments: dict[str, Any] = {
            "dataset_fingerprint": real.dataset_fingerprint,
            "eligible_groups": groups,
            "chart_fingerprint": real.chart_fingerprint,
            "event_formula": real.event_formula,
            "event_availability_timestamp": real.event_availability_timestamp,
            "primary_endpoint": real.primary_endpoint,
            "primary_horizon": real.primary_horizon,
            "outcome_overlap_embargo_groups": real.outcome_overlap_embargo_groups,
        }
        arguments.update(overrides)
        return ResearchD2BoundaryV1.from_eligible_groups(**arguments)

    for boundary, message in (
        (_variant(dataset_fingerprint="f" * 64), "dataset fingerprint"),
        (_variant(eligible_groups=list(reversed(groups))), "eligible groups"),
        (
            _variant(
                shares=ResearchEvidenceSharesV1(
                    d0_percent=0, d1_percent=61, d2_percent=19, d3_percent=20
                )
            ),
            "does not align",
        ),
    ):
        with pytest.raises(DataError, match=message):
            run_deep_research(
                tmp_path,
                project_id=PROJECT_ID,
                contract_id=CONTRACT_ID,
                contract=contract,
                bars=bars,
                boundary=boundary,
            )


@pytest.mark.bias_guard
def test_daily_deep_run_never_reads_confirmation_or_holdout_sessions(tmp_path: Path) -> None:
    """Rewriting D2/D3 session-daily bars must not change any empirical D1 measurement."""
    lows = _daily_lows()
    clean_dir = tmp_path / "clean"
    clean_dir.mkdir()
    ref = _registered_daily_ref(clean_dir, lows)
    bars = load_registered_research_bars(clean_dir, ref=ref)
    contract = _empirical_contract(ref, bars)
    manifest = run_deep_research(
        clean_dir,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        bars=bars,
        boundary=_sealed_boundary(contract),
    )
    clean_analyses = (
        clean_dir / "runs" / str(manifest["run_id"]) / "d1_analyses.json"
    ).read_bytes()
    stop = json.loads(clean_analyses)["measurements"]["topology"]["discovery_stop"]

    poisoned_dir = tmp_path / "poisoned"
    poisoned_dir.mkdir()
    poisoned_lows = [*lows[:stop], *([5_000.0] * (len(lows) - stop))]
    poisoned_ref = _registered_daily_ref(poisoned_dir, poisoned_lows)
    poisoned_bars = load_registered_research_bars(poisoned_dir, ref=poisoned_ref)
    poisoned_contract = _empirical_contract(poisoned_ref, poisoned_bars)
    poisoned_manifest = run_deep_research(
        poisoned_dir,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=poisoned_contract,
        bars=poisoned_bars,
        boundary=_sealed_boundary(poisoned_contract),
    )
    poisoned_analyses = (
        poisoned_dir / "runs" / str(poisoned_manifest["run_id"]) / "d1_analyses.json"
    ).read_bytes()
    assert poisoned_analyses == clean_analyses
