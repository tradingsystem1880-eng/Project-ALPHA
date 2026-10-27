"""Explicit synthetic owner confirmation for one closed rule capability."""

from __future__ import annotations

import hashlib
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

from alpha_cli._native_rule_protocol import fixed_study, rule_plan, validate_rule_plan
from alpha_cli.control_store import ControlStore, ResearchPhase
from alpha_core import DataError
from tests.unit.test_research_control_store import PROJECT_ID

if TYPE_CHECKING:
    from alpha_cli._native_loop_admission import NativeLaunch


@pytest.fixture
def configured_rule_source() -> Path:
    from alpha_cli._native_loop_admission import WORKER

    configured = os.environ.get("ALPHA_RDAGENT_SOURCE")
    if configured is None:
        pytest.skip("explicit ALPHA_RDAGENT_SOURCE and qualified rule profiles required")
    source = Path(configured).resolve()
    assert (source / "rdagent").is_dir(), "configured native source is missing/broken"
    for name in (".venv-rule-qualified", ".venv-economics-qualified"):
        runtime = WORKER / name
        assert (runtime / "bin/python").is_file(), f"configured worker {name} is missing"
        assert (runtime / "rule-profile.json").is_file(), f"configured profile {name} is missing"
    return source


def test_rule_protocol_is_exact_and_has_no_statistical_claim() -> None:
    study = fixed_study()
    plan = rule_plan()
    assert plan["study"] == study.to_dict()
    assert validate_rule_plan(plan, max_grid_cells=1) == plan
    assert study.data.dataset.provider == "synthetic"
    for key in ("schema", "study", "trial_limit", "control"):
        changed = deepcopy(plan)
        changed[key] = "changed"
        with pytest.raises(DataError):
            validate_rule_plan(changed, max_grid_cells=1)
    with pytest.raises(DataError):
        validate_rule_plan({**plan, "extra": True}, max_grid_cells=1)


def test_actual_rule_positions_match_hand_reference() -> None:
    from alpha_cli._native_rule_protocol import position_payload

    assert position_payload()["baseline"] == [1, 0, 1]
    assert position_payload()["control"] == [0, 0, 0]


def _draft(
    store: ControlStore,
    fingerprints: dict[str, str | None] | None = None,
    *,
    costed: bool = False,
    project_id: str = PROJECT_ID,
) -> tuple[str, dict[str, object]]:
    from datetime import timedelta

    from alpha_cli._native_rule_protocol import draft_rule_contract
    from tests.unit.test_research_control_store import START

    store.create_project(
        name="Synthetic frozen rule fixture",
        hypothesis="Fixed engineering mechanics only",
        falsification_criterion="Reject mismatched canonical mechanics",
        project_id=project_id,
        at=START,
    )
    source = store.create_research_source(
        project_id,
        title="Independent synthetic arithmetic",
        locator="synthetic:fixed-rule-reference-v1",
        provider="synthetic",
        access_mode="metadata_only",
        metadata={"synthetic": True},
        at=START + timedelta(minutes=1),
    )
    pack = store.create_research_source_pack(
        project_id,
        source_ids=[str(source["source_id"])],
        definition={"synthetic": True, "reference": "hand-specified positions and economics"},
        at=START + timedelta(minutes=2),
    )
    payload = draft_rule_contract(
        str(pack["pack_id"]),
        fingerprints
        or {
            **{
                key: hashlib.sha256(key.encode()).hexdigest()
                for key in ("code", "environment", "evaluator", "dependency_lock")
            },
            "data": fixed_study().data.dataset.content_sha256,
        },
        {
            "wall_seconds": 300,
            "source_requests": 1,
            "variants": 5,
            "rdagent_native_v1_model_calls": 0,
            "rdagent_native_v1_input_tokens": 0,
            "rdagent_native_v1_output_tokens": 0,
            "rdagent_native_v1_loop_steps": 5,
            "rdagent_native_v1_tool_calls": 0,
            "rdagent_native_v1_cpu_milliseconds": 10000,
        },
        costed=costed,
    )
    contract = store.create_research_contract(
        project_id,
        scope="exploration",
        payload=payload,
        created_by="synthetic-test-agent",
        author_kind="agent",
        at=START + timedelta(minutes=3),
    )
    cid = str(contract["contract_id"])
    for minute, phase in ((4, "triage"), (5, "exploration_review")):
        store.transition_research_phase(
            project_id,
            to_phase=cast(ResearchPhase, phase),
            contract_id=cid,
            actor="synthetic-test-agent",
            reason="Synthetic engineering fixture",
            next_action="Explicit synthetic owner confirmation",
            responsibility="owner",
            at=START + timedelta(minutes=minute),
        )
    return cid, payload


def _approve(
    tmp_path: Path,
    fingerprints: dict[str, str | None] | None = None,
    *,
    costed: bool = False,
    project_id: str = PROJECT_ID,
) -> None:
    from datetime import timedelta

    from alpha_cli import owner_auth
    from alpha_cli.control_store import ControlStore, research_case_revision
    from tests.unit.test_research_control_store import START

    store = ControlStore(tmp_path)
    cid, payload = _draft(store, fingerprints, costed=costed, project_id=project_id)
    kwargs: dict[str, Any] = dict(
        scope="exploration",
        decision="approve",
        actor="owner:local-confirmation",
        actor_kind="human",
        reason="Explicit synthetic engineering approval",
        at=START + timedelta(minutes=6),
    )
    with pytest.raises(DataError, match="consumed owner confirmation"):
        store.review_research_contract(project_id, cid, **kwargs)
    request = {"contract_id": cid}
    binding = owner_auth.action_binding(
        data_dir=tmp_path,
        action_type="approve_exploration",
        project_id=project_id,
        artifact_hash=cid.removeprefix("rc_"),
        expected_case_revision=research_case_revision(store.research_case_summary(project_id)),
        consequence_summary="Approve synthetic rule mechanics only",
        reason="Synthetic test owner decision",
        payload=request,
    )
    envelope = owner_auth.local_confirmation_options(
        data_dir=tmp_path, binding=binding, now=START + timedelta(minutes=6)
    )
    confirm: dict[str, Any] = dict(
        data_dir=tmp_path,
        challenge_id=envelope["challenge_id"],
        confirmation_token=envelope["confirmation_token"],
        payload=request,
        now=START + timedelta(minutes=6),
    )
    result = owner_auth.verify_local_confirmation(**confirm)
    assert result["actor"] == "owner:local-confirmation"
    store.review_research_contract(project_id, cid, **kwargs)
    with pytest.raises(DataError, match="already used"):
        owner_auth.verify_local_confirmation(**confirm)


