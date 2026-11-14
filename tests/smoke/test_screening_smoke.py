"""Screen synthetic frozen prices through the installed CLI and recompute independently.

The pandas/SciPy calculation reads snapshot parquet directly; it does not use
alpha_cli or alpha_research calculations. It covers equity price screening, not
crypto inputs, universe memberships or corporate-action adjustment.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from scipy.stats import spearmanr

from tests.fixtures.cli_fixtures import seed_store
from tests.smoke._harness import alpha

pytestmark = [pytest.mark.smoke, pytest.mark.usefixtures("owned_test_process")]

SYMBOLS = ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF")
SCREEN_ARGS = (
    "scan", "hypotheses", "--symbols", ",".join(SYMBOLS), "--snapshot", "screen-v1",
    "--as-of", "2020-12-31", "--signals", "rev_1m,vol_63", "--horizons", "1,5",
    "--cost-bps", "10",
)  # fmt: skip


@pytest.fixture
def screening_home(tmp_path: Path) -> Path:
    """Use the labelled synthetic bars documented in smoke/conftest.py, without actions."""
    home = tmp_path / "home"
    home.mkdir()
    for i, symbol in enumerate(SYMBOLS):
        seed_store(
            home / "data",
            symbol=symbol,
            n=300,
            seed=i,
            sigma=0.01 + 0.002 * i,
            drift=0.0004 * (i - 2),
        )
    alpha(home, "data", "snapshot", "screen-v1", *SYMBOLS)
    alpha(home, "data", "verify", "screen-v1")
    return home


def _replacement_fraction(signal: pd.DataFrame, lag: int) -> float:
    fractions = []
    for t in range(len(signal) - lag):
        common = pd.concat(
            [signal.iloc[t].rename("before"), signal.iloc[t + lag].rename("after")], axis=1
        ).dropna()
        if len(common) < 5:
            continue
        width = len(common) // 5
        before = common["before"].sort_values(kind="stable").index
        after = common["after"].sort_values(kind="stable").index
        leavers = len(set(before[:width]) - set(after[:width])) + len(
            set(before[-width:]) - set(after[-width:])
        )
        fractions.append(leavers / (2 * width))
    assert fractions, "synthetic signal must have scorable turnover pairs"
    return float(pd.Series(fractions).mean())


def _independent_measurements(
    prices: pd.DataFrame, signal: pd.DataFrame, horizon: int
) -> dict[str, float | int]:
    outcomes = prices.shift(-horizon) / prices - 1
    correlations = []
    spreads = []
    for t in range(len(prices)):
        scored = pd.concat(
            [signal.iloc[t].rename("signal"), outcomes.iloc[t].rename("outcome")], axis=1
        ).dropna()
        if len(scored) < 5:
            continue
        correlations.append(float(spearmanr(scored["signal"], scored["outcome"]).statistic))
        ordered = scored.sort_values("signal", kind="stable")["outcome"]
        width = len(scored) // 5
        spreads.append(float(ordered.iloc[-width:].mean() - ordered.iloc[:width].mean()))
    assert correlations and spreads, "synthetic screen must have scorable dates"
    ic = pd.Series(correlations)
    spread = float(pd.Series(spreads).mean())
    turnover_h = _replacement_fraction(signal, horizon)
    return {
        "ic_mean": float(ic.mean()),
        "t_stat": float(ic.mean() / ic.std(ddof=1) * len(ic) ** 0.5),
        "n_dates": len(ic),
        "spread": spread,
        "turnover": _replacement_fraction(signal, 1),
        "horizon_turnover": turnover_h,
        "cost_adjusted_spread": spread - 4 * turnover_h * 10 / 1e4,
    }


def test_screen_is_recorded_replayed_and_recomputes_independently(screening_home: Path) -> None:
    home = screening_home
    result = alpha(home, *SCREEN_ARGS, "--json").json()
    assert result["trials"] == 4
    assert result["authority"] == "none"
    assert result["execution_authority"] is False
    assert result["missing"] == []
    assert len(result["results"]) == 4
    assert {(row["signal"], row["horizon"]) for row in result["results"]} == {
        (name, horizon) for name in ("rev_1m", "vol_63") for horizon in (1, 5)
    }

    scans = home / "data" / "scans" / "hypotheses"
    attempt = scans / "attempts" / result["attempt_id"]
    receipts = {}
    for name in ("started", "resolved", "result", "finished"):
        path = attempt / f"{name}.json"
        assert path.is_file()
        receipts[name] = json.loads(path.read_text())
        assert receipts[name]["attempt_id"] == result["attempt_id"]
        assert receipts[name]["authority"] == "none"
    assert receipts["started"]["status"] == "started"
    assert receipts["resolved"]["scan_id"] == result["scan_id"]
    assert receipts["resolved"]["planned_trials"] == 4
    assert receipts["result"] == result
    assert receipts["finished"]["status"] == "completed"
    assert receipts["finished"]["scan_id"] == result["scan_id"]
    assert receipts["finished"]["result_digest"] == result["result_digest"]
    assert (scans / "specs" / f"{result['scan_id']}.json").is_file()
    trial_paths = list((attempt / "trials").glob("*.json"))
    assert len(trial_paths) == 8
    trials = [json.loads(path.read_text()) for path in trial_paths]
    assert sorted((trial["trial_index"], trial["status"]) for trial in trials) == [
        (i, status) for i in range(4) for status in ("completed", "started")
    ]
    assert all(trial["attempt_id"] == result["attempt_id"] for trial in trials)
    assert all(trial["scan_id"] == result["scan_id"] for trial in trials)
    assert not (home / "data" / "runs").exists()
    assert not (home / "data" / "control").exists()

    closes = {}
    for symbol in SYMBOLS:
        bars = pd.read_parquet(
            home / "data" / "snapshots" / "screen-v1" / "bars" / f"{symbol}.parquet"
        )
        closes[symbol] = bars.set_index("ts")["close"].sort_index()
    prices = pd.DataFrame(closes).loc[:"2020-12-31"]
    assert prices.shape == (300, 6)
    assert prices.notna().all().all()
    signals = {
        "rev_1m": -(prices / prices.shift(21) - 1),
        "vol_63": prices.pct_change(fill_method=None).rolling(63).std(ddof=1),
    }
    for row in result["results"]:
        expected = _independent_measurements(prices, signals[row["signal"]], row["horizon"])
        actual = {
            "ic_mean": row["ic"]["mean"],
            "t_stat": row["ic"]["t_stat"],
            "spread": row["quantiles"]["spread"],
            "turnover": row["turnover"],
            "horizon_turnover": row["horizon_turnover"],
            "cost_adjusted_spread": row["cost_adjusted_spread"],
        }
        assert row["ic"]["n_dates"] == expected["n_dates"]
        assert row["quantiles"]["n_dates"] == expected["n_dates"]
        for key, value in actual.items():
            assert value == pytest.approx(expected[key], rel=0, abs=1e-12), (row, key)

    replayed = alpha(home, "scan", "replay", result["scan_id"], "--json").json()
    assert replayed["scan_id"] == result["scan_id"]
    assert replayed["result_digest"] == result["result_digest"]
    assert replayed["attempt_id"] != result["attempt_id"]
    text = alpha(home, *SCREEN_ARGS).stdout
    assert text.startswith(f"exploratory screen {result['scan_id']}: 4 trials; authority none\n")
    assert "signal      h    IC mean   t (plain)  dates   spread     cost-adj   turnover/h" in text
    for name in ("rev_1m", "vol_63"):
        assert sum(line.startswith(name) for line in text.splitlines()) == 2
    assert (
        "plain t statistics; horizons over 1 overlap and are not corrected; "
        "no selection adjustment over 4 trials"
    ) in text
    assert not (home / "data" / "runs").exists()
    assert not (home / "data" / "control").exists()


def test_screen_without_a_snapshot_is_refused_and_recorded(screening_home: Path) -> None:
    home = screening_home
    refused = alpha(
        home,
        "scan",
        "hypotheses",
        "--symbols",
        ",".join(SYMBOLS[:5]),
        "--as-of",
        "2020-12-31",
        expect=2,
    )
    assert "snapshot" in refused.stdout + refused.stderr, refused.report()
    attempts = list((home / "data" / "scans" / "hypotheses" / "attempts").iterdir())
    assert len(attempts) == 1
    assert json.loads((attempts[0] / "finished.json").read_text())["status"] == "failed"
