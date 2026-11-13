"""Workflow 4, research case: capture -> status -> sources -> dataset -> stop at the owner.

The offline path ends before the owner's approval. The only available chart choice for the daily
lane is registered Tiingo bars, and offline there is only synthetic data, which is not relabelled
here, so the draft is refused. Running the pilot also waits for an owner-approved phase. Owner
approval is a research-integrity control and is never automated by this check.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.smoke._harness import alpha
from tests.smoke.conftest import SNAPSHOT, copy_home

pytestmark = [pytest.mark.smoke, pytest.mark.usefixtures("owned_test_process")]

_IDEA = "SPY bounces after double bottoms on the daily chart"


def test_research_case_advances_to_the_owner_boundary(data_home: Path, tmp_path: Path) -> None:
    home = copy_home(data_home, tmp_path)

    def research(*args: str) -> Any:
        return alpha(home, "research", *args, "--json").json()

    captured = research("capture", _IDEA)
    case_id = str(captured["project"]["project_id"])
    assert captured["contract"]["payload"]["raw_idea"] == _IDEA

    listed = research("list")
    assert case_id in {item["case_id"] for item in listed["items"]}
    status = research("status", case_id)
    assert status["phase"] == "triage"
    assert status["scorecard"]["recommendation"]["value"] == "MORE RESEARCH REQUIRED"

    source = research(
        "sources", "add", case_id, "--title", "Technical trading revisited",
        "--locator", "doi:10.0000/example", "--provider", "crossref",
        "--access-mode", "metadata_only",
    )  # fmt: skip
    pack = research("sources", "freeze", case_id, "--source-id", str(source["source_id"]))
    dataset = research(
        "data", "register", "SPY", "--kind", "snapshot", "--snapshot-id", SNAPSHOT,
        "--start", "2020-01-01", "--end", "2021-02-03", "--bar-minutes", "1440",
        "--registered-by", "smoke-check",
    )  # fmt: skip
    assert dataset["origin"]["snapshot_id"] == SNAPSHOT
    assert dataset["research_only"] is True

    refused_draft = alpha(
        home, "research", "draft", case_id, "--source-pack-id", str(pack["pack_id"]),
        "--answer", "chart_construction=tiingo_daily_fallback",
        "--answer", "event_availability=second_trough_confirmable",
        "--answer", "primary_outcome=next_regular_session_return_50bp",
        "--dataset", str(dataset["ref_id"]), "--json", expect=2,
    )  # fmt: skip
    assert "tiingo" in refused_draft.stderr + refused_draft.stdout
    refused_pilot = alpha(home, "research", "run", "pilot", case_id, "--json", expect=2)
    assert "owner-approved" in refused_pilot.stderr + refused_pilot.stdout

    report = research("report", case_id)
    assert report["report_schema"] == "ResearchProgressReportV1"
    assert report["terminal"] is False
    view = research("decision-view", case_id)
    assert view["gate_packet"] is None  # a terminal gate packet needs the owner's decision
    assert view["phase"] == "triage"
    assert str(view["next_action"]).startswith("Owner")
