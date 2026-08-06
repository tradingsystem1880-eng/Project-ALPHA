"""CLI-owned ResearchGatePacket projection over the public control-store seam."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import cast

import pytest
from typer.testing import CliRunner

import alpha_cli.control_store as control_store_module
from alpha_cli import research_cmds
from alpha_cli.control_store import ControlStore
from alpha_cli.main import app
from alpha_cli.research_gate_packet import research_report_projection
from tests.unit.test_research_control_store import PROJECT_ID, START, _approved_contracts, _project
from tests.unit.test_research_gate_packet import _inputs


class _FakeStore:
    def __init__(self, summary: dict[str, object], inputs: dict[str, object]) -> None:
        self.summary = summary
        self.inputs = inputs
        self.packet_reads = 0

    def research_case_summary(self, project_id: str) -> dict[str, object]:
        assert project_id == "project-1"
        return self.summary

    def research_gate_packet_inputs(
        self, project_id: str, *, ledger_limit: int = 10_000
    ) -> dict[str, object]:
        assert project_id == "project-1"
        assert ledger_limit == 10_000
        self.packet_reads += 1
        return self.inputs


def test_active_case_preserves_progress_report_and_does_not_read_terminal_inputs() -> None:
    summary: dict[str, object] = {
        "project_id": "project-1",
        "phase": "deep_research",
        "execution_state": "idle",
        "next_action": "Keep D2 sealed.",
    }
    store = _FakeStore(summary, _inputs())
    row = research_report_projection(store, "project-1")
    assert row == {
        "report_schema": "ResearchProgressReportV1",
        "terminal": False,
        "case": summary,
        "warning": "This is a progress report, not a terminal ResearchGatePacket.",
    }
    assert store.packet_reads == 0


def test_closed_case_uses_only_public_packet_inputs_and_returns_terminal_packet() -> None:
    summary: dict[str, object] = {
        "project_id": "project-1",
        "phase": "closed",
        "execution_state": "idle",
        "next_action": "Enter strategy development through the governed link.",
    }
    store = _FakeStore(summary, _inputs())
    row = research_report_projection(store, "project-1")
    assert row["report_schema"] == "ResearchGatePacketV1"
    assert row["terminal"] is True
    assert str(row["packet_id"]).startswith("rgp_")
    assert store.packet_reads == 1
    layers = cast(dict[str, object], row["layers"])
    assert "technical_appendix" in layers


def test_alpha_research_report_emits_terminal_packet_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary: dict[str, object] = {
        "project_id": "project-1",
        "phase": "closed",
        "execution_state": "idle",
        "next_action": "Enter strategy development through the governed link.",
    }
    store = _FakeStore(summary, _inputs())
    monkeypatch.setattr(research_cmds, "_store", lambda: store)

    result = CliRunner().invoke(
        app,
        ["research", "report", "project-1", "--json"],
    )
    assert result.exit_code == 0, result.output
    row = json.loads(result.output)
    assert row["report_schema"] == "ResearchGatePacketV1"
    assert row["terminal"] is True
    assert row["packet_id"] == f"rgp_{row['packet_hash']}"


def test_projection_walks_the_public_control_store_packet_seam(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(control_store_module, "_UNRELEASED_EMPIRICAL_RESEARCH_ENABLED", True)
    store = ControlStore(tmp_path)
    _project(store)
    _, confirmation_id = _approved_contracts(
        store,
        outcome="INCONCLUSIVE",
        disposition="park",
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="closed",
        contract_id=confirmation_id,
        actor="codex",
        reason="Owner decision recorded; close the case.",
        next_action="Enter strategy development through the governed linkage.",
        responsibility="owner",
        at=START + timedelta(minutes=16),
    )

    row = research_report_projection(store, PROJECT_ID)
    assert row["report_schema"] == "ResearchGatePacketV1"
    assert row["terminal"] is True
    assert row["scientific_outcome"] == "INCONCLUSIVE"
    assert row["recommended_disposition"] == "park"
    layers = cast(dict[str, object], row["layers"])
    guided = cast(dict[str, object], layers["guided_evidence"])
    assert cast(dict[str, object], guided["primary_result"])["status"] == "TESTED"
    assert guided["confirmation_classification"] == "INCONCLUSIVE"
