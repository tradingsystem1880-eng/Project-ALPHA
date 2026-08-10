"""Bounded research REST projections over real offline ``alpha`` subprocesses."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_cli.control_store import ControlStore
from alpha_core.config import AlphaSettings
from alpha_research import build_research_gate_packet
from alpha_web import _research
from alpha_web.app import create_app
from tests.fixtures.cli_fixtures import seed_store
from tests.unit.test_research_gate_packet import _inputs_with_evidence


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    return TestClient(create_app())


def test_compare_endpoint_single_strategy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_store(tmp_path, symbol="SPY", n=400)
    resp = _client(tmp_path, monkeypatch).get(
        "/api/research/compare", params={"symbol": "SPY", "strategies": "ma_crossover"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "SPY"
    assert body["ranked"][0]["strategy"] == "ma_crossover"


def test_compare_no_bars_is_422(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    resp = _client(tmp_path, monkeypatch).get("/api/research/compare", params={"symbol": "NOPE"})
    assert resp.status_code == 422


def test_research_case_capture_propose_status_report_and_pilot_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    captured_response = client.post(
        "/api/research/cases",
        json={"idea": "S&P500 bounces after double bottoms on the 4h time frame"},
    )
    assert captured_response.status_code == 200, captured_response.text
    captured = captured_response.json()
    project_id = captured["project"]["project_id"]
    assert captured["case"]["phase"] == "triage"
    assert captured["case"]["responsibility"] == "owner"
    assert len(captured["contract"]["payload"]["blocking_questions"]) == 3
    assert captured["case"]["d2_state"] == "sealed"

    store = ControlStore(AlphaSettings().data_dir)
    source = store.create_research_source(
        project_id,
        title="Technical trading revisited",
        locator="doi:10.0000/example",
        provider="crossref",
        access_mode="metadata_only",
    )
    pack = store.create_research_source_pack(
        project_id,
        source_ids=[str(source["source_id"])],
        definition={"screened": True},
    )
    proposal_response = client.post(
        f"/api/research/cases/{project_id}/proposal",
        json={
            "source_pack_id": pack["pack_id"],
            "answers": {
                "chart_construction": "spy_rth_60m_four_hour_window",
                "event_availability": "second_trough_confirmable",
                "primary_outcome": "four_trading_hour_return_25bp",
            },
        },
    )
    assert proposal_response.status_code == 200, proposal_response.text
    proposal = proposal_response.json()
    contract_id = proposal["contract"]["contract_id"]
    assert proposal["case"]["phase"] == "exploration_review"
    assert proposal["case"]["responsibility"] == "owner"

    shown = client.get(f"/api/research/cases/{project_id}")
    status = client.get(f"/api/research/cases/{project_id}/status")
    report = client.get(f"/api/research/cases/{project_id}/report")
    assert shown.status_code == status.status_code == report.status_code == 200
    assert shown.json() == status.json()
    assert shown.json()["active_contract_id"] == contract_id
    assert report.json()["report_schema"] == "ResearchProgressReportV1"
    assert report.json()["terminal"] is False
    assert "ResearchGatePacket" in report.json()["warning"]

    store.review_research_contract(
        project_id,
        contract_id,
        scope="exploration",
        decision="approve",
        actor="owner",
        actor_kind="human",
        reason="exact exploration contract approved for the synthetic pilot",
    )
    store.transition_research_phase(
        project_id,
        to_phase="pilot",
        contract_id=contract_id,
        actor="owner",
        reason="owner approved the exact exploration contract",
        next_action="Codex runs the deterministic D0 synthetic pilot.",
        responsibility="codex",
    )
    launched_response = client.post(
        f"/api/research/cases/{project_id}/launch", json={"stage": "pilot"}
    )
    assert launched_response.status_code == 200, launched_response.text
    launched = launched_response.json()
    assert launched["manifest"]["evidence_zone"] == "D0"
    assert launched["attempt"]["kind"] == "d0-synthetic-pilot"
    assert launched["case"]["phase"] == "deep_research"
    assert launched["case"]["responsibility"] == "codex"
    assert launched["case"]["next_action"] == (
        "Launch `alpha research run deep` to execute the frozen analysis plan on D1."
    )
    assert launched["case"]["d2_state"] == "sealed"


def test_research_rest_surface_cannot_approve_decide_reveal_or_confirm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    captured = client.post(
        "/api/research/cases", json={"idea": "A generic synthetic research idea"}
    )
    assert captured.status_code == 200, captured.text
    project_id = captured.json()["project"]["project_id"]

    invalid_launch = client.post(
        f"/api/research/cases/{project_id}/launch", json={"stage": "confirm"}
    )
    extra_authority = client.post(
        "/api/research/cases",
        json={"idea": "Another idea", "approve": True},
    )
    assert invalid_launch.status_code == 422
    assert extra_authority.status_code == 422

    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    paths = set(openapi.json()["paths"])
    forbidden_fragments = ("approve", "decide", "reveal", "python", "paper", "order")
    research_case_paths = {path for path in paths if path.startswith("/api/research/cases")}
    assert not any(
        fragment in path for path in research_case_paths for fragment in forbidden_fragments
    )


def test_research_report_route_validates_terminal_gate_packet_union(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    packet_inputs, _ = _inputs_with_evidence()
    packet = build_research_gate_packet(packet_inputs).to_dict()
    monkeypatch.setattr(_research, "report", lambda *_args, **_kwargs: packet)

    response = _client(tmp_path, monkeypatch).get("/api/research/cases/project-1/report")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["report_schema"] == "ResearchGatePacketV1"
    assert body["terminal"] is True
    assert body["authority"]["places_orders"] is False
    assert body["layers"]["guided_evidence"]["confirmation_classification"] == "SUPPORTED"


def test_research_proposal_requires_exact_material_answer_vocabulary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    captured = client.post(
        "/api/research/cases", json={"idea": "A generic synthetic research idea"}
    )
    project_id = captured.json()["project"]["project_id"]

    invalid = client.post(
        f"/api/research/cases/{project_id}/proposal",
        json={
            "source_pack_id": "sp_deadbeef",
            "answers": {
                "chart_construction": "mixed_240m_150m_bars",
                "event_availability": "second_trough_confirmable",
                "primary_outcome": "four_trading_hour_return_25bp",
                "alpha": "0.50",
            },
        },
    )
    assert invalid.status_code == 422

    canonical = {
        "chart_construction": "spy_rth_60m_four_hour_window",
        "event_availability": "second_trough_confirmable",
        "primary_outcome": "four_trading_hour_return_25bp",
    }
    for field, unavailable in (
        ("chart_construction", "spy_extended_fixed_4h"),
        ("chart_construction", "synthetic_only"),
        ("event_availability", "neckline_breakout_confirmed"),
        ("primary_outcome", "next_regular_session_return_50bp"),
        ("primary_outcome", "owner_specified_economic_hurdle"),
    ):
        answers = {**canonical, field: unavailable}
        unavailable_response = client.post(
            f"/api/research/cases/{project_id}/proposal",
            json={"source_pack_id": "sp_deadbeef", "answers": answers},
        )
        assert unavailable_response.status_code == 422


def test_unknown_research_case_reads_are_404(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    project_id = "00000000-0000-4000-8000-000000000000"
    assert client.get(f"/api/research/cases/{project_id}").status_code == 404
    assert client.get(f"/api/research/cases/{project_id}/status").status_code == 404
    assert client.get(f"/api/research/cases/{project_id}/report").status_code == 404


def test_option_shaped_project_id_maps_to_a_typed_error_not_a_500(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--help`` makes the CLI print help with exit 0; non-JSON output must not crash the route."""
    resp = _client(tmp_path, monkeypatch).get("/api/research/cases/--help")
    assert resp.status_code == 404
    assert "did not return valid JSON" in resp.json()["detail"]


