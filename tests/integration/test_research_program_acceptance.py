"""Program-level acceptance for the research-first workstation (R6i; 2026-08-07 spec §17).

Composite end-to-end stories through the public CLI. Per-phase behaviour is proven in the
dedicated suites; this module proves the program-level claims that only hold when every
phase composes losslessly:

- Golden path: one raw sentence becomes a case with its wording preserved, renders an honest
  all-``not_tested`` scorecard and empty Evidence Hub, runs the governed empirical D1 and
  one-shot sealed D2 lanes, closes ``SUPPORTED`` / ``advance_to_strategy``, and the recorded
  promotion dossier reaches the linked strategy version's AgentBrief byte-identically.
- ``SUPPORTED`` never implies promotion: a non-advancing owner disposition closes with an
  honest terminal packet, records no promotion dossier, and keeps the gate locked.
- A parked pre-D2 case closes honestly (``NOT_TESTED`` primary result, no manufactured
  support) and cannot claim ``SUPPORTED`` or advance.

The remaining §17 bullets are proven where they live: agent-authority negatives in
``test_research_mcp.py`` (62-tool pin, no approve/decide/D2 verbs) and
``test_web_api_research.py`` (Gate-1-only POST pin); kill-and-resume in the per-phase
crash/recovery suites; planted-pattern/confounder/null fixtures in the R5 acceptance tests;
override visibility in ``test_research_gate_watermark_cli.py`` plus the Playwright e2e; and
byte-identical Codex packet history in the R2 context-packet suites.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from tests.integration.test_research_cli import (
    _approve_confirmation,
    _approved_empirical_daily_project,
    _confirmation_ready_project,
    _daily_draft_args,
    _invoke,
    _register_daily_dataset,
    _varied_daily_lows,
)

runner = CliRunner()

_RAW_IDEA = "SPY bounces after double bottoms on the daily chart"

# Every checklist/scorecard status the program may render. Typed enumerations only — a
# numeric aggregate anywhere in the decision plane is a program-acceptance failure.
_CHECKLIST_STATUSES = frozenset(
    {
        "SUPPORTED",
        "CONTRADICTED",
        "INCONCLUSIVE",
        "CLEARS_HURDLE",
        "BELOW_MINIMUM",
        "PASSED",
        "FAILED",
        "STABLE",
        "UNSTABLE",
        "TESTED",
        "NOT_TESTED",
    }
)


def _project_cli(*args: str) -> dict[str, object]:
    result = runner.invoke(app, ["project", *args, "--json"])
    assert result.exit_code == 0, result.output
    value: object = json.loads(result.output)
    assert isinstance(value, dict)
    return value


def _scorecard_states(scorecard: dict[str, object]) -> dict[str, str]:
    dimensions = cast(list[dict[str, object]], scorecard["dimensions"])
    return {str(entry["dimension_id"]): str(entry["state"]) for entry in dimensions}


def _checklist_questions(view: dict[str, object]) -> list[dict[str, object]]:
    checklist = cast(dict[str, object], view["checklist"])
    assert checklist["checklist_schema"] == "ResearchEdgeChecklistV1"
    questions = cast(list[dict[str, object]], checklist["questions"])
    assert len(questions) == 14
    for question in questions:
        assert str(question["status"]) in _CHECKLIST_STATUSES, question
    return questions


def _promotion_packets(project_id: str) -> list[dict[str, object]]:
    listed = _invoke("context", "list", project_id)
    items = cast(list[dict[str, object]], listed["items"])
    return [row for row in items if row["packet_kind"] == "strategy_promotion"]


def _version_args(project_id: str, *extra: str) -> list[str]:
    return [
        "version",
        project_id,
        "--strategy",
        "double_bottom",
        "--source-fingerprint",
        "git:acceptance0",
        "--definition-json",
        '{"detector": "causal-double-bottom-v1"}',
        "--parameter-space-json",
        '{"tolerance": [0.005, 0.01]}',
        *extra,
    ]


def test_program_golden_path_reaches_the_strategy_brief_losslessly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§17: capture → D1 → one-shot D2 → SUPPORTED → promotion → AgentBrief, end to end."""
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    ref_id = _register_daily_dataset(tmp_path, "SPY", _varied_daily_lows())

    # One raw sentence becomes a governed case: wording preserved, at most one bounded
    # three-question clarification batch, and no trading-rule inputs anywhere.
    captured = _invoke("capture", _RAW_IDEA)
    project_id = str(cast(dict[str, object], captured["project"])["project_id"])
    intake_payload = cast(
        dict[str, object], cast(dict[str, object], captured["contract"])["payload"]
    )
    assert intake_payload["raw_idea"] == _RAW_IDEA
    assert len(cast(list[object], intake_payload["blocking_questions"])) <= 3

    # The fresh case is honest: every evidence dimension not_tested, the recommendation is
    # an enumerated sentence (never a numeric aggregate), and the Evidence Hub renders all
    # eleven sections with empty/NOT_TESTED states.
    status = _invoke("status", project_id)
    states = _scorecard_states(cast(dict[str, object], status["scorecard"]))
    for dimension_id in (
        "data_quality",
        "sample_adequacy",
        "effect_existence",
        "effect_size",
        "temporal_stability",
        "cross_asset_stability",
        "regime_robustness",
        "falsification",
        "mechanism",
    ):
        assert states[dimension_id] == "not_tested", dimension_id
    recommendation = cast(
        dict[str, object], cast(dict[str, object], status["scorecard"])["recommendation"]
    )
    assert recommendation["value"] == "MORE RESEARCH REQUIRED"
    hub = _invoke("evidence-hub", project_id)
    assert hub["hub_schema"] == "ResearchEvidenceHubV1"
    sections = cast(dict[str, object], hub["sections"])
    assert set(sections) == {
        "overview",
        "data",
        "literature",
        "mechanism",
        "exploration",
        "experiments",
        "evidence_for",
        "evidence_against",
        "falsification",
        "robustness",
        "decision",
    }
    assert cast(dict[str, object], sections["overview"])["original_idea"] == _RAW_IDEA
    assert cast(dict[str, object], sections["exploration"])["status"] == "NOT_TESTED"
    assert cast(dict[str, object], sections["evidence_for"])["findings"] == []
    assert cast(dict[str, object], sections["evidence_against"])["findings"] == []

    # Sources → frozen pack → approved empirical exploration → governed D1 → frozen D2.
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
    pack = _invoke("sources", "freeze", project_id, "--source-id", str(source["source_id"]))
    drafted = _invoke(*_daily_draft_args(project_id, str(pack["pack_id"])), "--dataset", ref_id)
    exploration_id = str(cast(dict[str, object], drafted["contract"])["contract_id"])
    _invoke(
        "approve",
        "exploration",
        project_id,
        exploration_id,
        "--actor",
        "owner",
        "--reason",
        "The registered daily dataset and bounded plan suit empirical D1 exploration.",
    )
    pilot = _invoke("run", "pilot", project_id)
    assert cast(dict[str, object], pilot["case"])["phase"] == "deep_research"
    _invoke("run", "deep", project_id)
    confirmation = _invoke("draft-confirmation", project_id)
    confirmation_id = str(cast(dict[str, object], confirmation["contract"])["contract_id"])
    _approve_confirmation(project_id, confirmation_id)
    confirm = _invoke("run", "confirm", project_id)
    manifest = cast(dict[str, object], confirm["manifest"])
    assert manifest["watermark"] == "REGISTERED CONFIRMATORY"
    assert manifest["eligible_for_holdout_or_execution"] is False
    case = cast(dict[str, object], confirm["case"])
    assert case["phase"] == "research_decision"
    assert case["d2_state"] == "consumed"

    # The owner decision view is typed all the way down: fourteen bound questions, no
    # numeric aggregate, and no terminal packet before the case closes.
    view = _invoke("decision-view", project_id)
    assert view["gate_packet"] is None
    questions = _checklist_questions(view)
    assert str(questions[0]["question_id"]) == "effect_exists"
    # Open cases answer from live admitted evidence: the primary is TESTED, but the
    # SUPPORTED classification binds only once the case closes with its terminal packet.
    assert str(questions[0]["status"]) == "TESTED"

    decided = _invoke(
        "decide",
        project_id,
        "--outcome",
        "SUPPORTED",
        "--disposition",
        "advance_to_strategy",
        "--actor",
        "owner",
        "--reason",
        "The mechanically confirmed effect advances to strategy work.",
    )
    assert cast(dict[str, object], decided["decision"])["outcome"] == "SUPPORTED"
    assert cast(dict[str, object], decided["case"])["phase"] == "closed"

    # The closed case has its deterministic terminal packet, the gate reads passed, and
    # exactly one lossless promotion dossier exists.
    report = _invoke("report", project_id)
    assert report["report_schema"] == "ResearchGatePacketV1"
    assert report["scientific_outcome"] == "SUPPORTED"
    closed_view = _invoke("decision-view", project_id)
    gate_packet = cast(dict[str, object], closed_view["gate_packet"])
    assert gate_packet["packet_id"] == report["packet_id"]
    closed_questions = _checklist_questions(closed_view)
    assert str(closed_questions[0]["status"]) == "SUPPORTED"
    history = cast(list[dict[str, object]], closed_view["decision_history"])
    assert [row["outcome"] for row in history] == ["SUPPORTED"]
    shown = _project_cli("show", project_id)
    assert shown["research_gate_state"] == "passed"
    promotions = _promotion_packets(project_id)
    assert len(promotions) == 1
    promotion_id = str(promotions[0]["packet_id"])
    assert promotion_id.startswith("cp_")

    # Byte-identical retrieval: the recorded dossier returns the same bytes every read.
    first = runner.invoke(app, ["research", "context", "show", promotion_id, "--json"])
    second = runner.invoke(app, ["research", "context", "show", promotion_id, "--json"])
    assert first.exit_code == 0 and second.exit_code == 0
    assert first.output == second.output
    packet = cast(dict[str, object], json.loads(first.output))
    payload = cast(dict[str, object], packet["payload"])
    assert payload, "promotion dossier payload must not be empty"

    # Even a passed gate refuses an unlinked strategy version: promoted work must carry
    # its research inheritance.
    unlinked = runner.invoke(app, ["project", *_version_args(project_id), "--json"])
    assert unlinked.exit_code != 0
    assert "research_contract_id" in unlinked.output

    version = _project_cli(*_version_args(project_id, "--research-contract-id", confirmation_id))
    assert str(version["version_id"]).startswith("sv_")

    # Lossless inheritance: the strategy AgentBrief embeds the exact recorded dossier and
    # terminal-packet identity — never a recomputed or paraphrased copy.
    brief = _project_cli("agent-brief", project_id)
    promotion_ref = cast(dict[str, object], brief["research_promotion"])
    assert promotion_ref["packet_id"] == promotion_id
    assert promotion_ref["contract_id"] == confirmation_id
    assert promotion_ref["gate_packet_id"] == report["packet_id"]
    assert promotion_ref["gate_packet_hash"] == report["packet_hash"]


