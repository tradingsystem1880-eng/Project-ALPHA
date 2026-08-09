"""Owner/Codex research workflow from raw idea through the synthetic Gate-1 pilot."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import cast

import pytest
from typer.testing import CliRunner

from alpha_cli import research_cmds
from alpha_cli.artifact_contract import artifact_metadata
from alpha_cli.control_store import ControlStore
from alpha_cli.main import app
from alpha_core import DataError
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()


def _invoke(*args: str) -> dict[str, object]:
    result = runner.invoke(app, ["research", *args, "--json"])
    assert result.exit_code == 0, result.output
    value: object = json.loads(result.output)
    assert isinstance(value, dict)
    return value


def _rewrite_d0_acceptance_and_manifest(data_dir: Path, run_id: str) -> None:
    run_dir = data_dir / "runs" / run_id
    acceptance_path = run_dir / "d0_acceptance.json"
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    acceptance["measurements"]["planted_events"] = []
    acceptance_path.write_text(
        json.dumps(acceptance, sort_keys=True, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["d0_acceptance.json"] = artifact_metadata(acceptance_path)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")


def test_raw_idea_reaches_bounded_contract_review_and_synthetic_pilot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke(
        "capture",
        "I notice the S&P500 bounces after double bottoms on the 4h time frame",
    )
    project = captured["project"]
    contract = captured["contract"]
    case = captured["case"]
    assert isinstance(project, dict) and isinstance(contract, dict) and isinstance(case, dict)
    project_id = str(project["project_id"])
    assert case["phase"] == "triage"
    assert case["responsibility"] == "owner"
    payload = contract["payload"]
    assert isinstance(payload, dict)
    assert len(payload["blocking_questions"]) == 3
    assert payload["raw_idea"] == (
        "I notice the S&P500 bounces after double bottoms on the 4h time frame"
    )
    assert case["d2_state"] == "sealed"

    source = _invoke(
        "sources",
        "add",
        project_id,
        "--title",
        "Technical trading revisited",
        "--locator",
        "doi:10.0000/example",
        "--provider",
        "crossref",
        "--access-mode",
        "metadata_only",
    )
    pack = _invoke(
        "sources",
        "freeze",
        project_id,
        "--source-id",
        str(source["source_id"]),
    )
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
    frozen_contract = drafted["contract"]
    review_case = drafted["case"]
    assert isinstance(frozen_contract, dict) and isinstance(review_case, dict)
    frozen_id = str(frozen_contract["contract_id"])
    frozen_payload = frozen_contract["payload"]
    assert isinstance(frozen_payload, dict)
    assert frozen_payload["approval_ready"] is True
    assert frozen_payload["blocking_questions"] == []
    assert frozen_payload["source_pack_id"] == pack["pack_id"]
    hashes = frozen_payload["hashes"]
    assert isinstance(hashes, dict)
    assert hashes["data"] is None
    for field in ("code", "dependency_lock", "environment", "evaluator"):
        assert isinstance(hashes[field], str)
        assert len(hashes[field]) == 64
    assert review_case["phase"] == "exploration_review"
    assert review_case["responsibility"] == "owner"

    approved = _invoke(
        "approve",
        "exploration",
        project_id,
        frozen_id,
        "--actor",
        "owner",
        "--reason",
        "The bounded protocol and source pack are suitable for D0/D1 exploration.",
    )
    approved_case = approved["case"]
    assert isinstance(approved_case, dict)
    assert approved_case["phase"] == "pilot"
    assert approved_case["responsibility"] == "codex"

    pilot = _invoke("run", "pilot", project_id)
    manifest = pilot["manifest"]
    attempt = pilot["attempt"]
    pilot_case = pilot["case"]
    assert isinstance(manifest, dict) and isinstance(attempt, dict)
    assert isinstance(pilot_case, dict)
    assert manifest["evidence_zone"] == "D0"
    assert manifest["real_market_evidence"] is False
    assert pilot_case["phase"] == "research_decision"
    assert pilot_case["execution_state"] == "idle"
    assert pilot_case["responsibility"] == "owner"
    assert pilot_case["next_action"] == (
        "Owner records INCONCLUSIVE with revise, park, or reject; empirical D1 is unavailable "
        "in Gate 1."
    )
    assert pilot_case["attempt_count"] == 1
    assert pilot_case["terminal_attempt_count"] == 1
    assert pilot_case["unfinalized_launch_count"] == 0
    assert pilot_case["remaining_launches"] == 2
    assert pilot_case["elapsed_budget"] == {
        "source_requests": 0,
        "variants": 3,
        "wall_seconds": 1,
    }
    assert attempt["budget_used"] == {}
    assert attempt["launch_reservation_id"] == pilot_case["latest_launch_reservation_id"]
    details = attempt["details"]
    assert isinstance(details, dict)
    assert details["d0_acceptance_ref"] == {
        "artifact": "d0_acceptance.json",
        "content_sha256": manifest["artifacts"]["d0_acceptance.json"]["sha256"],
    }
    assert pilot_case["d2_state"] == "sealed"
    assert pilot_case["latest_run_id"] == manifest["run_id"]
    assert pilot_case["latest_run_fingerprint"] == manifest["execution_fingerprint"]
    assert "not real-market evidence" in str(pilot_case["latest_finding"])
    assert pilot_case["elapsed_time_seconds"] >= 0
    assert pilot_case["completed_milestones"][-1]["phase"] == "research_decision"
    assert pilot_case["remaining_milestones"] == ["closed"]

    contradicted = runner.invoke(
        app,
        [
            "research",
            "decide",
            project_id,
            "--outcome",
            "CONTRADICTED",
            "--disposition",
            "reject",
            "--actor",
            "owner",
            "--reason",
            "D0 alone must not be presented as a market contradiction.",
            "--json",
        ],
    )
    assert contradicted.exit_code != 0
    after_rejected_claim = _invoke("status", project_id)
    assert after_rejected_claim["phase"] == "research_decision"
    assert after_rejected_claim["research_decision"] is None

    closed = _invoke(
        "decide",
        project_id,
        "--outcome",
        "INCONCLUSIVE",
        "--disposition",
        "park",
        "--actor",
        "owner",
        "--reason",
        "D0 passed, but empirical D1/D2 remain gated and no market claim is supportable.",
    )
    closed_case = cast(dict[str, object], closed["case"])
    assert closed_case["phase"] == "closed"
    assert closed_case["d2_state"] == "sealed"
    terminal = _invoke("report", project_id)
    assert terminal["report_schema"] == "ResearchGatePacketV1"
    assert terminal["scientific_outcome"] == "INCONCLUSIVE"
    assert terminal["recommended_disposition"] == "park"


def test_interrupted_pilot_recovery_rejects_post_admission_d0_rewrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke(
        "capture",
        "I notice the S&P500 bounces after double bottoms on the 4h time frame",
    )
    project = cast(dict[str, object], captured["project"])
    project_id = str(project["project_id"])
    store = ControlStore(tmp_path)
    source = store.create_research_source(
        project_id,
        title="Synthetic recovery protocol",
        locator="owner:synthetic-recovery",
        provider="owner",
        access_mode="owner_provided",
    )
    pack = store.create_research_source_pack(
        project_id,
        source_ids=[str(source["source_id"])],
    )
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
        "Approve the recovery integrity fixture.",
    )

    original_transition = ControlStore.transition_research_phase
    interrupted = False

    def interrupt_after_terminal_attempt(
        self: ControlStore, *args: object, **kwargs: object
    ) -> dict[str, object]:
        nonlocal interrupted
        if kwargs.get("to_phase") == "research_decision" and not interrupted:
            interrupted = True
            raise RuntimeError("simulated process interruption after D0 admission")
        return original_transition(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(ControlStore, "transition_research_phase", interrupt_after_terminal_attempt)
    first = runner.invoke(app, ["research", "run", "pilot", project_id, "--json"])
    assert first.exit_code != 0
    checkpoint = store.research_case_summary(project_id)
    assert checkpoint["phase"] == "pilot"
    assert checkpoint["execution_state"] == "idle"
    run_id = cast(str, checkpoint["latest_run_id"])
    _rewrite_d0_acceptance_and_manifest(tmp_path, run_id)

    recovery = runner.invoke(app, ["research", "run", "pilot", project_id, "--json"])
    assert recovery.exit_code != 0
    assert "deterministic" in recovery.output
    assert "recomputation" in recovery.output
    database = sqlite3.connect(tmp_path / "control" / "workstation.sqlite3")
    latest_phase = database.execute(
        "SELECT phase FROM research_phase_events WHERE project_id = ? "
        "ORDER BY sequence DESC LIMIT 1",
        (project_id,),
    ).fetchone()
    database.close()
    assert latest_phase == ("pilot",)


def test_generated_dossier_export_and_verify_use_current_sqlite_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "Synthetic-only double bottom detector validation")
    project = captured["project"]
    assert isinstance(project, dict)
    project_id = str(project["project_id"])

    exported = _invoke("export", project_id)
    path = Path(str(exported["path"]))
    assert path.is_file()
    assert "GENERATED PROJECTION" in path.read_text(encoding="utf-8")
    verified = _invoke("verify", project_id, "--path", str(path))
    assert verified["sha256"] == exported["sha256"]

    path.write_text(path.read_text(encoding="utf-8") + "manual edit\n", encoding="utf-8")
    failed = runner.invoke(
        app,
        ["research", "verify", project_id, "--path", str(path), "--json"],
    )
    assert failed.exit_code != 0
    assert "does not match its deterministic projection" in failed.output


def test_pause_resume_and_cancel_preserve_the_active_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "Pause and resume a bounded source-feasibility check")
    project = cast(dict[str, object], captured["project"])
    contract = cast(dict[str, object], captured["contract"])
    project_id = str(project["project_id"])
    contract_id = str(contract["contract_id"])
    ControlStore(tmp_path).transition_research_execution(
        project_id,
        to_state="queued",
        contract_id=contract_id,
        actor="codex",
        reason="Queue the bounded triage checkpoint.",
        next_action="Codex checks source feasibility.",
        responsibility="codex",
    )

    paused = _invoke(
        "pause",
        project_id,
        "--reason",
        "Owner requested a checkpoint.",
        "--checkpoint",
        "triage:source-feasibility",
    )
    assert paused["execution_state"] == "paused"
    assert paused["checkpoint"] == "triage:source-feasibility"
    resumed = _invoke("resume", project_id)
    assert resumed["execution_state"] == "queued"
    cancelled = _invoke(
        "cancel",
        project_id,
        "--reason",
        "Owner ended the queued work without changing the evidence phase.",
    )
    assert cancelled["execution_state"] == "idle"
    assert cancelled["active_contract_id"] == contract_id


def test_owner_can_reject_and_replace_an_exploration_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "Synthetic-only owner rejection fixture")
    project = cast(dict[str, object], captured["project"])
    project_id = str(project["project_id"])
    source = _invoke(
        "sources",
        "add",
        project_id,
        "--title",
        "Owner protocol",
        "--locator",
        "owner:protocol",
        "--provider",
        "owner",
        "--access-mode",
        "owner_provided",
    )
    pack = _invoke(
        "sources",
        "freeze",
        project_id,
        "--source-id",
        str(source["source_id"]),
    )
    answers = (
        "--answer",
        "chart_construction=synthetic_only",
        "--answer",
        "event_availability=second_trough_confirmable",
        "--answer",
        "primary_outcome=four_trading_hour_return_25bp",
    )
    first = _invoke(
        "draft",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        *answers,
    )
    first_contract = cast(dict[str, object], first["contract"])
    rejected = _invoke(
        "reject",
        "exploration",
        project_id,
        str(first_contract["contract_id"]),
        "--actor",
        "owner",
        "--reason",
        "The owner requires a replacement contract.",
    )
    rejected_case = cast(dict[str, object], rejected["case"])
    assert rejected_case["exploration_review"]["state"] == "rejected"  # type: ignore[index]
    assert rejected_case["responsibility"] == "owner"

    replacement = _invoke(
        "draft",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        "--answer",
        "chart_construction=synthetic_only",
        "--answer",
        "event_availability=neckline_breakout_confirmed",
        "--answer",
        "primary_outcome=four_trading_hour_return_25bp",
    )
    replacement_contract = cast(dict[str, object], replacement["contract"])
    assert replacement_contract["contract_id"] != first_contract["contract_id"]
    replacement_case = cast(dict[str, object], replacement["case"])
    assert replacement_case["phase"] == "exploration_review"
    assert replacement_case["exploration_review"]["state"] == "pending"  # type: ignore[index]


def test_rejected_exploration_can_close_and_reopen_one_pre_d2_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "SPY double bottom pre-D2 revision fixture")
    project = cast(dict[str, object], captured["project"])
    project_id = str(project["project_id"])
    source = _invoke(
        "sources",
        "add",
        project_id,
        "--title",
        "Revision protocol",
        "--locator",
        "owner:revision-protocol",
        "--provider",
        "owner",
        "--access-mode",
        "owner_provided",
    )
    pack = _invoke(
        "sources",
        "freeze",
        project_id,
        "--source-id",
        str(source["source_id"]),
    )
    answers = (
        "--answer",
        "chart_construction=spy_rth_60m_four_hour_window",
        "--answer",
        "event_availability=second_trough_confirmable",
        "--answer",
        "primary_outcome=four_trading_hour_return_25bp",
    )
    drafted = _invoke(
        "draft",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        *answers,
    )
    contract = cast(dict[str, object], drafted["contract"])
    _invoke(
        "reject",
        "exploration",
        project_id,
        str(contract["contract_id"]),
        "--actor",
        "owner",
        "--reason",
        "The protocol needs one bounded pre-D2 revision.",
    )
    closed = _invoke(
        "decide",
        project_id,
        "--outcome",
        "INVALID",
        "--disposition",
        "revise",
        "--actor",
        "owner",
        "--reason",
        "Reject this protocol without opening D2, then revise it.",
    )
    assert cast(dict[str, object], closed["case"])["phase"] == "closed"

    revised = _invoke(
        "revise",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        *answers,
        "--actor",
        "owner",
        "--reason",
        "Reopen one immutable child while the original D2 boundary is still sealed.",
    )
    revised_contract = cast(dict[str, object], revised["contract"])
    revised_case = cast(dict[str, object], revised["case"])
    assert revised_contract["parent_contract_id"] == contract["contract_id"]
    assert revised_case["phase"] == "exploration_review"
    assert revised_case["active_contract_id"] == revised_contract["contract_id"]
    assert revised_case["d2_state"] == "sealed"
    assert (
        revised_contract["payload"]["protocol"]["evidence_topology"]["D2"][  # type: ignore[index]
            "relation_to_prior"
        ]
        == "unopened_sealed_reuse"
    )

    replay = _invoke(
        "revise",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        *answers,
        "--actor",
        "owner",
        "--reason",
        "Reopen one immutable child while the original D2 boundary is still sealed.",
    )
    assert (
        cast(dict[str, object], replay["contract"])["contract_id"]
        == revised_contract["contract_id"]
    )


def test_draft_rejects_cross_project_source_pack_before_persisting_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    first = cast(dict[str, object], _invoke("capture", "First synthetic case")["project"])
    second = cast(dict[str, object], _invoke("capture", "Second synthetic case")["project"])
    source = _invoke(
        "sources",
        "add",
        str(first["project_id"]),
        "--title",
        "First project source",
        "--locator",
        "owner:first",
        "--provider",
        "owner",
        "--access-mode",
        "owner_provided",
    )
    pack = _invoke(
        "sources",
        "freeze",
        str(first["project_id"]),
        "--source-id",
        str(source["source_id"]),
    )
    before = _invoke("status", str(second["project_id"]))
    failed = runner.invoke(
        app,
        [
            "research",
            "draft",
            str(second["project_id"]),
            "--source-pack-id",
            str(pack["pack_id"]),
            "--answer",
            "chart_construction=synthetic_only",
            "--answer",
            "event_availability=second_trough_confirmable",
            "--answer",
            "primary_outcome=four_trading_hour_return_25bp",
            "--json",
        ],
    )
    assert failed.exit_code != 0
    assert "must belong" in failed.output
    after = _invoke("status", str(second["project_id"]))
    assert after["active_contract_id"] == before["active_contract_id"]


def test_deep_and_confirmation_runs_remain_gated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "A generic synthetic research idea")
    project = captured["project"]
    assert isinstance(project, dict)
    project_id = str(project["project_id"])

    for phase in ("deep", "confirm"):
        result = runner.invoke(
            app,
            ["research", "run", phase, project_id, "--json"],
        )
        assert result.exit_code != 0
        assert "Gate-1 unavailable" in result.output


def test_postlaunch_v1_project_attaches_to_research_through_public_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    control_dir = tmp_path / "control"
    control_dir.mkdir()
    database = control_dir / "workstation.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE projects (
            project_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            hypothesis TEXT NOT NULL,
            falsification_criterion TEXT NOT NULL,
            status TEXT NOT NULL,
            current_version_id TEXT,
            current_experiment_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        ) STRICT;
        PRAGMA user_version = 1;
        """
    )
    project_id = "f03802b8-df35-4f19-a90c-0b3437aa587d"
    connection.execute(
        "INSERT INTO projects VALUES (?, ?, ?, ?, 'active', NULL, NULL, ?, ?)",
        (
            project_id,
            "Migrated postlaunch research project",
            "SPY double bottoms may precede positive four-hour returns.",
            "Reject when the registered effect is absent.",
            "2026-08-06T00:00:00.000000Z",
            "2026-08-06T00:00:00.000000Z",
        ),
    )
    connection.commit()
    connection.close()

    source = _invoke(
        "sources",
        "add",
        project_id,
        "--title",
        "Migrated protocol source",
        "--locator",
        "owner:migrated-source",
        "--provider",
        "owner",
        "--access-mode",
        "owner_provided",
    )
    pack = _invoke(
        "sources",
        "freeze",
        project_id,
        "--source-id",
        str(source["source_id"]),
    )
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
    case = cast(dict[str, object], drafted["case"])
    assert case["phase"] == "exploration_review"
    assert case["responsibility"] == "owner"