def _pilot(
    tmp_path: Path,
    fingerprints: dict[str, str | None] | None = None,
    *,
    costed: bool = False,
    project_id: str = PROJECT_ID,
) -> None:
    from datetime import timedelta

    from alpha_cli._native_rule_artifacts import d0_fingerprint, publish_rule_run
    from alpha_cli.control_store import ControlStore
    from tests.unit.test_research_control_store import START, _d0_acceptance_ref

    _approve(tmp_path, fingerprints, costed=costed, project_id=project_id)
    store = ControlStore(tmp_path)
    cid = str(store.research_case_summary(project_id)["active_contract_id"])
    payload = cast(dict[str, object], store.get_research_contract(cid)["payload"])
    store.transition_research_phase(
        project_id,
        to_phase="pilot",
        contract_id=cid,
        actor="owner:local-confirmation",
        reason="Approved synthetic fixture",
        next_action="Run D0",
        responsibility="codex",
        at=START + timedelta(minutes=7),
    )
    store.transition_research_execution(
        project_id,
        to_state="queued",
        contract_id=cid,
        actor="synthetic-test-agent",
        reason="Queue D0",
        next_action="Run D0",
        responsibility="codex",
        at=START + timedelta(minutes=8),
    )
    fingerprint = d0_fingerprint(payload)
    reservation = store.reserve_d0_research_launch(
        project_id, cid, config_fingerprint=fingerprint, at=START + timedelta(minutes=9)
    )
    manifest = publish_rule_run(
        tmp_path,
        project_id=project_id,
        contract_id=cid,
        contract=payload,
        execution_fingerprint=fingerprint,
    )
    assert set(manifest["artifacts"]) == {"baseline.json", "control.json", "d0_acceptance.json"}
    store.record_research_attempt(
        project_id,
        cid,
        kind="d0-synthetic-pilot",
        status="completed",
        config_fingerprint=fingerprint,
        budget_used={},
        run_id=manifest["run_id"],
        details={
            "attempt_number": 1,
            "evidence_zone": "D0",
            "d0_acceptance_ref": _d0_acceptance_ref(tmp_path, manifest["run_id"]),
        },
        launch_reservation_id=str(reservation["reservation_id"]),
        at=START + timedelta(minutes=10),
    )
    store.transition_research_execution(
        project_id,
        to_state="idle",
        contract_id=cid,
        actor="synthetic-test-agent",
        reason="D0 finished",
        next_action="Reserve native trial",
        responsibility="codex",
        at=START + timedelta(minutes=10, seconds=1),
    )
    store.transition_research_phase(
        project_id,
        to_phase="deep_research",
        contract_id=cid,
        actor="synthetic-test-agent",
        reason="Verified D0 mechanics",
        next_action="Reserve one synthetic native trial",
        responsibility="codex",
        at=START + timedelta(minutes=11),
    )


def test_rule_approval_requires_real_consumed_confirmation(tmp_path: Path) -> None:
    _approve(tmp_path)


def test_rule_d0_uses_immutable_position_artifacts(tmp_path: Path) -> None:
    _pilot(tmp_path)


