"""The web research adapter stays a closed argv projection over the authoritative CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpha_web import _research


def test_research_projection_uses_only_the_bounded_cli_vocabulary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[list[str], Path, float]] = []

    def fake_run_json(args: list[str], *, data_dir: Path, timeout_seconds: float = 60.0) -> object:
        calls.append((args, data_dir, timeout_seconds))
        return {"ok": True}

    monkeypatch.setattr(_research, "_run_json", fake_run_json)
    assert _research.capture(data_dir=tmp_path, idea="idea", name="case") == {"ok": True}
    assert _research.get("project", data_dir=tmp_path) == {"ok": True}
    assert _research.proposal_options("project", data_dir=tmp_path) == {"ok": True}
    assert _research.propose(
        "project",
        data_dir=tmp_path,
        source_pack_id="sp_pack",
        answer_bundle_id="synthetic_spy_60m_four_hour_v1",
        dataset_ref_id=None,
        expected_case_revision="a" * 64,
    ) == {"ok": True}
    assert _research.launch("project", data_dir=tmp_path, stage="pilot") == {"ok": True}
    assert _research.status("project", data_dir=tmp_path) == {"ok": True}
    assert _research.report("project", data_dir=tmp_path) == {"ok": True}
    assert _research.list_cases(data_dir=tmp_path, limit=25, offset=5) == {"ok": True}
    assert _research.evidence_hub("project", data_dir=tmp_path) == {"ok": True}
    assert _research.context_packets("project", data_dir=tmp_path, limit=20, offset=0) == {
        "ok": True
    }
    assert _research.context_packet("cp_" + "0" * 64, data_dir=tmp_path) == {"ok": True}
    assert _research.notes("project", data_dir=tmp_path, limit=30, offset=0) == {"ok": True}
    assert _research.protocols(data_dir=tmp_path) == {"ok": True}
    assert _research.datasets(data_dir=tmp_path, symbol="AAPL", limit=10, offset=0) == {"ok": True}

    assert calls == [
        (["research", "capture", "idea", "--json", "--name", "case"], tmp_path, 60.0),
        (["research", "status", "project", "--json"], tmp_path, 60.0),
        (["research", "proposal-options", "project", "--json"], tmp_path, 60.0),
        (
            [
                "research",
                "draft",
                "project",
                "--source-pack-id",
                "sp_pack",
                "--answer-bundle",
                "synthetic_spy_60m_four_hour_v1",
                "--expected-case-revision",
                "a" * 64,
                "--json",
            ],
            tmp_path,
            60.0,
        ),
        (["research", "run", "pilot", "project", "--json"], tmp_path, 120.0),
        (["research", "status", "project", "--json"], tmp_path, 60.0),
        (["research", "report", "project", "--json"], tmp_path, 60.0),
        (
            ["research", "list", "--limit", "25", "--offset", "5", "--json"],
            tmp_path,
            60.0,
        ),
        (["research", "evidence-hub", "project", "--json"], tmp_path, 60.0),
        (
            [
                "research",
                "context",
                "list",
                "project",
                "--limit",
                "20",
                "--offset",
                "0",
                "--json",
            ],
            tmp_path,
            60.0,
        ),
        (["research", "context", "show", "cp_" + "0" * 64, "--json"], tmp_path, 60.0),
        (
            ["research", "note", "list", "project", "--limit", "30", "--offset", "0", "--json"],
            tmp_path,
            60.0,
        ),
        (["research", "protocols", "list", "--json"], tmp_path, 60.0),
        (
            [
                "research",
                "data",
                "list",
                "--symbol",
                "AAPL",
                "--limit",
                "10",
                "--offset",
                "0",
                "--json",
            ],
            tmp_path,
            60.0,
        ),
    ]


def test_scorecard_projection_extracts_the_status_scorecard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def fake_run_json(args: list[str], *, data_dir: Path, timeout_seconds: float = 60.0) -> object:
        del data_dir, timeout_seconds
        calls.append(args)
        return {
            "phase": "triage",
            "scorecard": {"scorecard_schema": "ResearchReadinessScorecardV1"},
        }

    monkeypatch.setattr(_research, "_run_json", fake_run_json)
    assert _research.scorecard("project", data_dir=tmp_path) == {
        "scorecard_schema": "ResearchReadinessScorecardV1"
    }
    assert calls == [["research", "status", "project", "--json"]]

    def missing_scorecard(
        args: list[str], *, data_dir: Path, timeout_seconds: float = 60.0
    ) -> object:
        del args, data_dir, timeout_seconds
        return {"phase": "triage"}

    monkeypatch.setattr(_research, "_run_json", missing_scorecard)
    with pytest.raises(RuntimeError, match="invalid research scorecard projection"):
        _research.scorecard("project", data_dir=tmp_path)


def test_research_projection_rejects_unavailable_stages(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must be pilot"):
        _research.launch("project", data_dir=tmp_path, stage="confirm")


@pytest.mark.parametrize("payload", [[], {1: "not-a-string-key"}])
def test_research_projection_rejects_malformed_cli_output(
    payload: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run_json(args: list[str], *, data_dir: Path, timeout_seconds: float = 60.0) -> object:
        del args, data_dir, timeout_seconds
        return payload

    monkeypatch.setattr(_research, "_run_json", fake_run_json)
    with pytest.raises(RuntimeError, match="invalid research capture projection"):
        _research.capture(data_dir=tmp_path, idea="idea")