@pytest.mark.parametrize(
    ("idea", "chart", "availability"),
    [
        (
            "A generic owner research event may predict returns",
            "spy_rth_60m_four_hour_window",
            "second_trough_confirmable",
        ),
        (
            "SPY double bottom neckline variants may predict returns",
            "spy_rth_60m_four_hour_window",
            "neckline_breakout_confirmed",
        ),
        (
            "SPY double bottom literal extended-hours variant",
            "spy_extended_fixed_4h",
            "second_trough_confirmable",
        ),
    ],
)
def test_gate1_unavailable_contracts_cannot_be_approved_or_attempted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    idea: str,
    chart: str,
    availability: str,
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", idea)
    project = cast(dict[str, object], captured["project"])
    project_id = str(project["project_id"])
    store = ControlStore(tmp_path)
    source = store.create_research_source(
        project_id,
        title="Unsupported D0 fixture protocol",
        locator="owner:unsupported-d0",
        provider="owner",
        access_mode="owner_provided",
    )
    pack = store.create_research_source_pack(
        project_id,
        source_ids=[str(source["source_id"])],
    )
    drafted = _invoke(
        "draft",
        project_id,
        "--source-pack-id",
        str(pack["pack_id"]),
        "--answer",
        f"chart_construction={chart}",
        "--answer",
        f"event_availability={availability}",
        "--answer",
        "primary_outcome=four_trading_hour_return_25bp",
    )
    contract = cast(dict[str, object], drafted["contract"])
    payload = cast(dict[str, object], contract["payload"])
    case = cast(dict[str, object], drafted["case"])
    assert payload["approval_ready"] is False
    assert cast(dict[str, object], payload["gate1_availability"])["state"] == "UNAVAILABLE"
    assert case["phase"] == "exploration_review"
    assert case["responsibility"] == "owner"
    assert "rejects and closes" in str(case["next_action"])

    failed = runner.invoke(
        app,
        [
            "research",
            "approve",
            "exploration",
            project_id,
            str(contract["contract_id"]),
            "--actor",
            "owner",
            "--reason",
            "Unavailable operators cannot enter the pilot phase.",
            "--json",
        ],
    )
    assert failed.exit_code != 0
    assert "approval_ready=true" in failed.output
    status = _invoke("status", project_id)
    assert status["phase"] == "exploration_review"
    assert status["execution_state"] == "idle"
    assert status["attempt_count"] == 0
    assert not (tmp_path / "runs").exists()


