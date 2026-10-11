"""Real platform-process tests for the closed synthetic measurement worker."""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
WORKER = ROOT / "tools/alpha-eval/worlds/investigation_worker.py"


def panel():
    values = [100.0, 110.0, 44.0, 48.4, 19.36]
    return {
        "schema_version": 1,
        "synthetic": True,
        "mode": "retrospective_diagnosis",
        "cutoff": "2020-01-05",
        "rows": [
            {
                "ts": f"2020-01-0{i + 1}",
                "available_at": f"2020-01-0{i + 1}",
                "equity": e,
                "cash": e,
                "marked_position": 0.0,
                "benchmark": 100.0 - i,
                "risk_indicator": i % 2,
            }
            for i, e in enumerate(values)
        ],
        "sources": [
            {
                "source_id": "local-1",
                "text": "Synthetic event; not causal evidence.",
                "event_date": "2020-01-03",
                "publication_date": "2020-01-03",
                "available_date": "2020-01-03",
                "retrieved_date": "2020-01-06",
            }
        ],
    }


def publish(path, payload):
    raw = json.dumps(payload).encode()
    (path / "panel.json").write_bytes(raw)
    (path / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "panel_sha256": hashlib.sha256(raw).hexdigest()})
    )


def run(path, action):
    return subprocess.run(
        [str(ROOT / ".venv/bin/python"), str(WORKER), str(path), action],
        capture_output=True,
        text=True,
        check=False,
    )


def test_worker_measurements_and_lagged_negative_control(tmp_path):
    publish(tmp_path, panel())
    proc = run(tmp_path, "inspect_run")
    assert proc.returncode == 0, proc.stderr
    inspect = json.loads(proc.stdout)
    assert inspect["integrity_ok"] and inspect["integrity_scope"] == "synthetic_identity_only"
    loss = json.loads(run(tmp_path, "loss_episodes").stdout)
    assert loss["episodes"][0]["depth"] == pytest.approx(-0.824)
    assert loss["episodes"][0]["peak_to_trough_intervals"] == 3
    assert "peak_to_trough_observations" not in loss["episodes"][0]
    assert loss["episodes"][0]["benchmark_total_return"] == pytest.approx(96 / 99 - 1)
    conditional = json.loads(run(tmp_path, "conditional_diagnostic").stdout)
    assert conditional["groups"]["0"]["mean_next_return"] == pytest.approx(0.1)
    assert conditional["groups"]["1"]["mean_next_return"] == pytest.approx(-0.6)
    # Leaky contemporaneous labels produce the opposite answer on this fixture.
    rows = panel()["rows"]
    leaky = [
        rows[i]["equity"] / rows[i - 1]["equity"] - 1
        for i in range(1, 5)
        if rows[i]["risk_indicator"] == 1
    ]
    assert sum(leaky) / len(leaky) != pytest.approx(conditional["groups"]["1"]["mean_next_return"])
    context = json.loads(run(tmp_path, "historical_context").stdout)
    assert len(context["sources"]) == 1 and context["causal_proof"] is False
    assert conditional["synthetic"] and conditional["advisory_only"] and not conditional["admitted"]


def test_integrity_defect_blocks_interpretation(tmp_path):
    value = panel()
    value["rows"][2]["cash"] += 1
    publish(tmp_path, value)
    assert json.loads(run(tmp_path, "inspect_run").stdout)["integrity_ok"] is False
    for action in ("loss_episodes", "historical_context", "conditional_diagnostic"):
        proc = run(tmp_path, action)
        assert proc.returncode != 0 and "integrity" in proc.stderr


@pytest.mark.parametrize(
    "mutation", ["future", "late", "duplicate", "nonfinite", "bool", "source", "missing_group"]
)
def test_invalid_panels_fail(tmp_path, mutation):
    value = panel()
    if mutation == "future":
        value["rows"][-1]["ts"] = "2020-01-06"
    if mutation == "late":
        value["rows"][0]["available_at"] = "2020-01-02"
    if mutation == "duplicate":
        value["rows"][1]["ts"] = "2020-01-01"
    if mutation == "nonfinite":
        value["rows"][0]["equity"] = float("nan")
    if mutation == "bool":
        value["rows"][0]["risk_indicator"] = True
    if mutation == "source":
        value["sources"][0]["available_date"] = "2020-01-06"
    if mutation == "missing_group":
        for row in value["rows"]:
            row["risk_indicator"] = 0
    publish(tmp_path, value)
    assert run(tmp_path, "conditional_diagnostic").returncode != 0


@pytest.mark.parametrize("mutation", ["tamper", "extra", "symlink", "duplicate_key"])
def test_export_boundary(tmp_path, mutation):
    publish(tmp_path, panel())
    if mutation == "tamper":
        (tmp_path / "panel.json").write_text("{}")
    if mutation == "extra":
        (tmp_path / "truth.json").write_text("hidden")
    if mutation == "symlink":
        (tmp_path / "panel.json").unlink()
        (tmp_path / "panel.json").symlink_to(tmp_path / "manifest.json")
    if mutation == "duplicate_key":
        (tmp_path / "manifest.json").write_text(
            '{"schema_version":1,"schema_version":1,"panel_sha256":"' + "a" * 64 + '"}'
        )
    assert run(tmp_path, "inspect_run").returncode != 0
