from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_investigation_worker import publish, run

from alpha_eval.investigation_cases import export_panel
from alpha_eval.investigation_judgment_cases import CASES, judgment_panel


def test_context_pair_preserves_quantitative_evidence():
    assert judgment_panel("market_context")["rows"] == judgment_panel("misleading_context")["rows"]
    assert len(CASES) == 6


def test_missing_data_is_not_zero_or_bad_accounting(tmp_path: Path):
    publish(tmp_path, judgment_panel("missing_evidence"))
    inspect = run(tmp_path, "inspect_run")
    assert inspect.returncode == 0, inspect.stderr
    assert json.loads(inspect.stdout)["integrity_ok"] is True
    loss = json.loads(run(tmp_path, "loss_episodes").stdout)
    assert loss["episodes"][0]["benchmark_total_return"] is None
    conditional = json.loads(run(tmp_path, "conditional_diagnostic").stdout)
    assert conditional["status"] == "unavailable"
    assert "groups" not in conditional


def test_hindsight_provenance_survives_measurement(tmp_path: Path):
    publish(tmp_path, judgment_panel("hindsight_indicator"))
    result = run(tmp_path, "conditional_diagnostic")
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout)
    assert value["indicator_provenance"]["kind"] == "post_outcome_label"
    assert value["indicator_provenance"]["available_date"] > "2020-09-27"
    assert value["mean_difference_1_minus_0"] == pytest.approx(-0.014)
    assert value["validated_edge"] is False
    assert "recorded" in value["conditioning"]


def test_future_label_poison_cannot_change_earlier_export(tmp_path: Path):
    panel = judgment_panel("hindsight_indicator")
    first = export_panel(panel, tmp_path / "a", "2020-09-27")
    panel["rows"][100]["risk_indicator"] = 1 - panel["rows"][100]["risk_indicator"]
    panel["indicator_provenance"]["definition"] = "Future poison"
    second = export_panel(panel, tmp_path / "b", "2020-09-27")
    assert first["parent_sha256"] != second["parent_sha256"]  # leaky unfiltered parent changes
    assert first["panel_sha256"] == second["panel_sha256"]
    exported = json.loads((tmp_path / "a/panel.json").read_text())
    assert all(r["risk_indicator"] is None for r in exported["rows"])
    assert exported["indicator_provenance"]["kind"] == "unavailable"


def test_worker_rejects_unredacted_future_provenance(tmp_path: Path):
    panel = judgment_panel("hindsight_indicator")
    panel["indicator_provenance"]["available_date"] = "2030-01-01"
    publish(tmp_path, panel)
    assert run(tmp_path, "inspect_run").returncode != 0


def test_judgment_prompt_preserves_facts_and_prioritizes_discriminating_evidence(tmp_path):
    from alpha_eval.investigation_demo import run_case

    prompts = []

    def propose(prompt, *args):
        prompts.append(prompt)
        return dict(
            action="final",
            reason="bounded",
            conclusion="Exploratory.",
            next_tests=[],
            evidence_ids=["attempt-1"],
        )

    result = run_case(
        tmp_path / "trial",
        propose,
        lambda _: dict(integrity_ok=True),
        mode="prechecked",
        judgment=True,
    )
    assert result["status"] == "completed"
    assert "credible alternative" in prompts[0]
    assert "distinguish" in prompts[0]
    assert "frozen observable" not in prompts[0]
    assert result["judgment_guidance"] is True


def test_provider_failure_after_measurement_preserves_known_evidence(tmp_path):
    from alpha_eval.investigation_demo import run_case

    def fail(*args):
        raise RuntimeError("synthetic provider interruption")

    report = run_case(
        tmp_path / "trial",
        fail,
        lambda _: dict(integrity_ok=True),
        mode="prechecked",
        judgment=True,
    )
    assert report["status"] == "incomplete"
    assert len(report["receipts"]) == 1
    assert report["model_calls"] == 1
    assert "provider interruption" in report["error"]


def test_judgment_schedule_and_failure_are_explicit():
    from alpha_eval.investigation_judgment import judgment_schedule, measure_action

    schedule = judgment_schedule()
    assert len(schedule) == 12
    assert {r["mode"] for r in schedule} == {"prechecked", "fixed"}
    calls = []

    def worker(action):
        calls.append(action)
        return {"value": 42}

    with pytest.raises(RuntimeError, match="injected"):
        measure_action(worker, "historical_context", "historical_context")
    assert calls == []
    assert measure_action(worker, "inspect_run", "historical_context") == {"value": 42}


def test_online_provenance_cannot_postdate_nonnull_labels(tmp_path):
    panel = judgment_panel("market_context")
    panel["indicator_provenance"]["available_date"] = panel["cutoff"]
    publish(tmp_path, panel)
    assert run(tmp_path, "inspect_run").returncode != 0


def test_provider_error_is_not_classified_as_model_tool_attempt(tmp_path, monkeypatch):
    from alpha_eval import investigation_codex as transport

    proposer = transport.CodexProposer.__new__(transport.CodexProposer)
    proposer.workspace, proposer.model, proposer.version = tmp_path, "gpt-6-astra", "test"

    def stream(argv, cwd, env, seconds, raw, consume):
        event = json.dumps(dict(type="error", message="workspace routing discovery failed"))
        raw.write(event)
        assert consume(event) is False
        return dict(stop="tool_call_cap", returncode=-15, stderr_tail="")

    monkeypatch.setattr(transport, "stream_process", stream)
    with pytest.raises(RuntimeError):
        proposer("test", tmp_path / "call", 1)
    record = json.loads((tmp_path / "call.transport.json").read_text())
    assert record["failure_kind"] == "provider_error"