def test_pilot_rejects_implementation_drift_before_reserving_a_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "Synthetic double bottom implementation drift fixture")
    project = cast(dict[str, object], captured["project"])
    project_id = str(project["project_id"])
    store = ControlStore(tmp_path)
    source = store.create_research_source(
        project_id,
        title="Synthetic implementation fingerprint protocol",
        locator="owner:synthetic-implementation-drift",
        provider="owner",
        access_mode="owner_provided",
    )
    pack = store.create_research_source_pack(
        project_id,
        source_ids=[str(source["source_id"])],
    )
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
        "Approve the exact implementation fingerprint fixture.",
    )
    current = research_cmds._implementation_hashes()
    monkeypatch.setattr(
        research_cmds,
        "_implementation_hashes",
        lambda: {**current, "code": "0" * 64},
    )

    rejected = runner.invoke(app, ["research", "run", "pilot", project_id, "--json"])
    assert rejected.exit_code != 0
    assert "implementation fingerprints no longer match" in rejected.output
    case = _invoke("status", project_id)
    assert case["execution_state"] == "idle"
    assert case["attempt_count"] == 0
    database = sqlite3.connect(tmp_path / "control" / "workstation.sqlite3")
    assert database.execute("SELECT COUNT(*) FROM research_launch_reservations").fetchone() == (0,)
    database.close()


