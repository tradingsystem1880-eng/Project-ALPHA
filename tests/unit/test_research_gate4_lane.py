"""The Gate-4 Tiingo-daily fallback lane (spec §9, ADR-0025; data authority ADR-0023).

Registered daily datasets load into research bars only after fail-closed origin
verification and ADR-0020 session/equal-duration acceptance; the D1 executor then runs
the frozen plan on real-data-shaped daily bars end to end.
"""

from __future__ import annotations

import hashlib
import json
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
