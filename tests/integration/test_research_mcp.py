"""The six research MCP tools remain thin, bounded, and unable to approve or reveal data."""

from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from alpha_cli.control_store import ControlStore
from alpha_core.config import AlphaSettings
from alpha_mcp import server

# The complete bounded MCP authority surface. Adding, removing, or renaming ANY tool must
# consciously update this pin (and the 48-tool documentation claim) — a silently grown
# surface is an authority expansion, not a convenience.
_EXPECTED_MCP_TOOLS = frozenset(
    {
        "advance_experiment_stage",
        "advance_stage_state",
        "backtest_cross_sectional",
        "backtest_portfolio",
        "backtest_run",
        "cancel_development_suite",
        "compare_runs",
        "create_development_job",
        "create_experiment_spec",
        "create_strategy_project",
        "create_strategy_version",
        "data_pull",
        "draft_evidence",
        "forecast_eval",
        "forecast_run",
        "get_agent_brief",
        "get_chart_bundle",
        "get_development_job",
        "get_evidence",
        "get_experiment_spec",
        "get_portfolio_analytics",
        "get_project",
        "get_run",
        "get_strategy_version",
        "launch_development_suite",
        "launch_ml_experiment",
        "link_project_run",
        "list_development_jobs",
        "list_projects",
        "list_runs",
        "list_strategies",
        "optim_grid",
        "plan_development_suite",
        "plan_ml_experiment",
        "propfirm_run",
        "reconcile_development_jobs",
        "record_project_attempt",
        "add_research_note",
        "build_research_context_packet",
        "get_research_brief",
        "get_research_context_packet",
        "get_research_protocol",
        "list_research_protocols",
        "research_capture",
        "research_get",
        "research_launch",
        "research_propose",
        "research_report",
        "research_status",
        "review_evidence",
        "seal_project_holdout",
        "search_asset_evidence",
        "search_evidence",
        "validate",
    }
)


def test_research_mcp_surface_is_pinned_without_owner_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    names = {tool.name for tool in anyio.run(server.mcp.list_tools)}

    assert names == _EXPECTED_MCP_TOOLS
    assert len(names) == 54  # ADR-0022 R2 budget: 48 + 6 Codex-seam tools
    assert {name for name in names if name.startswith("research_")} == {
        "research_capture",
        "research_get",
        "research_propose",
        "research_launch",
        "research_status",
        "research_report",
    }
    # Forever-absent authority (ADR-0022): no approval, decision, or D2 verbs — ever.
    forbidden_markers = ("approve", "decide", "decision", "reveal", "d2", "order", "paper")
    for name in names:
        assert not any(marker in name for marker in forbidden_markers), name


def test_research_mcp_capture_propose_status_and_report_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = server.research_capture("S&P500 bounces after double bottoms on the 4h time frame")
    project_id = captured["project"]["project_id"]
    assert captured["case"]["phase"] == "triage"
    assert len(captured["contract"]["payload"]["blocking_questions"]) == 3

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
    proposed = server.research_propose(
        project_id,
        str(pack["pack_id"]),
        {
            "chart_construction": "spy_rth_60m_four_hour_window",
            "event_availability": "second_trough_confirmable",
            "primary_outcome": "four_trading_hour_return_25bp",
        },
    )

    assert proposed["case"]["phase"] == "exploration_review"
    assert proposed["case"]["responsibility"] == "owner"
    assert (
        server.research_get(project_id)["active_contract_id"]
        == (proposed["contract"]["contract_id"])
    )
    assert server.research_status(project_id)["d2_state"] == "sealed"
    report = server.research_report(project_id)
    assert report["terminal"] is False
    assert "ResearchGatePacket" in str(report["warning"])


def test_research_mcp_launch_cannot_confirm_or_bypass_owner_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = server.research_capture("A generic synthetic idea")
    project_id = captured["project"]["project_id"]

    with pytest.raises(RuntimeError, match="owner-approved pilot phase"):
        server.research_launch(project_id, "pilot")
    for unavailable_stage in ("deep", "confirm"):
        with pytest.raises(ValueError, match="must be pilot"):
            server.research_launch(project_id, unavailable_stage)


def test_research_launch_uses_a_launch_class_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A projection-class timeout would kill a mid-compute pilot and burn a lifetime slot."""
    from alpha_mcp import _control, _invoke

    captured: dict[str, object] = {}

    def _fake_run_json(
        args: list[str], *, data_dir: Path, timeout_seconds: float = 30.0
    ) -> dict[str, object]:
        captured["args"] = args
        captured["timeout_seconds"] = timeout_seconds
        return {}

    monkeypatch.setattr(_invoke, "run_json", _fake_run_json)
    _control.research_launch("00000000-0000-4000-8000-000000000000", "pilot", data_dir=tmp_path)

    assert captured["args"] == [
        "research",
        "run",
        "pilot",
        "00000000-0000-4000-8000-000000000000",
        "--json",
    ]
    web_launch_timeout = 120.0  # alpha_web/_research.py::launch uses this launch-class ceiling
    timeout_seconds = captured["timeout_seconds"]
    assert isinstance(timeout_seconds, float)
    assert timeout_seconds >= web_launch_timeout


def test_codex_seam_tools_record_packets_notes_and_briefs_with_agent_authorship(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = server.research_capture("SPY drifts upward into month-end rebalancing")
    project_id = captured["project"]["project_id"]

    protocols = server.list_research_protocols()
    assert len(protocols["protocols"]) == 13
    intake = server.get_research_protocol("new-idea-intake")
    assert intake["id"] == "new-idea-intake"
    assert isinstance(intake["content"], str) and intake["content"]

    packet = server.build_research_context_packet(
        project_id, kind="research_case", protocol_id="new-idea-intake"
    )
    packet_id = str(packet["packet_id"])
    assert packet_id.startswith("cp_")
    assert packet["created_by"] == "codex"
    assert packet["protocol_content_hash"] == intake["sha256"]

    fetched = server.get_research_context_packet(packet_id)
    assert fetched["payload"] == packet["payload"]  # byte-identical visibility

    note = server.add_research_note(
        project_id,
        note_kind="critique",
        body="The volatility-regime confounder is not yet matched.",
    )
    assert note["author_kind"] == "agent"  # MCP notes can never claim owner authorship

    brief = server.get_research_brief(project_id)
    assert brief["brief_schema"] == "ResearchBriefV1"
    assert str(brief["packet_id"]).startswith("cp_")
    assert brief["case"]["project_id"] == project_id
