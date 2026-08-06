"""The six research MCP tools remain thin, bounded, and unable to approve or reveal data."""

from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from alpha_cli.control_store import ControlStore
from alpha_core.config import AlphaSettings
from alpha_mcp import server


def test_research_mcp_surface_is_exactly_six_tools_without_owner_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    names = {tool.name for tool in anyio.run(server.mcp.list_tools)}

    assert {
        "research_capture",
        "research_get",
        "research_propose",
        "research_launch",
        "research_status",
        "research_report",
    } <= names
    assert "research_approve" not in names
    assert "research_decide" not in names
    assert "research_reveal" not in names


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
    from alpha_mcp import _control

    captured: dict[str, object] = {}

    def _fake_run_json(
        args: list[str], *, data_dir: Path, timeout_seconds: float = 30.0
    ) -> dict[str, object]:
        captured["args"] = args
        captured["timeout_seconds"] = timeout_seconds
        return {}

    monkeypatch.setattr(_control._invoke, "run_json", _fake_run_json)
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