def _assert_costed_projection(
    rdir: Path, chart: dict[str, Any], raw: dict[str, Any], *, control: bool
) -> None:
    import json
    from datetime import datetime

    import polars as pl

    from alpha_cli._native_rule_economics import fixed_costed_study
    from alpha_cli.run_store import research_gate_watermark, run_context_projection

    assert chart["bars_status"] == "available"
    assert chart["trace_status"] == "available"
    assert not any(chart["truncated"].values())
    bars = cast(list[list[Any]], fixed_costed_study().to_dict()["bars"])
    assert chart["bars"] == [
        {
            "t": datetime.fromisoformat(row[0]).timestamp(),
            **{field: row[index] for index, field in enumerate(("o", "h", "l", "c", "v"), 1)},
        }
        for row in bars
    ]
    timestamps = [datetime.fromisoformat(row[0]).timestamp() for row in raw["equity_curve"]]
    values = [row[1] for row in raw["equity_curve"]]
    assert chart["equity"]["ts"] == timestamps
    assert chart["equity"]["equity"] == values
    assert chart["equity"]["drawdown"] == pytest.approx(
        [value / max(values[: index + 1]) - 1.0 for index, value in enumerate(values)]
    )
    assert chart["trades"] == [
        {
            **trade,
            "entry_ts": datetime.fromisoformat(trade["entry_ts"]).timestamp(),
            "exit_ts": datetime.fromisoformat(trade["exit_ts"]).timestamp(),
        }
        for trade in raw["trades"]
    ]
    # Consolidated event sequence/parent IDs, fill quantities/prices and trade times
    # come unchanged from the canonical artifact, rather than inferred UI events.
    trace = pl.read_parquet(rdir / "execution_trace.parquet").sort("sequence_id")
    assert chart["trace"] == [
        {
            key: value.timestamp() if isinstance(value, datetime) else value
            for key, value in row.items()
        }
        for row in trace.iter_rows(named=True)
    ]
    assert len(chart["fills"]) == (0 if control else 4)
    assert len(chart["trades"]) == (0 if control else 2)
    benchmark = pl.read_parquet(rdir / "benchmark_comparison.parquet")
    assert benchmark.height == len(timestamps)
    assert benchmark["available"].to_list() == [True] * len(timestamps)
    assert benchmark["benchmark_kind"].unique().to_list() == ["passive_open_to_open_price_only"]
    assert [value.timestamp() for value in benchmark["ts"]] == timestamps
    benchmark_values = [row[1] for row in raw["benchmark_curve"]]
    assert benchmark["benchmark_equity"].to_list() == pytest.approx(
        [value / benchmark_values[0] for value in benchmark_values]
    )
    exposure = pl.read_parquet(rdir / "exposure_turnover.parquet")
    assert exposure.height == len(timestamps) - 1
    states = {datetime.fromisoformat(row["ts"]): row for row in raw["portfolio_state_trace"]}
    for row in exposure.iter_rows(named=True):
        assert row["exposure_available"] is True and row["turnover_available"] is True
        for field in ("gross_exposure", "net_exposure", "turnover"):
            assert row[field] == states[row["start_ts"]][field]
            if control:
                assert row[field] == 0
    if control:
        assert chart["trades"] == [] and chart["orders"] == [] and chart["fills"] == []
        assert values == [12000.0] * len(timestamps)
        assert chart["equity"]["drawdown"] == [0.0] * len(timestamps)
    # Existing reader lacks a synthetic badge contract; preserve that visible gap.
    manifest = json.loads((rdir / "manifest.json").read_text())
    assert manifest["watermark"] == "SYNTHETIC ENGINEERING ONLY"
    assert research_gate_watermark(manifest) is None
    assert run_context_projection(manifest) == {
        "run_context_kind": "legacy_context_unknown",
        "run_context_project_id": None,
        "run_context_watermark": "LEGACY_CONTEXT_UNKNOWN",
    }


def _assert_projection_manifest_rejections(
    root: Path, selectors: dict[str, Any], receipt: dict[str, Any], source_fingerprint: str
) -> None:
    import json

    from alpha_cli._native_rule_projection import validate_projections

    manifest_path = root / "runs" / selectors["roles"]["baseline"]["run_id"] / "manifest.json"
    original = manifest_path.read_bytes()
    manifest = json.loads(original)
    control_path = root / "runs" / selectors["roles"]["control"]["run_id"] / "manifest.json"
    original_control = control_path.read_bytes()
    accepted = []
    changes: dict[str, object] = {
        "final_equity": 99999999.0,
        "starting_equity": 1.0,
        "n_trades": 999,
        "fills": 999,
        "orders": 999,
        "rejected": 999,
        "synthetic": False,
        "real_market_evidence": True,
        "eligible_for_holdout_or_execution": True,
        "places_orders": True,
        "watermark": "PROVEN MARKET EDGE",
        "execution_fingerprint": "0" * 64,
        "research_cutoff": "2099-01-01T00:00:00+00:00",
        "parent_run_id": "0" * 16,
        "strategy_fingerprint": "0" * 64,
        "params": {"fee_bps": 0},
        "run_identity_version": 3.0,
        "scope": "live",
        "research_gate": {"watermark": "PROVEN MARKET EDGE"},
    }
    try:
        for field, value in changes.items():
            changed = {**manifest, field: value}
            altered_selectors = deepcopy(selectors)
            if field == "parent_run_id":
                # Corrupt both copies: the parent must come from a trusted caller.
                altered_selectors["parent_run_id"] = value
                changed_control = {**json.loads(original_control), field: value}
                control_bytes = json.dumps(changed_control, sort_keys=True).encode()
                control_path.write_bytes(control_bytes)
                altered_selectors["roles"]["control"]["manifest_sha256"] = hashlib.sha256(
                    control_bytes
                ).hexdigest()
            else:
                control_path.write_bytes(original_control)
            raw = json.dumps(changed, sort_keys=True, indent=2).encode()
            manifest_path.write_bytes(raw)
            altered_selectors["roles"]["baseline"]["manifest_sha256"] = hashlib.sha256(
                raw
            ).hexdigest()
            try:
                validate_projections(
                    root,
                    altered_selectors,
                    receipt,
                    parent_run_id=str(selectors["parent_run_id"]),
                    source_fingerprint=source_fingerprint,
                )
            except DataError:
                pass
            else:
                accepted.append(field)
    finally:
        manifest_path.write_bytes(original)
        control_path.write_bytes(original_control)
    assert not accepted, f"self-rehashed semantic projection changes accepted: {accepted}"

    malformed_selectors: list[object] = [None, [], {**selectors, "extra": True}]
    for field, value in (
        ("schema", 1),
        ("parent_run_id", "0" * 16),
        ("trial_id", "other-trial"),
        ("scientific_acceptance", "admitted"),
        ("snapshot_id", False),
        ("roles", []),
        ("roles", {"baseline": selectors["roles"]["baseline"]}),
    ):
        malformed_selectors.append({**selectors, field: value})
    malformed_references: list[object] = [
        None,
        [],
        {},
        {**selectors["roles"]["baseline"], "extra": True},
    ]
    for reference in malformed_references:
        changed_selectors = deepcopy(selectors)
        changed_selectors["roles"]["baseline"] = reference
        malformed_selectors.append(changed_selectors)
    for value in malformed_selectors:
        with pytest.raises(DataError):
            validate_projections(
                root,
                value,
                receipt,
                parent_run_id=str(selectors["parent_run_id"]),
                source_fingerprint=source_fingerprint,
            )
    for field, value in (("n_trades", 2.0), ("synthetic", 1), ("final_equity", float("nan"))):
        changed = {**manifest, field: value}
        raw = json.dumps(changed).encode()
        manifest_path.write_bytes(raw)
        altered_selectors = deepcopy(selectors)
        altered_selectors["roles"]["baseline"]["manifest_sha256"] = hashlib.sha256(raw).hexdigest()
        try:
            with pytest.raises(DataError):
                validate_projections(
                    root,
                    altered_selectors,
                    receipt,
                    parent_run_id=str(selectors["parent_run_id"]),
                    source_fingerprint=source_fingerprint,
                )
        finally:
            manifest_path.write_bytes(original)