def test_supported_outcome_with_a_non_advancing_disposition_never_promotes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§17: promotion requires SUPPORTED *and* the owner's advance disposition."""
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    project_id, contract_id, _ = _confirmation_ready_project(tmp_path)
    _approve_confirmation(project_id, contract_id)
    _invoke("run", "confirm", project_id)

    decided = _invoke(
        "decide",
        project_id,
        "--outcome",
        "SUPPORTED",
        "--disposition",
        "reject",
        "--actor",
        "owner",
        "--reason",
        "Real but too small to pursue: the owner rejects despite mechanical support.",
    )
    assert cast(dict[str, object], decided["case"])["phase"] == "closed"

    # The closed case still gets its honest terminal packet…
    report = _invoke("report", project_id)
    assert report["report_schema"] == "ResearchGatePacketV1"
    assert report["scientific_outcome"] == "SUPPORTED"
    # …but nothing promotes: no dossier, a still-locked gate, and no version path.
    assert _promotion_packets(project_id) == []
    assert _project_cli("show", project_id)["research_gate_state"] == "open"
    linked = runner.invoke(
        app,
        ["project", *_version_args(project_id, "--research-contract-id", contract_id), "--json"],
    )
    assert linked.exit_code != 0
    assert "advance_to_strategy" in linked.output
    unlinked = runner.invoke(app, ["project", *_version_args(project_id), "--json"])
    assert unlinked.exit_code != 0
    assert "research_contract_id" in unlinked.output


