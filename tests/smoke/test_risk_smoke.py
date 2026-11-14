"""Risk figures and their basis through the installed CLI and Workstation."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.error import HTTPError

import numpy as np
import polars as pl
import pytest
from numpy.typing import NDArray

from tests.smoke._harness import alpha, get_json, web_server
from tests.smoke.conftest import SNAPSHOT, STRATEGY, BacktestHome, copy_home
from tests.smoke.test_validation_smoke import _GAUNTLET

pytestmark = [pytest.mark.smoke, pytest.mark.usefixtures("owned_test_process")]

_SCENARIO_NAMES = ["base", "vol +50%", "vol +100%", "-3σ shock", "-5σ shock"]


def _recompute(equity: NDArray[np.float64], confidence: float = 0.95) -> list[dict[str, float]]:
    returns = equity[1:] / equity[:-1] - 1.0
    mean = np.mean(returns)
    std = np.std(returns, ddof=1)
    scenarios = [
        returns,
        mean + (returns - mean) * 1.5,
        mean + (returns - mean) * 2.0,
        np.append(returns, -3.0 * std),
        np.append(returns, -5.0 * std),
    ]
    summaries = []
    for scenario in scenarios:
        sample_std = np.std(scenario, ddof=1)
        wealth = np.concatenate(([1.0], np.cumprod(1.0 + scenario)))
        quantile = np.quantile(scenario, 1.0 - confidence)
        summaries.append(
            {
                "sharpe": float(np.mean(scenario) / sample_std * np.sqrt(252)),
                "annual_vol": float(sample_std * np.sqrt(252)),
                "max_drawdown": float(np.min(wealth / np.maximum.accumulate(wealth) - 1.0)),
                "value_at_risk": max(0.0, -float(quantile)),
                "expected_shortfall": max(0.0, -float(np.mean(scenario[scenario <= quantile]))),
                "total_return": float(wealth[-1] - 1.0),
            }
        )
    return summaries


def test_backtest_risk_figures_recompute_and_state_their_basis(
    backtest_home: BacktestHome, tmp_path: Path
) -> None:
    home = copy_home(backtest_home.home, tmp_path)
    run_id = backtest_home.run_id
    run_dir = home / "data" / "runs" / run_id
    equity_path = run_dir / "equity_curve.parquet"
    frame = pl.read_parquet(equity_path)
    equity = frame["equity"].to_numpy()
    manifest = json.loads((run_dir / "manifest.json").read_text())
    args = ("risk", "scenario", "--from-run", run_id)
    payload = alpha(home, *args, "--json", "--include-metric-basis").json()

    assert [scenario["name"] for scenario in payload["scenarios"]] == _SCENARIO_NAMES
    for actual, expected in zip(payload["scenarios"], _recompute(equity), strict=True):
        for metric, value in expected.items():
            assert actual[metric] == pytest.approx(
                value, abs=1e-12, rel=1e-12 if metric == "sharpe" else 0
            ), (actual["name"], metric)

    provenance = payload["provenance"]
    assert provenance["source_command"] == "backtest_run"
    assert provenance["snapshot_id"] == SNAPSHOT
    assert provenance["snapshot_hash"] == manifest["snapshot_hash"]
    assert (
        provenance["source_artifact_sha256"] == hashlib.sha256(equity_path.read_bytes()).hexdigest()
    )
    assert provenance["as_of"] == frame["ts"][-1].isoformat()
    assert provenance["metric_basis"]["anchor_value"] == equity[0]
    assert provenance["metric_basis"]["anchor_ts"] == frame["ts"][0].isoformat()

    without_basis = alpha(home, *args, "--json").json()
    assert without_basis == {
        **payload,
        "provenance": {key: value for key, value in provenance.items() if key != "metric_basis"},
    }
    at_99 = alpha(home, *args, "--json", "--confidence", "0.99").json()
    for actual, expected in zip(at_99["scenarios"], _recompute(equity, 0.99), strict=True):
        for metric in ("value_at_risk", "expected_shortfall"):
            assert actual[metric] == pytest.approx(expected[metric], abs=1e-12, rel=0)

    text = alpha(home, *args).stdout
    scenario_lines = [line for line in text.splitlines() if ": vol=" in line]
    assert [line.split(": vol=", 1)[0].strip() for line in scenario_lines] == _SCENARIO_NAMES
    assert "Anchor: first recorded equity" in text
    assert (
        "Shock scenarios append one day of -3 or -5 sample standard deviations after the last "
        "recorded return; the drawdown changes only if that day deepens one."
    ) in text
    alpha(home, *args, "--include-metric-basis", expect=2)


def test_workstation_serves_the_same_risk_payload(
    backtest_home: BacktestHome, tmp_path: Path
) -> None:
    home = copy_home(backtest_home.home, tmp_path)
    run_id = backtest_home.run_id
    payload = alpha(
        home, "risk", "scenario", "--from-run", run_id, "--json", "--include-metric-basis"
    ).json()
    with web_server(home) as base:
        assert (
            get_json(f"{base}/api/risk/scenario?run_id={run_id}&include_metric_basis=true")
            == payload
        )
        with pytest.raises(HTTPError) as unknown:
            get_json(f"{base}/api/risk/scenario?run_id=deadbeefdeadbeef")
        assert unknown.value.code == 404
        unknown.value.close()
        with pytest.raises(HTTPError) as invalid_confidence:
            get_json(f"{base}/api/risk/scenario?run_id={run_id}&confidence=1.2")
        assert invalid_confidence.value.code == 422
        invalid_confidence.value.close()


def test_validation_run_risk_names_its_snapshot(data_home: Path, tmp_path: Path) -> None:
    home = copy_home(data_home, tmp_path)
    ran = alpha(home, "validate", "SPY", *STRATEGY, *_GAUNTLET, "--snapshot", SNAPSHOT)
    match = re.search(r"-> run ([0-9a-f]{16}):", ran.stdout)
    assert match, ran.report()
    run_id = match.group(1)
    manifest = json.loads((home / "data" / "runs" / run_id / "manifest.json").read_text())
    payload = alpha(
        home, "risk", "scenario", "--from-run", run_id, "--json", "--include-metric-basis"
    ).json()

    assert payload["provenance"]["source_command"] == "validate"
    assert payload["provenance"]["snapshot_id"] == SNAPSHOT
    base = payload["scenarios"][0]
    assert base["name"] == "base"
    for metric in (
        "sharpe",
        "value_at_risk",
        "expected_shortfall",
        "max_drawdown",
        "total_return",
    ):
        assert base[metric] == pytest.approx(manifest["oos_metrics"][metric], abs=1e-12, rel=0)


def test_rewritten_equity_is_refused_before_any_figure(
    backtest_home: BacktestHome, tmp_path: Path
) -> None:
    """A run's equity cannot be swapped after the fact: the artifact contract refuses it first.

    The timestamp-order and finiteness checks inside ``risk scenario`` sit behind this integrity
    check, so they are proven in-process (tests/integration/test_risk_equity_clocks.py); here the
    installed program must refuse a rewritten file, disordered or non-finite, and print no figure.
    """
    home = copy_home(backtest_home.home, tmp_path)
    equity_path = home / "data" / "runs" / backtest_home.run_id / "equity_curve.parquet"
    frame = pl.read_parquet(equity_path)
    equity_path.chmod(equity_path.stat().st_mode | 0o200)
    args = ("risk", "scenario", "--from-run", backtest_home.run_id, "--json")

    timestamps = frame["ts"].to_list()
    timestamps[1] = timestamps[0]
    frame.with_columns(pl.Series("ts", timestamps, dtype=frame.schema["ts"])).write_parquet(
        equity_path
    )
    disordered = alpha(home, *args, expect=2)
    assert "equity_curve.parquet" in disordered.stderr, disordered.report()
    assert "mismatch" in disordered.stderr, disordered.report()
    assert "scenarios" not in disordered.stdout

    equity = frame["equity"].to_list()
    equity[1] = float("inf")
    frame.with_columns(pl.Series("equity", equity)).write_parquet(equity_path)
    broken = alpha(home, *args, expect=2)
    assert "mismatch" in broken.stderr, broken.report()
    assert "scenarios" not in broken.stdout