def _assert_trusted_observation_boundary(
    root: Path,
    store: ControlStore,
    job: str,
    launch: NativeLaunch,
    receipt: dict[str, Any],
    before: object,
) -> bytes:
    import json

    from alpha_cli._native_loop_admission import MAX_NATIVE_RECEIPT_BYTES
    from alpha_cli._native_rule_completion import complete_rule_trial

    native_path = root / f"payload-{job}" / "receipt.json"
    observed_bytes = native_path.read_bytes()
    assert len(observed_bytes) < MAX_NATIVE_RECEIPT_BYTES
    with store._transaction(write=False) as connection:
        row = connection.execute(
            "SELECT sequence,payload_json FROM job_events "
            "WHERE job_id=? AND event_type='native_outcome'",
            (job,),
        ).fetchone()
    assert row is not None
    original_outcome = json.loads(row["payload_json"])
    assert original_outcome["rule_result"] == {
        "schema": "SyntheticNativeRuleObservationV1",
        "receipt_sha256": hashlib.sha256(observed_bytes).hexdigest(),
    }
    # Historical absence is readable process evidence, never an automatic rule upgrade.
    missing = dict(original_outcome)
    del missing["rule_result"]
    malformed = [missing]
    for value in (
        None,
        {},
        {"schema": "unknown", "receipt_sha256": "0" * 64},
        {"schema": "SyntheticNativeRuleObservationV1", "receipt_sha256": True},
        {**original_outcome["rule_result"], "extra": 1},
        {"schema": "SyntheticNativeRuleObservationV1", "receipt_sha256": "0" * 64},
    ):
        malformed.append({**original_outcome, "rule_result": value})
    for changed in malformed:
        with store._transaction(write=True) as connection:
            connection.execute(
                "UPDATE job_events SET payload_json=? WHERE job_id=? AND sequence=?",
                (json.dumps(changed), job, row["sequence"]),
            )
        try:
            if "rule_result" not in changed:
                assert store.native_fixture_status(job)["state"] == "pending_scientific_admission"
            with pytest.raises(DataError):
                complete_rule_trial(store, job, launch)
        finally:
            with store._transaction(write=True) as connection:
                connection.execute(
                    "UPDATE job_events SET payload_json=? WHERE job_id=? AND sequence=?",
                    (row["payload_json"], job, row["sequence"]),
                )
        assert store.get_job(job)["status"] == "running"
        assert store.heavyweight_job_capacity()["active_count"] == 1
        assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before
    try:
        native_path.write_bytes(b"x" * (MAX_NATIVE_RECEIPT_BYTES + 1))
        with pytest.raises(DataError, match="fixed receipt limit"):
            launch.verify_result(native_path.parent, receipt["admission"])
    finally:
        native_path.write_bytes(observed_bytes)
    return observed_bytes


def _assert_completed_receipt_rewrite_rejected(
    root: Path,
    store: ControlStore,
    job: str,
    launch: NativeLaunch,
    result: dict[str, object],
    receipt: dict[str, Any],
) -> None:
    import json
    import shutil

    from alpha_cli._native_rule_completion import complete_rule_trial
    from alpha_cli._native_rule_projection import publish_projections
    from alpha_cli._native_rule_protocol import canonical
    from alpha_cli.artifact_contract import artifact_metadata

    assert launch.authority is not None
    contract = launch.authority.verify()
    attempt_id = str(result["attempt_id"])
    assert store.verified_research_attempt(PROJECT_ID, attempt_id)["attempt"] == result
    legacy = deepcopy(result)
    cast(dict[str, object], legacy["details"]).pop("native_receipt_ref")
    with pytest.raises(DataError, match="exact native receipt reference"):
        store._verify_research_attempt_run(
            project_id=PROJECT_ID, attempt=legacy, contract_payload=contract
        )
    parent = root / "runs" / str(result["run_id"])
    saved = {
        name: (parent / name).read_bytes()
        for name in ("native_receipt.json", "economics.json", "projections.json", "manifest.json")
    }
    existing_dirs = set((root / "runs").iterdir())
    altered = deepcopy(receipt)
    altered["economics"]["baseline"]["equity_curve"][1][1] += 123.0
    try:
        selectors = publish_projections(
            root,
            str(result["run_id"]),
            altered,
            source_fingerprint=str(launch.implementation_fingerprints()["code"]),
        )
        manifest = json.loads(saved["manifest.json"])
        for name, value in (
            ("native_receipt.json", altered),
            ("economics.json", altered["economics"]),
            ("projections.json", selectors),
        ):
            (parent / name).write_text(canonical(value))
            manifest["artifacts"][name] = artifact_metadata(parent / name)
        (parent / "manifest.json").write_text(json.dumps(manifest, sort_keys=True))
        # No database write: the immutable attempt must defeat a self-consistent artifact rewrite.
        with pytest.raises(DataError, match="exact native receipt reference"):
            complete_rule_trial(store, job, launch)
        with pytest.raises(DataError, match="exact native receipt reference"):
            store.verified_research_attempt(PROJECT_ID, attempt_id)
    finally:
        for name, raw in saved.items():
            (parent / name).write_bytes(raw)
        for directory in set((root / "runs").iterdir()) - existing_dirs:
            shutil.rmtree(directory)
    assert complete_rule_trial(store, job, launch) == result
    assert store.verified_research_attempt(PROJECT_ID, attempt_id)["attempt"] == result