@pytest.mark.parametrize("error_type", [DataError, RuntimeError, OSError])
def test_pilot_failures_checkpoint_and_stop_after_two_safe_retries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "Synthetic double bottom detector retry fixture")
    project = captured["project"]
    assert isinstance(project, dict)
    project_id = str(project["project_id"])
    store = ControlStore(tmp_path)
    source = store.create_research_source(
        project_id,
        title="Synthetic fixture protocol",
        locator="owner:synthetic-fixture",
        provider="owner",
        access_mode="owner_provided",
    )
    pack = store.create_research_source_pack(
        project_id,
        source_ids=[str(source["source_id"])],
    )
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
    contract = drafted["contract"]
    assert isinstance(contract, dict)
    _invoke(
        "approve",
        "exploration",
        project_id,
        str(contract["contract_id"]),
        "--actor",
        "owner",
        "--reason",
        "Approve the bounded retry fixture.",
    )

    def fail_pilot(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise error_type("planted fixture calibration failed")

    monkeypatch.setattr(research_cmds, "run_synthetic_pilot", fail_pilot)
    for attempt_number in range(1, 4):
        failed = runner.invoke(app, ["research", "run", "pilot", project_id, "--json"])
        assert failed.exit_code != 0
        assert "failed and was checkpointed" in failed.output
        case = _invoke("status", project_id)
        assert case["attempt_count"] == attempt_number
        assert case["terminal_attempt_count"] == attempt_number
        assert case["unfinalized_launch_count"] == 0
        assert case["elapsed_budget"] == {
            "source_requests": 0,
            "variants": 3 * attempt_number,
            "wall_seconds": attempt_number,
        }
        assert case["checkpoint"] == f"d0:failed:{attempt_number}"
        assert case["execution_state"] == ("blocked" if attempt_number == 3 else "failed")
        assert case["phase"] == ("research_decision" if attempt_number == 3 else "pilot")
        if attempt_number < 3:
            resumed = _invoke("resume", project_id)
            assert resumed["execution_state"] == "queued"

    exhausted = runner.invoke(app, ["research", "resume", project_id, "--json"])
    assert exhausted.exit_code != 0
    assert "terminal research decision state" in exhausted.output
    terminal = _invoke("status", project_id)
    assert terminal["execution_state"] == "blocked"
    assert terminal["d2_state"] == "sealed"

    closed = _invoke(
        "decide",
        project_id,
        "--outcome",
        "INVALID",
        "--disposition",
        "park",
        "--actor",
        "owner",
        "--reason",
        "The synthetic evaluator exhausted its safe retry budget.",
    )
    closed_case = closed["case"]
    assert isinstance(closed_case, dict)
    assert closed_case["phase"] == "closed"
    assert closed_case["execution_state"] == "idle"
    assert closed_case["d2_state"] == "sealed"
    packet = _invoke("report", project_id)
    assert packet["report_schema"] == "ResearchGatePacketV1"
    assert packet["terminal"] is True
    assert packet["scientific_outcome"] == "INVALID"
    assert packet["recommended_disposition"] == "park"
    layers = packet["layers"]
    assert isinstance(layers, dict)
    conclusion = layers["conclusion_90_seconds"]
    assert isinstance(conclusion, dict)
    assert conclusion["evidence_basis"] == "NO_TYPED_NON_SYNTHETIC_EVIDENCE"


def test_store_failure_after_successful_pilot_never_fabricates_a_failed_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A completed pilot whose attempt write fails must not be recorded as a pilot failure."""
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "Synthetic double bottom attempt-recording fixture")
    project = captured["project"]
    assert isinstance(project, dict)
    project_id = str(project["project_id"])
    store = ControlStore(tmp_path)
    source = store.create_research_source(
        project_id,
        title="Synthetic fixture protocol",
        locator="owner:synthetic-fixture",
        provider="owner",
        access_mode="owner_provided",
    )
    pack = store.create_research_source_pack(
        project_id,
        source_ids=[str(source["source_id"])],
    )
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
    contract = drafted["contract"]
    assert isinstance(contract, dict)
    _invoke(
        "approve",
        "exploration",
        project_id,
        str(contract["contract_id"]),
        "--actor",
        "owner",
        "--reason",
        "Approve the attempt-recording fixture.",
    )

    original_record = ControlStore.record_research_attempt

    def flaky_record(
        self: ControlStore, project_id: str, contract_id: str, **kwargs: object
    ) -> dict[str, object]:
        if kwargs.get("status") == "completed":
            raise DataError("injected: attempt store write failed after the pilot succeeded")
        return original_record(self, project_id, contract_id, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(ControlStore, "record_research_attempt", flaky_record)
    result = runner.invoke(app, ["research", "run", "pilot", project_id, "--json"])
    assert result.exit_code != 0
    assert "completed and published immutable run" in result.output
    monkeypatch.setattr(ControlStore, "record_research_attempt", original_record)

    # The immutable run was genuinely published.
    run_dirs = [path for path in (tmp_path / "runs").iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    manifest = json.loads((run_dirs[0] / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["command"] == "research_pilot"

    # The consumed launch stays counted (crash-consumes rule), but no attempt record of any
    # status was fabricated and the reservation stays visibly unfinalized.
    case = _invoke("status", project_id)
    assert case["attempt_count"] == 1
    assert case["terminal_attempt_count"] == 0
    assert case["unfinalized_launch_count"] == 1
    assert case["execution_state"] == "running"

    # The documented recovery path works: resume, re-run, and the identical immutable run
    # republishes idempotently while the interrupted reservation stays consumed.
    resumed = _invoke("resume", project_id, "--acknowledge-orphaned-process")
    assert resumed["execution_state"] == "queued"
    recovered = _invoke("run", "pilot", project_id)
    recovered_manifest = recovered["manifest"]
    recovered_case = recovered["case"]
    assert isinstance(recovered_manifest, dict) and isinstance(recovered_case, dict)
    assert recovered_manifest["run_id"] == manifest["run_id"]
    assert recovered_case["attempt_count"] == 2
    assert recovered_case["terminal_attempt_count"] == 1
    assert recovered_case["phase"] == "research_decision"
    assert recovered_case["remaining_launches"] == 1


def test_hard_crashes_consume_launch_slots_budget_and_deny_a_fourth_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "Synthetic double bottom hard-crash reservation fixture")
    project = cast(dict[str, object], captured["project"])
    project_id = str(project["project_id"])
    store = ControlStore(tmp_path)
    source = store.create_research_source(
        project_id,
        title="Synthetic hard-crash protocol",
        locator="owner:synthetic-hard-crash",
        provider="owner",
        access_mode="owner_provided",
    )
    pack = store.create_research_source_pack(
        project_id,
        source_ids=[str(source["source_id"])],
    )
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
        "Approve the crash durability fixture.",
    )

    def hard_crash(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise KeyboardInterrupt

    monkeypatch.setattr(research_cmds, "run_synthetic_pilot", hard_crash)
    for launch_number in range(1, 4):
        crashed = runner.invoke(app, ["research", "run", "pilot", project_id, "--json"])
        assert crashed.exit_code != 0
        case = _invoke("status", project_id)
        assert case["execution_state"] == "running"
        assert case["attempt_count"] == launch_number
        assert case["terminal_attempt_count"] == 0
        assert case["unfinalized_launch_count"] == launch_number
        assert case["latest_launch_number"] == launch_number
        assert case["elapsed_budget"] == {
            "source_requests": 0,
            "variants": 3 * launch_number,
            "wall_seconds": launch_number,
        }
        if launch_number < 3:
            resumed = _invoke("resume", project_id, "--acknowledge-orphaned-process")
            assert resumed["execution_state"] == "queued"

    denied = runner.invoke(app, ["research", "run", "pilot", project_id, "--json"])
    assert denied.exit_code != 0
    assert "revision or disposition is required" in denied.output
    denied_resume = runner.invoke(
        app,
        [
            "research",
            "resume",
            project_id,
            "--acknowledge-orphaned-process",
            "--json",
        ],
    )
    assert denied_resume.exit_code != 0
    assert "retry limit is exhausted" in denied_resume.output

    database = sqlite3.connect(tmp_path / "control" / "workstation.sqlite3")
    assert database.execute("SELECT COUNT(*) FROM research_launch_reservations").fetchone() == (3,)
    assert database.execute("SELECT COUNT(*) FROM research_launch_attempt_links").fetchone() == (0,)
    database.close()

    _invoke("cancel", project_id, "--reason", "Stop after the exhausted crash budget.")
    _invoke(
        "decide",
        project_id,
        "--outcome",
        "INVALID",
        "--disposition",
        "park",
        "--actor",
        "owner",
        "--reason",
        "Three hard crashes exhausted the durable launch budget.",
    )
    packet = _invoke("report", project_id)
    layers = cast(dict[str, object], packet["layers"])
    appendix = cast(dict[str, object], layers["technical_appendix"])
    assert len(cast(list[object], appendix["launch_reservation_ledger"])) == 3
    assert appendix["launch_attempt_link_ledger"] == []
    budget_ledger = cast(list[dict[str, object]], appendix["budget_ledger"])
    assert budget_ledger[0]["used"] == {
        "source_requests": 0,
        "variants": 9,
        "wall_seconds": 3,
    }


def test_completed_pilot_is_adopted_after_crash_without_duplicate_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "Synthetic double bottom crash-recovery fixture")
    project = cast(dict[str, object], captured["project"])
    project_id = str(project["project_id"])
    store = ControlStore(tmp_path)
    source = store.create_research_source(
        project_id,
        title="Synthetic recovery protocol",
        locator="owner:synthetic-recovery",
        provider="owner",
        access_mode="owner_provided",
    )
    pack = store.create_research_source_pack(
        project_id,
        source_ids=[str(source["source_id"])],
    )
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
        "Approve the deterministic crash-recovery fixture.",
    )

    original_transition = ControlStore.transition_research_execution
    crashed = False

    def crash_after_attempt(
        self: ControlStore, *args: object, **kwargs: object
    ) -> dict[str, object]:
        nonlocal crashed
        if kwargs.get("to_state") == "idle" and not crashed:
            crashed = True
            raise DataError("simulated process loss after attempt insertion")
        return original_transition(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(ControlStore, "transition_research_execution", crash_after_attempt)
    interrupted = runner.invoke(app, ["research", "run", "pilot", project_id, "--json"])
    assert interrupted.exit_code != 0
    assert "simulated process loss" in interrupted.output
    monkeypatch.setattr(ControlStore, "transition_research_execution", original_transition)

    stranded = _invoke("status", project_id)
    assert stranded["execution_state"] == "running"
    assert stranded["attempt_count"] == 1
    run_id = stranded["latest_run_id"]
    unsafe_resume = runner.invoke(app, ["research", "resume", project_id, "--json"])
    assert unsafe_resume.exit_code != 0
    assert _invoke("status", project_id)["execution_state"] == "running"
    resumed = _invoke("resume", project_id, "--acknowledge-orphaned-process")
    assert resumed["execution_state"] == "queued"

    recovered = _invoke("run", "pilot", project_id)
    recovered_case = cast(dict[str, object], recovered["case"])
    assert recovered_case["phase"] == "research_decision"
    assert recovered_case["responsibility"] == "owner"
    assert recovered_case["next_action"] == (
        "Owner records INCONCLUSIVE with revise, park, or reject; empirical D1 is unavailable "
        "in Gate 1."
    )
    assert recovered_case["attempt_count"] == 1
    assert recovered_case["latest_run_id"] == run_id


def test_legacy_compare_still_ranks_engine_strategies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=400)

    payload = _invoke("compare", "SPY")

    assert payload["symbol"] == "SPY"
    assert payload["n_bars"] == 400
    ranked = payload["ranked"]
    assert isinstance(ranked, list)
    assert len(ranked) == 4
    returns = [row["total_return"] for row in ranked if row["total_return"] is not None]
    assert returns == sorted(returns, reverse=True)


def test_legacy_compare_subset_and_missing_data_behavior_remain_compatible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=400)
    subset = runner.invoke(
        app,
        ["research", "compare", "SPY", "--strategies", "ma_crossover"],
    )
    assert subset.exit_code == 0
    assert "ma_crossover" in subset.stdout

    missing = runner.invoke(app, ["research", "compare", "NOPE", "--json"])
    assert missing.exit_code != 0


def test_research_list_projects_bounded_backlog_rows_newest_activity_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    first = _invoke("capture", "Gold rallies after triple witching expiries", "--name", "Gold")
    second = _invoke("capture", "SPY drifts upward into month-end rebalancing", "--name", "SPY")
    first_case = cast(dict[str, object], first["case"])
    second_case = cast(dict[str, object], second["case"])
    first_id = str(cast(dict[str, object], first["project"])["project_id"])
    second_id = str(cast(dict[str, object], second["project"])["project_id"])
    assert first_case["phase"] == "triage" and second_case["phase"] == "triage"

    page = _invoke("list")
    assert set(page) == {"items", "limit", "offset", "has_more"}
    assert page["limit"] == 50 and page["offset"] == 0 and page["has_more"] is False
    items = page["items"]
    assert isinstance(items, list) and len(items) == 2
    row = cast(dict[str, object], items[0])
    assert set(row) == {
        "case_id",
        "title",
        "original_idea",
        "phase",
        "execution_state",
        "outcome",
        "disposition",
        "next_action",
        "responsibility",
        "latest_finding",
        "blocker",
        "recovery_action",
        "completed_milestones",
        "total_milestones",
        "owner_pinned",
        "priority",
        "budget",
        "updated_at",
    }
    # Newest research activity first: the second capture leads.
    assert [cast(dict[str, object], item)["case_id"] for item in items] == [second_id, first_id]
    assert row["title"] == "SPY"
    assert row["original_idea"] == "SPY drifts upward into month-end rebalancing"
    assert row["phase"] == "triage"
    assert row["execution_state"] == "idle"
    assert row["outcome"] is None and row["disposition"] is None
    assert row["responsibility"] == "owner"
    assert (
        row["recovery_action"]
        == "Answer the single bounded question batch; Codex handles technical defaults."
    )
    assert row["completed_milestones"] == 2  # captured + triage phase events
    assert row["total_milestones"] == 9  # the nine research phases
    # The advisory priority rubric is not yet scored; the projection says so honestly.
    assert row["owner_pinned"] is False
    assert row["priority"] == {
        "falsifiability": 0,
        "data_readiness": 0,
        "novelty": 0,
        "information_gain_per_cost": 0,
    }
    budget = cast(dict[str, object], row["budget"])
    assert set(budget) == {"approved_units", "consumed_units", "unit"}
    assert budget["unit"] == "minutes"
    assert isinstance(row["updated_at"], str) and row["updated_at"]

    bounded = _invoke("list", "--limit", "1")
    assert bounded["has_more"] is True
    assert len(cast(list[object], bounded["items"])) == 1
    offset_page = _invoke("list", "--limit", "1", "--offset", "1")
    assert [
        cast(dict[str, object], item)["case_id"]
        for item in cast(list[object], offset_page["items"])
    ] == [first_id]

    rejected = runner.invoke(app, ["research", "list", "--limit", "0", "--json"])
    assert rejected.exit_code != 0


def test_context_packets_notes_protocols_and_brief_cli_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "SPY drifts upward into month-end rebalancing")
    project_id = str(cast(dict[str, object], captured["project"])["project_id"])

    protocols = _invoke("protocols", "list")
    entries = cast(list[dict[str, object]], protocols["protocols"])
    assert len(entries) == 13
    assert entries[0]["id"] == "new-idea-intake"
    shown = _invoke("protocols", "show", "new-idea-intake")
    assert isinstance(shown["content"], str) and "no trading rules" in str(shown["purpose"])

    built = _invoke(
        "context",
        "build",
        project_id,
        "--kind",
        "research_case",
        "--protocol",
        "new-idea-intake",
    )
    packet_id = str(built["packet_id"])
    assert packet_id.startswith("cp_")
    assert built["protocol_id"] == "new-idea-intake"
    assert str(built["protocol_content_hash"]) == str(entries[0]["sha256"])
    payload = cast(dict[str, object], built["payload"])
    assert payload["packet_kind"] == "research_case"

    listed = _invoke("context", "list", project_id)
    assert [row["packet_id"] for row in cast(list[dict[str, object]], listed["items"])] == [
        packet_id
    ]
    shown_packet = _invoke("context", "show", packet_id)
    assert shown_packet["payload"] == payload

    note = _invoke(
        "note",
        "add",
        project_id,
        "--kind",
        "critique",
        "--body",
        "The volatility-regime confounder is not yet matched.",
        "--author",
        "codex",
        "--author-kind",
        "agent",
        "--packet",
        packet_id,
    )
    assert str(note["note_id"]).startswith("rn_")
    notes = _invoke("note", "list", project_id)
    assert [row["note_id"] for row in cast(list[dict[str, object]], notes["items"])] == [
        note["note_id"]
    ]

    brief = _invoke("brief", project_id)
    assert brief["brief_schema"] == "ResearchBriefV1"
    assert str(brief["packet_id"]).startswith("cp_")
    changes = cast(dict[str, object], brief["changes"])
    assert set(changes) == {"phase_events", "execution_events", "attempts", "decisions"}


def test_new_research_commands_report_human_fallbacks_and_fail_loud_on_unknown_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = _invoke("capture", "Gold rallies after triple witching expiries")
    project_id = str(cast(dict[str, object], captured["project"])["project_id"])

    listing = runner.invoke(app, ["research", "list"])
    assert listing.exit_code == 0 and project_id in listing.output
    hub = runner.invoke(app, ["research", "evidence-hub", project_id])
    assert hub.exit_code == 0 and "evidence hub sections" in hub.output
    empty_context = runner.invoke(app, ["research", "context", "list", project_id])
    assert empty_context.exit_code == 0 and "no packets recorded" in empty_context.output
    empty_notes = runner.invoke(app, ["research", "note", "list", project_id])
    assert empty_notes.exit_code == 0 and "no notes recorded" in empty_notes.output
    protocols_text = runner.invoke(app, ["research", "protocols", "list"])
    assert protocols_text.exit_code == 0 and "new-idea-intake" in protocols_text.output
    protocol_text = runner.invoke(app, ["research", "protocols", "show", "research-critic"])
    assert protocol_text.exit_code == 0 and "Research Critic" in protocol_text.output
    built = runner.invoke(app, ["research", "context", "build", project_id, "--kind", "validation"])
    assert built.exit_code == 0 and "recorded packet cp_" in built.output
    noted = runner.invoke(
        app,
        [
            "research",
            "note",
            "add",
            project_id,
            "--kind",
            "synthesis",
            "--body",
            "Established: nothing yet.",
        ],
    )
    assert noted.exit_code == 0 and "recorded note rn_" in noted.output
    briefed = runner.invoke(app, ["research", "brief", project_id])
    assert briefed.exit_code == 0 and "brief recorded as cp_" in briefed.output
    shown = runner.invoke(app, ["research", "context", "list", project_id])
    assert shown.exit_code == 0 and "validation" in shown.output

    unknown = "00000000-0000-4000-8000-000000000000"
    for args in (
        ["research", "evidence-hub", unknown, "--json"],
        ["research", "context", "build", unknown, "--kind", "research_case", "--json"],
        ["research", "context", "show", "cp_" + "9" * 64, "--json"],
        ["research", "context", "list", unknown, "--json"],
        ["research", "note", "add", unknown, "--kind", "critique", "--body", "x", "--json"],
        ["research", "note", "list", unknown, "--json"],
        ["research", "protocols", "show", "unknown-protocol", "--json"],
        ["research", "brief", unknown, "--json"],
        ["research", "status", unknown, "--json"],
    ):
        rejected = runner.invoke(app, args)
        assert rejected.exit_code != 0, args
