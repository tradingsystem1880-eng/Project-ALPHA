import json
from pathlib import Path

import pytest

from alpha_eval.investigation_comparison import frozen_schedule, resource_record


def test_schedule_is_balanced_complete_and_deterministic():
    schedule = frozen_schedule()
    assert schedule == frozen_schedule()
    assert len(schedule) == 9
    assert len({(r["case"], r["mode"]) for r in schedule}) == 9
    for position in range(3):
        assert {schedule[i]["mode"] for i in range(position, 9, 3)} == {
            "legacy",
            "prechecked",
            "fixed",
        }


def test_usage_is_complete_or_unknown_not_zero(tmp_path: Path):
    report = dict(model_calls=2, attempts=[{"status": "failed"}], receipts=[], status="incomplete")
    usage = dict(input_tokens=100, cached_input_tokens=20, output_tokens=10)
    (tmp_path / "turn-1.transport.json").write_text(json.dumps(dict(usage=[usage])))
    result = resource_record(tmp_path, report)
    assert result["usage_complete"] is False
    assert result["input_tokens"] is None
    assert result["observed_input_tokens"] == 100
    assert result["measurement_attempts"] == 1
    assert result["status"] == "incomplete"
    (tmp_path / "turn-2.transport.json").write_text(json.dumps(dict(usage=[usage])))
    result = resource_record(tmp_path, report)
    assert result["input_tokens"] == 200
    assert result["cached_input_tokens"] == 40  # subset, never added to input


@pytest.mark.parametrize(
    "bad", [None, {}, {"input_tokens": -1, "cached_input_tokens": 0, "output_tokens": 3}]
)
def test_invalid_usage_remains_unknown(tmp_path: Path, bad):
    (tmp_path / "turn-1.transport.json").write_text(json.dumps(dict(usage=[bad])))
    result = resource_record(
        tmp_path, dict(model_calls=1, attempts=[], receipts=[], status="incomplete")
    )
    assert result["input_tokens"] is None


@pytest.mark.parametrize("setup_failure", [False, True])
def test_comparison_freezes_protocol_before_calls_and_retains_all_cells(
    tmp_path: Path, monkeypatch, setup_failure
):
    from alpha_eval import investigation_comparison as mod

    cases = [
        dict(case=k, directory=str(i), panel_sha256=str(i), calibration={"inspect_run": {}})
        for i, k in enumerate(("conditional", "indicator_null", "accounting_defect"))
    ]

    def calibrate(base, model, live):
        assert live is False
        base.mkdir()
        for case in cases:
            (base / case["directory"]).mkdir()
        return dict(cases=cases)

    monkeypatch.setattr(mod, "run_demo", calibrate)
    monkeypatch.setattr(mod, "Worker", lambda *a: lambda _: dict(integrity_ok=True))
    seen = []

    setups = []

    def proposer(workspace, model):
        setups.append(workspace)
        assert list(workspace.parent.glob("*.reserved.json"))
        if setup_failure and len(setups) == 2:
            raise OSError("provider absent")
        protocol = json.loads((tmp_path / "run/comparison-protocol.json").read_text())
        assert len(protocol["schedule"]) == 9
        return lambda *a: dict(
            action="final",
            reason="test",
            conclusion="bounded",
            next_tests=[],
            evidence_ids=["attempt-1"],
        )

    monkeypatch.setattr(mod, "CodexProposer", proposer)
    real_run_case = mod.run_case

    def run_case(path, propose, worker, *, mode):
        seen.append(mode)
        # legacy cannot finalize without inspection: retain that failure, do not filter it out
        return real_run_case(path, propose, worker, mode=mode)

    monkeypatch.setattr(mod, "run_case", run_case)
    result = mod.run_comparison(tmp_path / "run", "test-model", live=True)
    expected = [item["mode"] for item in mod.frozen_schedule()]
    assert seen == ([m for i, m in enumerate(expected) if i != 1] if setup_failure else expected)
    assert len(result["records"]) == 9
    assert sum(r["result"]["status"] == "incomplete" for r in result["records"]) == (
        4 if setup_failure else 3
    )
    for i, r in enumerate(result["records"]):
        assert r["resources"]["input_tokens"] == (0 if setup_failure and i == 1 else None)


def test_corrupt_transport_is_unknown_with_diagnostic(tmp_path: Path):
    (tmp_path / "turn-1.transport.json").write_text("{truncated")
    result = resource_record(
        tmp_path, dict(model_calls=1, attempts=[], receipts=[], status="incomplete")
    )
    assert result["input_tokens"] is None
    assert result["usage_errors"]