def _assert_snapshot_rewrite_rejected(
    root: Path,
    store: ControlStore,
    result: dict[str, object],
    receipt: dict[str, Any],
    source_fingerprint: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json
    import shutil

    from alpha_cli import _native_rule_projection as projection
    from alpha_cli._native_rule_protocol import canonical
    from alpha_cli.artifact_contract import artifact_metadata
    from alpha_data.snapshot import snapshot_manifest_hash

    parent = root / "runs" / str(result["run_id"])
    saved = {name: (parent / name).read_bytes() for name in ("projections.json", "manifest.json")}
    selectors = json.loads(saved["projections.json"])
    snapshot_id = selectors["snapshot_id"]
    snapshot = root / "snapshots" / snapshot_id
    manifest_path = snapshot / "manifest.json"
    original_snapshot = manifest_path.read_bytes()
    original_receipt = (parent / "native_receipt.json").read_bytes()
    existing_dirs = set((root / "runs").iterdir())
    changed = json.loads(original_snapshot)
    changed["source"] = "tiingo"
    changed["created_at"] = "2099-01-01T00:00:00+00:00"
    manifest_path.write_text(canonical(changed))
    changed_hash = snapshot_manifest_hash(snapshot)
    try:
        with pytest.raises(DataError, match="costed synthetic snapshot"):
            projection.publish_projections(
                root, str(result["run_id"]), receipt, source_fingerprint=source_fingerprint
            )
        assert set((root / "runs").iterdir()) == existing_dirs
        # Deliberately disable only the new producer guard to construct a coordinated
        # artifact attack. Restore it BEFORE invoking the real verified-attempt reader.
        with monkeypatch.context() as scoped:
            scoped.setattr(
                projection, "_snapshot", lambda *args, **kwargs: (snapshot_id, changed_hash)
            )
            forged = projection.publish_projections(
                root, str(result["run_id"]), receipt, source_fingerprint=source_fingerprint
            )
        (parent / "projections.json").write_text(canonical(forged))
        manifest = json.loads(saved["manifest.json"])
        manifest["artifacts"]["projections.json"] = artifact_metadata(parent / "projections.json")
        (parent / "manifest.json").write_text(canonical(manifest))
        with pytest.raises(DataError, match="costed synthetic snapshot"):
            store.verified_research_attempt(PROJECT_ID, str(result["attempt_id"]))
        assert (parent / "native_receipt.json").read_bytes() == original_receipt
    finally:
        manifest_path.write_bytes(original_snapshot)
        for name, raw in saved.items():
            (parent / name).write_bytes(raw)
        for directory in set((root / "runs").iterdir()) - existing_dirs:
            shutil.rmtree(directory)
    assert (
        store.verified_research_attempt(PROJECT_ID, str(result["attempt_id"]))["attempt"] == result
    )


@pytest.mark.parametrize("costed", [False, True])
@pytest.mark.skipif(sys.platform != "linux", reason="requires the Linux native owner profile")
def test_one_actual_native_rule_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, costed: bool, configured_rule_source: Path
) -> None:
    if sys.platform != "linux":
        pytest.skip("requires the Linux native owner profile")
    from datetime import timedelta
    from pathlib import Path

    from alpha_cli._native_loop_admission import NativeLaunch
    from alpha_cli._native_rule_authority import RuleAuthority
    from alpha_cli._native_rule_environment import rule_implementation_fingerprints
    from alpha_cli.control_store import ControlStore
    from alpha_cli.native_supervisor import start_synthetic_owner, synthetic_workspace
    from tests.unit.test_research_control_store import PROJECT_ID, START, _native_d1_job

    job = "6555f253-3ffc-4b03-bd81-5343f29357df"
    source = configured_rule_source
    with synthetic_workspace() as root:
        _pilot(root, rule_implementation_fingerprints(costed), costed=costed)
        store = ControlStore(root)
        cid = str(store.research_case_summary(PROJECT_ID)["active_contract_id"])
        launch = NativeLaunch(
            source,
            "INCONCLUSIVE",
            study=__import__(
                "alpha_cli._native_rule_protocol", fromlist=["selected_study"]
            ).selected_study(costed),
            authority=RuleAuthority(root, PROJECT_ID, cid),
        )
        _, reservation = _native_d1_job(
            store,
            cid,
            job_id=job,
            manifest_sha256=launch.fingerprint,
            started_at=START + timedelta(minutes=12),
        )
        assert (
            store.reserve_d1_native_research_launch(
                PROJECT_ID, cid, job, native_manifest_sha256=launch.fingerprint
            )
            == reservation
        )
        from alpha_cli._native_rule_completion import complete_rule_trial

        with pytest.raises(DataError, match="trusted clean native outcome"):
            complete_rule_trial(store, job, launch)
        process = start_synthetic_owner(root, job, fixture="native_loop", seconds=20, native=launch)
        assert process.wait(timeout=30) == 0, (root / "control" / f"native-{job}.log").read_text()
        status = store.native_fixture_status(job)
        assert status["state"] == "pending_scientific_admission", {
            **status,
            "logs": {str(p.relative_to(root)): p.read_text() for p in root.rglob("*.log")},
        }
        receipt = __import__("json").loads((root / f"payload-{job}" / "receipt.json").read_text())
        assert receipt["rule_positions"]["baseline"] == (
            [0, 1, 0, 1, 0, 0] if costed else [1, 0, 1]
        )
        assert receipt["rule_positions"]["control"] == ([0] * 6 if costed else [0] * 3)

        from alpha_cli._native_rule_completion import complete_rule_trial

        before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
        observed_bytes = _assert_trusted_observation_boundary(
            root, store, job, launch, receipt, before
        )
        if costed:
            import json

            native_path = root / f"payload-{job}" / "receipt.json"
            observed_bytes = native_path.read_bytes()
            altered_receipt = deepcopy(receipt)
            altered_receipt["economics"]["baseline"]["equity_curve"][1][1] += 123.0
            native_path.write_text(json.dumps(altered_receipt))
            try:
                with pytest.raises(DataError, match="trusted observed receipt"):
                    complete_rule_trial(store, job, launch)
            finally:
                native_path.write_bytes(observed_bytes)
            assert store.get_job(job)["status"] == "running"
            assert store.heavyweight_job_capacity()["active_count"] == 1
            assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before
        from alpha_cli import _artifacts

        write_manifest = _artifacts.write_manifest

        def interrupted_publication(*args: Any, **kwargs: Any) -> None:
            raise OSError("injected immutable publication interruption")

        monkeypatch.setattr(_artifacts, "write_manifest", interrupted_publication)
        with pytest.raises(OSError, match="publication interruption"):
            complete_rule_trial(store, job, launch)
        assert store.get_job(job)["status"] == "running"
        assert store.heavyweight_job_capacity()["active_count"] == 1
        assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before
        monkeypatch.setattr(_artifacts, "write_manifest", write_manifest)
        original_verify = NativeLaunch.verify_result

        def capture_then_replace(
            self: NativeLaunch, work: Path, admission: dict[str, object] | None
        ) -> bytes:
            raw = original_verify(self, work, admission)
            (work / "receipt.json").write_bytes(b"changed after the verified bounded read")
            return raw

        with monkeypatch.context() as scoped:
            scoped.setattr(NativeLaunch, "verify_result", capture_then_replace)
            result = complete_rule_trial(store, job, launch)
        (root / f"payload-{job}" / "receipt.json").write_bytes(observed_bytes)
        assert (
            root / "runs" / str(result["run_id"]) / "native_receipt.json"
        ).read_bytes() == observed_bytes
        assert cast(dict[str, object], result["details"])["native_receipt_ref"] == {
            "artifact": "native_receipt.json",
            "content_sha256": hashlib.sha256(observed_bytes).hexdigest(),
        }
        assert result["status"] == "completed"
        assert cast(dict[str, object], result["details"])["scientific_acceptance"] == "not_admitted"
        assert store.get_job(job)["status"] == "succeeded"
        assert store.heavyweight_job_capacity()["active_count"] == 0
        assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before
        assert complete_rule_trial(store, job, launch) == result
        if costed:
            import json

            from alpha_cli._native_rule_projection import validate_projections
            from alpha_cli.run_projection import chart_bundle, compare_runs

            _assert_completed_receipt_rewrite_rejected(root, store, job, launch, result, receipt)
            _assert_snapshot_rewrite_rejected(
                root,
                store,
                result,
                receipt,
                str(launch.implementation_fingerprints()["code"]),
                monkeypatch,
            )
            parent = root / "runs" / str(result["run_id"])
            selectors = json.loads((parent / "projections.json").read_text())
            validate_projections(
                root,
                selectors,
                receipt,
                parent_run_id=str(result["run_id"]),
                source_fingerprint=str(launch.implementation_fingerprints()["code"]),
            )
            _assert_projection_manifest_rejections(
                root, selectors, receipt, str(launch.implementation_fingerprints()["code"])
            )
            run_ids = [selectors["roles"][role]["run_id"] for role in ("baseline", "control")]
            comparison = compare_runs(run_ids, data_dir=root)
            assert comparison["same_snapshot_hash"] is True
            import alpha_cli.run_projection as projection_module

            monkeypatch.setattr(
                projection_module,
                "_ALPHA_BIN",
                str(Path(__file__).resolve().parents[2] / ".venv/bin/alpha"),
            )
            charts = [chart_bundle(run_id, data_dir=root) for run_id in run_ids]
            for role, run_id, chart in zip(("baseline", "control"), run_ids, charts, strict=True):
                assert chart["run_id"] == run_id
                _assert_costed_projection(
                    root / "runs" / run_id,
                    chart,
                    receipt["economics"][role],
                    control=role == "control",
                )
            assert receipt["economics"]["baseline"]["equity_curve"][-1][1] == 12558.21
            assert receipt["economics"]["control"]["equity_curve"][-1][1] == 12000.0
            import polars as pl

            from alpha_cli.artifact_contract import artifact_metadata

            projection_dir = root / "runs" / run_ids[0]
            equity_path = projection_dir / "equity_curve.parquet"
            manifest_path = projection_dir / "manifest.json"
            original_equity = equity_path.read_bytes()
            original_manifest = manifest_path.read_bytes()
            original_reference = dict(selectors["roles"]["baseline"])
            frame = pl.read_parquet(equity_path).with_columns(
                (pl.col("equity") + 1).alias("equity")
            )
            frame.write_parquet(equity_path)
            altered = json.loads(original_manifest)
            altered["artifacts"]["equity_curve.parquet"] = artifact_metadata(equity_path)
            manifest_path.write_text(json.dumps(altered, sort_keys=True, indent=2))
            selectors["roles"]["baseline"]["manifest_sha256"] = hashlib.sha256(
                manifest_path.read_bytes()
            ).hexdigest()
            with pytest.raises(DataError, match="canonical projection sidecar"):
                validate_projections(
                    root,
                    selectors,
                    receipt,
                    parent_run_id=str(result["run_id"]),
                    source_fingerprint=str(launch.implementation_fingerprints()["code"]),
                )
            equity_path.write_bytes(original_equity)
            manifest_path.write_bytes(original_manifest)
            selectors["roles"]["baseline"] = original_reference
        import shutil

        receipt_destination = os.environ.get("ALPHA_RDAGENT_RECEIPTS")
        if receipt_destination:
            evidence = Path(receipt_destination) / "executions" / root.name
            evidence.mkdir(parents=True)
            for folder in ("runs", "snapshots", "control"):
                if (root / folder).exists():
                    shutil.copytree(root / folder, evidence / folder)
            for name in (
                "receipt.json",
                "progress.json",
                "rule-origins.json",
                "baseline.json",
                "control.json",
            ):
                shutil.copy2(root / f"payload-{job}" / name, evidence / name)
        with pytest.raises(DataError, match="reconnect only"):
            start_synthetic_owner(root, job, fixture="native_loop", seconds=20, native=launch)


