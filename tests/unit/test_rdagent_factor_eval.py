"""Synthetic screening/replay and cross-run ledger contracts (no market data)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from alpha_cli import rdagent_factor_eval as ev
from alpha_core import DataError


def fixture(run: Path, *, seed: int = 42, noise: bool = False) -> Path:
    (run / "panel").mkdir(parents=True)
    dates = pd.date_range("2021-01-01", "2023-12-31", tz="UTC")
    rng = np.random.default_rng(42)
    component = rng.normal(0, 0.018, (len(dates), 15))
    returns = component + rng.normal(0, 0.006, component.shape)
    opens = 100 * np.cumprod(1 + returns, axis=0)
    index = pd.MultiIndex.from_product(
        [dates.date, [f"C{i:02}USDT" for i in range(15)]], names=["date", "instrument"]
    )
    panel = pd.DataFrame(
        {
            "open": opens.ravel(),
            "close": opens.ravel(),
            "high": opens.ravel() * 1.01,
            "low": opens.ravel() * 0.99,
            "volume": 100.0,
            "quote_volume": 10000.0,
        },
        index=index,
    ).reset_index()
    panel.to_parquet(run / "panel/panel.parquet", index=False)
    (run / "panel/panel-receipt.json").write_text(
        json.dumps(
            {
                "panel_sha256": hashlib.sha256(
                    (run / "panel/panel.parquet").read_bytes()
                ).hexdigest(),
                "instruments": {s: {"last_day": "2023-12-31"} for s in panel.instrument.unique()},
            }
        )
    )
    signal = np.roll(component, -2, axis=0) + np.random.default_rng(seed).normal(
        0, 0.003, component.shape
    )
    if noise:
        signal = np.random.default_rng(seed).normal(size=component.shape)
    pd.DataFrame({"factor": signal.ravel()}, index=index).reset_index().to_parquet(
        run / "factors.parquet", index=False
    )
    req = run / "request.json"
    req.write_text(
        json.dumps(
            {
                "schema": "AlphaRdagentFactorRequestV1",
                "iteration": 0,
                "hypothesis_sha256": "b" * 64,
                "values_file": "factors.parquet",
                "factors": [
                    {
                        "name": "factor",
                        "code_sha256": hashlib.sha256(str(seed).encode()).hexdigest(),
                        "status": "OK",
                        "lookahead": {"status": "PASS"},
                    }
                ],
            }
        )
    )
    return req


def evaluate(run: Path, req: Path, ledger: Path) -> dict[str, Any]:
    return ev.evaluate(run, req, run / "result.json", ledger)


def test_planted_factor_is_candidate_and_deterministic(tmp_path: Path) -> None:
    run = tmp_path / "run"
    req = fixture(run)
    ledger = tmp_path / "trials.jsonl"
    result = evaluate(run, req, ledger)
    factor = result["factors"][0]
    assert factor["status"] == "CANDIDATE"
    assert factor["q"] < 0.10
    assert factor["replay"]["net"]["annualized_return"] > 0
    assert result["decision"] is True
    assert result["label"] == ev.LABEL
    assert ev.SURVIVORSHIP in result["feedback_text"]
    assert all(v is False for v in result["authority"].values())
    original = (run / "result.json").read_bytes()
    original_lines = ledger.read_bytes()
    other = tmp_path / "empty-ledger.jsonl"
    ev.evaluate(run, req, run / "second-result.json", other)
    assert (run / "second-result.json").read_bytes() == original
    assert other.read_bytes() == original_lines


@pytest.mark.parametrize("seed", [19, 81])
def test_noise_never_replayed(tmp_path: Path, seed: int) -> None:
    run = tmp_path / "run"
    req = fixture(run, seed=seed, noise=True)
    with patch.object(
        ev, "run_weight_replay", side_effect=AssertionError("screen failed but replay called")
    ):
        record = evaluate(run, req, tmp_path / "ledger.jsonl")
    assert record["decision"] is False
    assert record["factors"][0]["status"] == "SCREEN_FAIL"
    assert record["factors"][0]["q"] >= ev.Q_THRESHOLD


def test_noise_screen_is_calibrated() -> None:
    # Pure noise passes a 10% screen about 10% of the time (seed 7 of the fixture is one such
    # chance pass, q 0.01); a much higher rate would mean the inference is anti-conservative.
    dates = pd.date_range(*ev.EXPLORATION, tz="UTC")
    outcome = pd.DataFrame(np.random.default_rng(42).normal(0, 0.02, (len(dates), 15)), dates)
    passes = 0
    for seed in range(80):
        signal = pd.DataFrame(np.random.default_rng(1000 + seed).normal(size=outcome.shape), dates)
        passes += ev.screen(signal, outcome, f"{seed:064x}")["p"] < ev.Q_THRESHOLD
    assert passes / 80 <= 0.2


def test_repeat_across_runs_and_append_only(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    ledger = tmp_path / "ledger.jsonl"
    evaluate(first, fixture(first), ledger)
    before = ledger.read_bytes()
    result = evaluate(second, fixture(second), ledger)
    assert ledger.read_bytes().startswith(before)
    assert result["family_size"] == 1
    assert result["total_trials"] == 2
    repeated = result["factors"][0]
    assert repeated["status"] == "REPEAT"
    assert repeated["first_trial"]["run_id"] == "first"
    assert not result["decision"]


def test_failures_and_degenerate_count_in_family(tmp_path: Path) -> None:
    run = tmp_path / "run"
    req = fixture(run)
    frame = pd.read_parquet(run / "factors.parquet")
    frame["factor"] = 1.0
    frame.to_parquet(run / "factors.parquet", index=False)
    value = json.loads(req.read_bytes())
    value["factors"] += [
        {"name": s, "code_sha256": h * 64, "status": s, "lookahead": {}}
        for s, h in [("FAILED", "c"), ("LOOKAHEAD", "d")]
    ]
    req.write_text(json.dumps(value))
    result = evaluate(run, req, tmp_path / "ledger.jsonl")
    assert result["family_size"] == 3
    assert [f["status"] for f in result["factors"]] == ["DEGENERATE", "FAILED", "LOOKAHEAD"]
    assert all(f["p"] == pytest.approx(1) for f in result["factors"])


@pytest.mark.parametrize("kind", ["values", "panel", "tamper", "ledger"])
def test_invalid_inputs_refused(tmp_path: Path, kind: str) -> None:
    run = tmp_path / "run"
    req = fixture(run)
    ledger = tmp_path / "ledger.jsonl"
    if kind == "values":
        frame = pd.read_parquet(run / "factors.parquet")
        frame.loc[0, "date"] = pd.Timestamp("2024-01-01").date()
        frame.to_parquet(run / "factors.parquet", index=False)
    elif kind == "panel":
        receipt = json.loads((run / "panel/panel-receipt.json").read_bytes())
        receipt["instruments"]["C00USDT"]["last_day"] = "2024-01-01"
        (run / "panel/panel-receipt.json").write_text(json.dumps(receipt))
    elif kind == "tamper":
        with (run / "panel/panel.parquet").open("ab") as stream:
            stream.write(b"tamper")
    else:
        ledger.write_text('{"schema": "wrong"}\n')
    with pytest.raises(DataError):
        evaluate(run, req, ledger)


def test_one_failing_factor_is_recorded_as_error_and_the_rest_still_land(tmp_path: Path) -> None:
    run = tmp_path / "run"
    req = fixture(run)
    value = json.loads(req.read_bytes())
    value["factors"].append(
        {"name": "broken", "code_sha256": "e" * 64, "status": "OK", "lookahead": {}}
    )
    frame = pd.read_parquet(run / "factors.parquet")
    frame["broken"] = frame["factor"]
    frame.to_parquet(run / "factors.parquet", index=False)
    req.write_text(json.dumps(value))
    real = ev.screen

    def flaky(signal: pd.DataFrame, outcome: pd.DataFrame, digest: str) -> dict[str, Any]:
        if digest == "e" * 64:
            raise ZeroDivisionError("planted")
        return real(signal, outcome, digest)

    ledger = tmp_path / "ledger.jsonl"
    with patch.object(ev, "screen", flaky):
        result = evaluate(run, req, ledger)
    statuses = {f["name"]: f["status"] for f in result["factors"]}
    assert statuses == {"factor": "CANDIDATE", "broken": "ERROR"}
    assert result["family_size"] == 2
    assert len(ledger.read_bytes().splitlines()) == 2


def test_a_day_with_too_few_names_is_degenerate_not_a_crash(tmp_path: Path) -> None:
    run = tmp_path / "run"
    req = fixture(run)
    frame = pd.read_parquet(run / "factors.parquet")
    day = frame["date"] == frame["date"].iloc[15 * 400]
    frame.loc[day & ~frame["instrument"].isin(["C00USDT", "C01USDT"]), "factor"] = float("nan")
    frame.to_parquet(run / "factors.parquet", index=False)
    result = evaluate(run, req, tmp_path / "ledger.jsonl")
    factor = result["factors"][0]
    assert factor["status"] == "DEGENERATE"
    assert factor["screen"]["thin_days"] == 1