def test_parked_pre_d2_case_closes_honestly_and_cannot_claim_support(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§17: honest termination — a pre-D2 park never manufactures empirical support."""
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    project_id, _ = _approved_empirical_daily_project(tmp_path, lows=_varied_daily_lows())

    # Without consumed D2 the owner cannot record SUPPORTED, let alone advance.
    premature = runner.invoke(
        app,
        [
            "research",
            "decide",
            project_id,
            "--outcome",
            "SUPPORTED",
            "--disposition",
            "advance_to_strategy",
            "--actor",
            "owner",
            "--reason",
            "A premature advance claim must fail before any confirmation ran.",
            "--json",
        ],
    )
    assert premature.exit_code != 0
    assert "INCONCLUSIVE or INVALID" in premature.output

    parked = _invoke(
        "decide",
        project_id,
        "--outcome",
        "INCONCLUSIVE",
        "--disposition",
        "park",
        "--actor",
        "owner",
        "--reason",
        "Parked before confirmation: the discovery signal did not justify a sealed read.",
    )
    assert cast(dict[str, object], parked["case"])["phase"] == "closed"

    report = _invoke("report", project_id)
    assert report["report_schema"] == "ResearchGatePacketV1"
    assert report["scientific_outcome"] == "INCONCLUSIVE"
    view = _invoke("decision-view", project_id)
    questions = _checklist_questions(view)
    effect = next(q for q in questions if q["question_id"] == "effect_exists")
    assert str(effect["status"]) == "NOT_TESTED"

    assert _promotion_packets(project_id) == []
    assert _project_cli("show", project_id)["research_gate_state"] == "open"