@pytest.mark.parametrize(
    "field",
    [
        "schema",
        "rules_spec",
        "control_spec",
        "bars",
        "warmup_bars",
        "cutoff",
        "data_sha256",
        "economics",
        "price_unit",
        "horizon_bars",
        "authority",
    ],
)
def test_costed_request_changes_fail_before_effects(field: str) -> None:
    import json

    from alpha_cli._native_rule_economics import CostedRuleStudy, fixed_costed_study

    document = fixed_costed_study().to_dict()
    document[field] = "changed"
    with pytest.raises(DataError, match="data/cutoff/economics/version"):
        CostedRuleStudy(json.dumps(document, sort_keys=True, separators=(",", ":")))


@pytest.mark.parametrize("version", [0, 3, True, 1.0, "1"])
def test_rule_unknown_operator_versions_fail_closed(tmp_path: Path, version: object) -> None:
    from alpha_cli._native_rule_protocol import validate_rule_contract

    store = ControlStore(tmp_path)
    _, payload = _draft(store)
    protocol = cast(dict[str, Any], payload["protocol"])
    protocol["d0_operator"]["version"] = version
    with pytest.raises(DataError, match="version or binding"):
        validate_rule_contract(payload)


def test_real_discovery_is_blocked_without_reading_data() -> None:
    from alpha_cli._native_rule_protocol import real_discovery_readiness

    result = real_discovery_readiness(
        {"instrument": "BTCUSDT", "discovery_start": "2020", "discovery_end": "2022"}
    )
    assert result["status"] == "blocked"
    assert result["effects_started"] is False
    assert "snapshot_sha256" in cast(list[str], result["missing_fields"])
    assert "owner_frozen_contract" in cast(list[str], result["missing_fields"])


