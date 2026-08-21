"""S5a2 real-run future-poison guard for the verified semantic read."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from alpha_cli.artifact_contract import artifact_metadata
from alpha_cli.control_store import ControlStore
from alpha_core import DataError
from alpha_research._canonical import canonical_sha256
from alpha_study import BlindSemanticProjectionV1, project_blind_semantic_read
from tests.integration.test_research_cli import _invoke

pytestmark = pytest.mark.bias_guard


def _real_pilot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, run_pilot: bool = True
) -> tuple[ControlStore, str]:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke(
        "capture", "I notice the S&P500 bounces after double bottoms on the 4h time frame"
    )
    project_id = str(cast(dict[str, object], captured["project"])["project_id"])
    source = _invoke(
        "sources",
        "add",
        project_id,
        "--title",
        "Synthetic detector validation",
        "--locator",
        "owner:synthetic-detector",
        "--provider",
        "owner",
        "--access-mode",
        "owner_provided",
    )
    pack = _invoke("sources", "freeze", project_id, "--source-id", str(source["source_id"]))
    drafted = _invoke(
        "draft",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        "--answer",
        "chart_construction=spy_rth_60m_four_hour_window",
        "--answer",
        "event_availability=second_trough_confirmable",
        "--answer",
        "primary_outcome=four_trading_hour_return_25bp",
    )
    contract = cast(dict[str, object], drafted["contract"])
    _invoke(
        "approve",
        "exploration",
        project_id,
        str(contract["contract_id"]),
        "--actor",
        "owner",
        "--reason",
        "Approve the registered synthetic D0 fixture.",
    )
    if run_pilot:
        _invoke("run", "pilot", project_id)
    return ControlStore(tmp_path), project_id


def _read_projection(store: ControlStore, project_id: str) -> BlindSemanticProjectionV1:
    artifacts = store.verified_blind_semantic_artifacts(project_id)
    return project_blind_semantic_read(
        acceptance_bytes=cast(bytes, artifacts["acceptance_bytes"]),
        events_bytes=cast(bytes, artifacts["events_bytes"]),
        chart_data_bytes=cast(bytes, artifacts["chart_data_bytes"]),
    )


def _leaky_projection(chart_data_bytes: bytes) -> list[dict[str, object]]:
    """Deliberate twin: emits every chart point without applying the acceptance cutoff."""

    chart = json.loads(chart_data_bytes)
    return [
        {
            "available_at": point["ts"],
            "point_id": f"{series['series_id']}:{index}",
            "value": point["value"],
        }
        for series in chart["series"]
        for index, point in enumerate(series["points"])
    ]


def test_post_cutoff_append_preserves_all_emitted_past_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, project_id = _real_pilot(tmp_path, monkeypatch)
    clean = _read_projection(store, project_id)
    run_dir = tmp_path / "runs" / clean.run_id
    chart_path = run_dir / "chart-data.json"
    chart = json.loads(chart_path.read_text(encoding="utf-8"))
    points = chart["series"][0]["points"]
    last_ts = points[-1]["ts"]
    future_ts = datetime.fromisoformat(last_ts.replace("Z", "+00:00")) + timedelta(hours=1)
    points.append({"ts": future_ts.isoformat().replace("+00:00", "Z"), "value": 999999.0})
    chart["artifact_sha256"] = canonical_sha256(chart["series"][0])
    chart_path.write_text(
        json.dumps(chart, sort_keys=True, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["chart-data.json"] = artifact_metadata(chart_path)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    poisoned = _read_projection(store, project_id)
    assert poisoned.cutoff_confirmed_at == clean.cutoff_confirmed_at
    assert poisoned.visible_points == clean.visible_points
    assert poisoned.chart_data_artifact_sha256 != clean.chart_data_artifact_sha256
    assert poisoned.masked_count == clean.masked_count + 1
    assert all(
        point.available_at <= poisoned.cutoff_confirmed_at for point in poisoned.visible_points
    )
    assert "999999" not in json.dumps(poisoned.to_dict(), sort_keys=True)


def test_must_fail_leaky_twin_exposes_appended_real_chart_poison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, project_id = _real_pilot(tmp_path, monkeypatch)
    artifacts = store.verified_blind_semantic_artifacts(project_id)
    clean_chart_bytes = cast(bytes, artifacts["chart_data_bytes"])
    clean_points = _leaky_projection(clean_chart_bytes)
    chart = json.loads(clean_chart_bytes)
    points = chart["series"][0]["points"]
    last_ts = points[-1]["ts"]
    future_ts = datetime.fromisoformat(last_ts.replace("Z", "+00:00")) + timedelta(hours=1)
    points.append({"ts": future_ts.isoformat().replace("+00:00", "Z"), "value": 999999.0})
    chart["artifact_sha256"] = canonical_sha256(chart["series"][0])
    appended_chart_bytes = json.dumps(
        chart, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    leaky = _leaky_projection(appended_chart_bytes)
    assert len(leaky) == len(clean_points) + 1
    assert leaky[-1]["value"] == 999999.0
    with pytest.raises(AssertionError):
        assert leaky == clean_points


def test_manifest_consistent_race_is_denied_after_initial_verifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, project_id = _real_pilot(tmp_path, monkeypatch)
    clean = _read_projection(store, project_id)
    run_dir = tmp_path / "runs" / clean.run_id
    original = ControlStore._require_completed_d0_attempt
    original_verified_run = ControlStore._verified_run
    verified_run_calls = 0
    injected = False

    def count_verified_run(self: ControlStore, run_id: str) -> tuple[Path, dict[str, object]]:
        nonlocal verified_run_calls
        verified_run_calls += 1
        return original_verified_run(self, run_id)

    def rewrite_after_completed(
        self: ControlStore, connection: sqlite3.Connection, **kwargs: object
    ) -> sqlite3.Row:
        nonlocal injected
        row = original(self, connection, **kwargs)  # type: ignore[arg-type]
        if not injected:
            injected = True
            acceptance_path = run_dir / "d0_acceptance.json"
            acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
            acceptance["measurements"]["monotonic_event_count"] = 1
            acceptance_path.write_text(
                json.dumps(acceptance, sort_keys=True, separators=(",", ":"), allow_nan=False),
                encoding="utf-8",
            )
            events_path = run_dir / "events.json"
            events_path.write_bytes(events_path.read_bytes() + b" ")
            chart_path = run_dir / "chart-data.json"
            chart = json.loads(chart_path.read_text(encoding="utf-8"))
            chart["series"][0]["points"][-1]["value"] = 999999.0
            chart["artifact_sha256"] = canonical_sha256(chart["series"][0])
            chart_path.write_text(
                json.dumps(chart, sort_keys=True, separators=(",", ":"), allow_nan=False),
                encoding="utf-8",
            )
            manifest_path = run_dir / "manifest.json"
            current = json.loads(manifest_path.read_text(encoding="utf-8"))
            for filename in ("d0_acceptance.json", "events.json", "chart-data.json"):
                current["artifacts"][filename] = artifact_metadata(run_dir / filename)
            manifest_path.write_text(json.dumps(current, sort_keys=True), encoding="utf-8")
        return row

    monkeypatch.setattr(
        ControlStore,
        "_require_completed_d0_attempt",
        rewrite_after_completed,
    )
    monkeypatch.setattr(ControlStore, "_verified_run", count_verified_run)
    with pytest.raises(DataError, match="measurements fail exact deterministic recomputation"):
        store.verified_blind_semantic_artifacts(project_id)
    assert verified_run_calls >= 3


def test_verified_read_does_not_write_control_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, project_id = _real_pilot(tmp_path, monkeypatch)
    database = tmp_path / "control" / "workstation.sqlite3"
    before = database.read_bytes()
    _read_projection(store, project_id)
    assert database.read_bytes() == before


def test_no_completed_d0_is_denied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, project_id = _real_pilot(tmp_path, monkeypatch, run_pilot=False)
    with pytest.raises(DataError, match="exactly one completed immutable D0"):
        store.verified_blind_semantic_artifacts(project_id)


def test_wrong_active_lineage_is_denied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, project_id = _real_pilot(tmp_path, monkeypatch)
    summary = store.research_case_summary(project_id)
    old_exploration_id = str(summary["exploration_contract_id"])
    active_contract = cast(dict[str, object], summary["active_contract"])
    payload = json.loads(json.dumps(active_contract["payload"]))
    protocol = cast(dict[str, object], payload["protocol"])
    topology = cast(dict[str, object], protocol["evidence_topology"])
    d2_topology = cast(dict[str, object], topology["D2"])
    d2_topology["relation_to_prior"] = "unopened_sealed_reuse"
    store.close_early_research_case(
        project_id,
        outcome="INCONCLUSIVE",
        disposition="revise",
        actor="owner",
        reason="Create a distinct active exploration lineage for resolver testing.",
    )
    revision = store.create_research_contract(
        project_id,
        scope="exploration",
        parent_contract_id=old_exploration_id,
        payload=payload,
        created_by="codex",
        author_kind="agent",
    )
    revision_id = str(revision["contract_id"])
    store.reopen_research_revision(
        project_id,
        revision_id,
        actor="owner",
        reason="Select the newer valid exploration lineage.",
        next_action="Owner approves the newer exploration contract.",
    )
    store.review_research_contract(
        project_id,
        revision_id,
        scope="exploration",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="Approve the newer valid exploration contract.",
    )
    store.transition_research_phase(
        project_id,
        to_phase="pilot",
        contract_id=revision_id,
        actor="codex",
        reason="Move the newer lineage to pilot without a completed D0.",
        next_action="Run the newer D0 pilot.",
        responsibility="codex",
    )
    with pytest.raises(DataError, match="exactly one completed immutable D0"):
        store.verified_blind_semantic_artifacts(project_id)


def test_oversized_selected_file_is_denied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, project_id = _real_pilot(tmp_path, monkeypatch)
    projection = _read_projection(store, project_id)
    run_dir = tmp_path / "runs" / projection.run_id
    events_path = run_dir / "events.json"
    events_path.write_bytes(events_path.read_bytes() + b" " * (8 * 1024 * 1024))
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["events.json"] = artifact_metadata(events_path)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    with pytest.raises(DataError, match="exceeds the bounded"):
        store.verified_blind_semantic_artifacts(project_id)


def test_artifact_tamper_without_manifest_update_is_denied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, project_id = _real_pilot(tmp_path, monkeypatch)
    projection = _read_projection(store, project_id)
    events_path = tmp_path / "runs" / projection.run_id / "events.json"
    events_path.write_bytes(events_path.read_bytes() + b"\n")
    with pytest.raises(DataError, match="size mismatch|hash mismatch"):
        store.verified_blind_semantic_artifacts(project_id)