def test_research_case_list_evidence_hub_and_scorecard_read_plane(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    captured = client.post(
        "/api/research/cases",
        json={"idea": "SPY drifts upward into month-end rebalancing", "name": "Month-end"},
    )
    assert captured.status_code == 200, captured.text
    project_id = captured.json()["project"]["project_id"]

    listed = client.get("/api/research/cases")
    assert listed.status_code == 200, listed.text
    page = listed.json()
    assert page["limit"] == 50 and page["offset"] == 0 and page["has_more"] is False
    assert [row["case_id"] for row in page["items"]] == [project_id]
    row = page["items"][0]
    assert row["title"] == "Month-end"
    assert row["phase"] == "triage"
    assert row["owner_pinned"] is False
    assert row["budget"]["unit"] == "minutes"

    bounded = client.get("/api/research/cases", params={"limit": 1, "offset": 5})
    assert bounded.status_code == 200
    assert bounded.json()["items"] == []
    assert client.get("/api/research/cases", params={"limit": 0}).status_code == 422
    assert client.get("/api/research/cases", params={"limit": 101}).status_code == 422
    assert client.get("/api/research/cases", params={"offset": -1}).status_code == 422

    hub_response = client.get(f"/api/research/cases/{project_id}/evidence-hub")
    assert hub_response.status_code == 200, hub_response.text
    hub = hub_response.json()
    assert hub["hub_schema"] == "ResearchEvidenceHubV1"
    assert hub["project_id"] == project_id
    sections = hub["sections"]
    assert sections["overview"]["hypothesis_card"]["card_schema"] == "HypothesisCardV1"
    assert sections["evidence_for"] == {"findings": []}
    assert sections["evidence_against"] == {"findings": []}
    assert sections["decision"]["packet_id"] is None

    scorecard_response = client.get(f"/api/research/cases/{project_id}/scorecard")
    assert scorecard_response.status_code == 200, scorecard_response.text
    scorecard = scorecard_response.json()
    assert scorecard["scorecard_schema"] == "ResearchReadinessScorecardV1"
    assert len(scorecard["dimensions"]) == 12
    assert scorecard["recommendation"]["value"] == "MORE RESEARCH REQUIRED"

    assert client.get("/api/research/cases/unknown-project/evidence-hub").status_code == 404
    assert client.get("/api/research/cases/unknown-project/scorecard").status_code == 404


def test_research_router_exposes_no_new_mutation_verbs() -> None:
    paths = create_app().openapi()["paths"]
    research_routes: dict[str, set[str]] = {
        path: {method.upper() for method in operations}
        for path, operations in paths.items()
        if path.startswith("/api/research")
    }
    # ADR-0021: the read plane grows, mutation authority does not. Exactly the three
    # bounded Gate-1 POSTs (capture, proposal, pilot launch) may write; everything else
    # on the research router is GET-only.
    mutating = {
        path: methods - {"GET", "HEAD"}
        for path, methods in research_routes.items()
        if methods - {"GET", "HEAD"}
    }
    assert mutating == {
        "/api/research/cases": {"POST"},
        "/api/research/cases/{project_id}/proposal": {"POST"},
        "/api/research/cases/{project_id}/launch": {"POST"},
    }
    read_only_paths = {
        "/api/research/cases/{project_id}/evidence-hub",
        "/api/research/cases/{project_id}/scorecard",
        "/api/research/cases/{project_id}/decision-view",
    }
    assert read_only_paths <= set(research_routes)


def test_research_decision_view_read_plane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    captured = client.post(
        "/api/research/cases",
        json={"idea": "SPY drifts upward into month-end rebalancing", "name": "Month-end"},
    )
    assert captured.status_code == 200, captured.text
    project_id = captured.json()["project"]["project_id"]

    response = client.get(f"/api/research/cases/{project_id}/decision-view")
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["view_schema"] == "ResearchDecisionViewV1"
    assert view["project_id"] == project_id
    assert view["phase"] == "triage"
    # A fresh case has no terminal packet and no recorded owner decisions.
    assert view["gate_packet"] is None
    assert view["decision_history"] == []
    questions = view["checklist"]["questions"]
    assert len(questions) == 14
    assert [entry["number"] for entry in questions] == list(range(1, 15))
    statuses = {entry["question_id"]: entry["status"] for entry in questions}
    assert statuses["effect_exists"] == "NOT_TESTED"
    assert statuses["economic_hurdle"] == "NOT_TESTED"
    assert statuses["residual_uncertainty"] == "TESTED"
    assert len(view["scorecard"]["dimensions"]) == 12
    assert view["scorecard"]["recommendation"]["value"] == "MORE RESEARCH REQUIRED"

    assert client.get("/api/research/cases/unknown-project/decision-view").status_code == 404


def test_codex_read_plane_serves_packets_notes_and_protocols(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    captured = client.post(
        "/api/research/cases",
        json={"idea": "SPY drifts upward into month-end rebalancing"},
    )
    assert captured.status_code == 200, captured.text
    project_id = captured.json()["project"]["project_id"]

    store = ControlStore(AlphaSettings().data_dir)
    packet = store.build_research_context_packet(
        project_id, kind="research_case", created_by="codex"
    )
    packet_id = str(packet["packet_id"])
    store.add_research_note(
        project_id,
        note_kind="critique",
        body="The volatility-regime confounder is not yet matched.",
        author="codex",
        author_kind="agent",
        context_packet_id=packet_id,
    )

    packets = client.get(f"/api/research/cases/{project_id}/context-packets")
    assert packets.status_code == 200, packets.text
    packet_rows = packets.json()["items"]
    assert [row["packet_id"] for row in packet_rows] == [packet_id]

    fetched = client.get(f"/api/research/context-packets/{packet_id}")
    assert fetched.status_code == 200, fetched.text
    # Byte-identical visibility: the served payload equals the recorded payload.
    assert fetched.json()["payload"] == packet["payload"]

    notes = client.get(f"/api/research/cases/{project_id}/notes")
    assert notes.status_code == 200, notes.text
    note_rows = notes.json()["items"]
    assert len(note_rows) == 1
    assert note_rows[0]["author_kind"] == "agent"
    assert note_rows[0]["context_packet_id"] == packet_id

    protocols = client.get("/api/research/protocols")
    assert protocols.status_code == 200, protocols.text
    entries = protocols.json()["protocols"]
    assert len(entries) == 13
    assert entries[0]["id"] == "new-idea-intake"

    assert client.get("/api/research/context-packets/cp_" + "9" * 64).status_code == 404
    assert client.get("/api/research/cases/unknown/context-packets").status_code == 404


def test_dataset_read_plane_serves_registered_refs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    store = ControlStore(AlphaSettings().data_dir)
    ref = store.register_research_dataset(
        dataset_kind="store_slice",
        instrument="AAPL",
        provider="fake",
        start_ts="2020-01-01",
        end_ts="2020-06-01",
        bar_duration_minutes=None,
        origin={"provenance_sha256": "a" * 64},
        registered_by="owner",
    )
    listed = client.get("/api/research/datasets")
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    assert [row["ref_id"] for row in payload["items"]] == [ref["ref_id"]]
    row = payload["items"][0]
    assert row["research_only"] is True
    assert row["latest_audit"] is None
    filtered = client.get("/api/research/datasets", params={"symbol": "SPY"})
    assert filtered.status_code == 200
    assert filtered.json()["items"] == []
    assert client.get("/api/research/datasets", params={"limit": 0}).status_code == 422