def test_reapproved_renamed_project_cannot_reset_trial_exposure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import timedelta

    import tests.unit.test_research_control_store as fixtures
    from tests.unit.test_research_control_store import START, _native_d1_job

    first_job = "99aa3c1e-854b-4c96-b91f-f023820f2851"
    second_job = "26fa5abb-a18f-40d0-bef5-05cb0573160a"
    second_project = "ad1357e3-4ddc-42fa-968a-aedc503324bb"
    root = tmp_path
    _pilot(root)
    store = ControlStore(root)
    cid = str(store.research_case_summary(PROJECT_ID)["active_contract_id"])
    _, reservation = _native_d1_job(
        store, cid, job_id=first_job, started_at=START + timedelta(minutes=12)
    )
    assert store.get_job(first_job)["job_id"] == first_job
    with store._transaction(write=False) as connection:
        assert not connection.execute(
            "SELECT 1 FROM job_events WHERE job_id=? AND event_type LIKE 'native_%'",
            (first_job,),
        ).fetchall()
    before = store.research_case_summary(PROJECT_ID)["elapsed_budget"]
    store.record_research_attempt(
        PROJECT_ID,
        cid,
        kind="d1-deep-research",
        status="failed",
        config_fingerprint=str(reservation["config_fingerprint"]),
        budget_used={},
        error="Synthetic inert proposal stopped before any process claim",
        details={"attempt_number": 1, "evidence_zone": "D1"},
        launch_reservation_id=str(reservation["reservation_id"]),
        at=START + timedelta(minutes=13),
    )
    store.set_job_status(
        first_job,
        "failed",
        terminal_error="Synthetic no-process failure",
        at=START + timedelta(minutes=13),
    )
    store.transition_research_execution(
        PROJECT_ID,
        to_state="failed",
        contract_id=cid,
        actor="system",
        reason="Inert synthetic trial failed",
        next_action="Inspect retained charge",
        responsibility="owner",
        blocker="No process was started",
        recovery="No retry allowed",
        at=START + timedelta(minutes=14),
    )
    assert store.heavyweight_job_capacity()["active_count"] == 0
    assert store.research_case_summary(PROJECT_ID)["elapsed_budget"] == before
    _pilot(root, project_id=second_project)
    second_cid = str(store.research_case_summary(second_project)["active_contract_id"])
    assert second_cid != cid
    with monkeypatch.context() as scoped:
        # Select the second synthetic project in the existing inert-job fixture helper.
        scoped.setattr(fixtures, "PROJECT_ID", second_project)
        with pytest.raises(DataError, match="one trial exposure"):
            _native_d1_job(
                store, second_cid, job_id=second_job, started_at=START + timedelta(minutes=12)
            )
    with store._transaction(write=False) as connection:
        assert not connection.execute(
            "SELECT 1 FROM job_events WHERE job_id=? AND event_type LIKE 'native_%'",
            (second_job,),
        ).fetchall()
    assert store.get_job(second_job)["job_id"] == second_job
    assert not (root / f"payload-{first_job}").exists()
    assert not (root / f"payload-{second_job}").exists()
    with store._transaction(write=False) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM research_launch_reservations WHERE phase='deep_research'"
            ).fetchone()[0]
            == 1
        )


