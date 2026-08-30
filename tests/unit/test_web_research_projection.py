"""The web research adapter stays a closed argv projection over the authoritative CLI."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from alpha_web import _research
from alpha_web.api.models import VerifiedBlindSemanticReadV1


def _projection() -> dict[str, object]:
    return {
        "schema": "VerifiedBlindSemanticReadV1",
        "schema_version": 1,
        "source_verification": "verified_completed_d0_recomputation",
        "authority": "none",
        "run_id": "0123456789abcdef",
        "projection": {
            "schema": "BlindSemanticProjectionV1",
            "schema_version": 1,
            "run_id": "0123456789abcdef",
            "acceptance_artifact_sha256": "a" * 64,
            "events_artifact_sha256": "b" * 64,
            "chart_data_artifact_sha256": "c" * 64,
            "cutoff_confirmed_at": "2024-01-01T00:00:00Z",
            "points": [
                {
                    "point_id": "price:0",
                    "available_at": "2024-01-01T00:00:00Z",
                    "value": 1.25,
                }
            ],
            "masked_count": 2,
            "authority": "none",
            "cutoff_source": "d0_acceptance_measurement_reference",
            "lineage_verification": "not_checked",
            "semantic_status": "unfrozen",
            "content_sha256": "d" * 64,
        },
        "content_sha256": "e" * 64,
    }


def test_semantic_projection_uses_exact_cli_argv_without_cutoff_or_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[list[str], Path]] = []

    def fake_run_json(args: list[str], *, data_dir: Path, **kwargs: object) -> object:
        calls.append((args, data_dir))
        assert kwargs == {}
        return _projection()

    monkeypatch.setattr(_research, "_run_json", fake_run_json)
    assert _research.semantic_projection("project", data_dir=tmp_path) == _projection()
    assert calls == [(["research", "semantic-projection", "project", "--json"], tmp_path)]


@pytest.mark.parametrize("payload", [[], "projection", 1, None])
def test_semantic_projection_distinguishes_non_object_output(
    payload: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_research, "_run_json", lambda *args, **kwargs: payload)
    with pytest.raises(_research.InvalidSemanticProjection, match="invalid semantic projection"):
        _research.semantic_projection("project", data_dir=tmp_path)


def test_verified_projection_model_is_strict_and_checks_nested_run_identity() -> None:
    payload = _projection()
    assert VerifiedBlindSemanticReadV1.model_validate(payload).model_dump(by_alias=True) == payload

    mismatched = _projection()
    projection = cast(dict[str, object], mismatched["projection"])
    mismatched["projection"] = {**projection, "run_id": "fedcba9876543210"}
    with pytest.raises(ValueError):
        VerifiedBlindSemanticReadV1.model_validate(mismatched)


@pytest.mark.parametrize(
    "change",
    [
        {"extra": True},
        {"run_id": "0123456789ABCDEf"},
        {"projection": {"cutoff_confirmed_at": "2024-01-01T00:00:00+00:00"}},
        {
            "projection": {
                "points": [
                    {
                        "point_id": "price:0",
                        "available_at": "2024-01-01T00:00:00Z",
                        "value": float("nan"),
                    }
                ]
            }
        },
        {
            "projection": {
                "points": [{"point_id": "", "available_at": "2024-01-01T00:00:00Z", "value": 1.25}]
            }
        },
        {
            "projection": {
                "points": [
                    {"point_id": " price:0", "available_at": "2024-01-01T00:00:00Z", "value": 1.25}
                ]
            }
        },
        {
            "projection": {
                "points": [
                    {
                        "point_id": "price:" + chr(10) + "0",
                        "available_at": "2024-01-01T00:00:00Z",
                        "value": 1.25,
                    }
                ]
            }
        },
        {"projection": {"masked_count": True}},
    ],
)
def test_verified_projection_model_rejects_malformed_values(change: dict[str, object]) -> None:
    payload = _projection()
    for key, value in change.items():
        if key == "projection":
            projection = cast(dict[str, object], payload["projection"])
            payload["projection"] = {**projection, **cast(dict[str, object], value)}
        else:
            payload[key] = value
    with pytest.raises(ValueError):
        VerifiedBlindSemanticReadV1.model_validate(payload)


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