@pytest.mark.parametrize("costed", [False, True])
def test_qualified_installed_bytes_are_rechecked_before_admission(
    monkeypatch: pytest.MonkeyPatch, costed: bool, configured_rule_source: Path
) -> None:
    from alpha_cli._native_loop_admission import WORKER
    from alpha_cli._native_rule_environment import measure_rule_environment

    runtime = WORKER / (".venv-economics-qualified" if costed else ".venv-rule-qualified")
    target = runtime / "lib/python3.12/site-packages/alpha_strategies/rules.py"
    original = Path.read_bytes

    def changed_read(path: Path) -> bytes:
        raw = original(path)
        return raw + b"\n# substituted bytes\n" if path == target else raw

    monkeypatch.setattr(Path, "read_bytes", changed_read)
    with pytest.raises(DataError, match="installed rule runtime bytes changed"):
        measure_rule_environment(costed)


def test_runtime_inventory_rejects_cache_and_symlink(tmp_path: Path) -> None:
    from alpha_cli._native_rule_environment import _files

    cached = tmp_path / "stale.pyc"
    cached.write_bytes(b"unqualified bytecode")
    with pytest.raises(DataError, match="unqualified bytecode"):
        _files(tmp_path)
    cached.unlink()
    (tmp_path / "linked.py").symlink_to(Path(__file__))
    with pytest.raises(DataError, match="package symlink"):
        _files(tmp_path)


@pytest.mark.parametrize("mutation", ["issued_nested_mapping", "caller_original_alias"])
def test_issued_rule_receipt_binding_is_detached_and_immutable(mutation: str) -> None:
    """Object-only regression: no child execution, journal record or synthetic approval."""
    if sys.platform != "linux":
        pytest.skip("requires an actual Linux native owner to issue the receipt")
    from collections.abc import Mapping, MutableMapping

    from alpha_cli.native_supervisor import (
        _open_lock,
        _Owner,
        _verify_observation,
        synthetic_workspace,
    )

    job = "46df8184-82b3-45cd-a061-d5130584ab21"
    original = {"schema": "SyntheticNativeRuleObservationV1", "receipt_sha256": "a" * 64}
    with synthetic_workspace() as root, _open_lock(root, job) as lock:
        owner = _Owner(root, job, "success", 5, lock)
        # Exercise the real issuer/owner identity without publishing a fabricated process fact.
        observation = owner._issue("native_outcome", {"rule_result": original})
        assert _verify_observation(observation) is observation
        if mutation == "issued_nested_mapping":
            nested = cast(MutableMapping[str, object], observation.fields["rule_result"])
            with pytest.raises(TypeError):
                nested["receipt_sha256"] = "b" * 64
        else:
            original["receipt_sha256"] = "b" * 64
        assert (
            cast(Mapping[str, object], observation.fields["rule_result"])["receipt_sha256"]
            == "a" * 64
        )
        assert _verify_observation(observation) is observation


@pytest.mark.parametrize(
    "mutation",
    [
        "source",
        "created_at",
        "adapter_version",
        "parser_version",
        "snapshot_id",
        "schema_version",
        "empty_symbols",
        "extra_symbol",
        "missing_provenance",
        "extra_actions",
        "provenance_source",
        "provenance_adapter_version",
        "provenance_parser_version",
        "provenance_schema_version",
    ],
)
def test_costed_snapshot_rejects_rehashed_lineage_without_repair(
    tmp_path: Path, mutation: str
) -> None:
    import json

    from alpha_cli._native_rule_projection import _snapshot
    from alpha_cli._native_rule_protocol import canonical

    snapshot_id, expected_hash = _snapshot(tmp_path)
    snapshot = tmp_path / "snapshots" / snapshot_id
    manifest_path = snapshot / "manifest.json"
    original = manifest_path.read_bytes()
    manifest = json.loads(original)
    entry = manifest["symbols"]["RULES"]
    provenance_path = snapshot / entry["provenance_file"]
    original_provenance = provenance_path.read_bytes()
    if mutation.startswith("provenance_"):
        field = mutation.removeprefix("provenance_")
        provenance = json.loads(original_provenance)
        provenance[field] = 2 if field == "schema_version" else "unadmitted"
        provenance_path.write_text(canonical(provenance))
        entry["provenance_sha256"] = hashlib.sha256(provenance_path.read_bytes()).hexdigest()
    elif mutation == "empty_symbols":
        manifest["symbols"] = {}
    elif mutation == "extra_symbol":
        manifest["symbols"]["UNADMITTED"] = dict(entry)
    elif mutation == "missing_provenance":
        del entry["provenance_file"], entry["provenance_sha256"]
    elif mutation == "extra_actions":
        entry["actions_file"] = entry["bars_file"]
        entry["actions_sha256"] = entry["bars_sha256"]
    else:
        manifest[mutation] = 2 if mutation == "schema_version" else "unadmitted"
    manifest_path.write_text(canonical(manifest))
    changed_manifest = manifest_path.read_bytes()
    changed_provenance = provenance_path.read_bytes()
    for create in (False, True):
        with pytest.raises(DataError, match="costed synthetic snapshot"):
            _snapshot(tmp_path, create=create)
        assert manifest_path.read_bytes() == changed_manifest
        assert provenance_path.read_bytes() == changed_provenance
    manifest_path.write_bytes(original)
    provenance_path.write_bytes(original_provenance)
    assert _snapshot(tmp_path, create=False) == (snapshot_id, expected_hash)
