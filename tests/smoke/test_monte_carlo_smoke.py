"""Classical path-risk evidence through installed programs and independent arithmetic."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from statistics import NormalDist

import numpy as np
import polars as pl
import pytest

from tests.smoke._harness import Ran, alpha
from tests.smoke.conftest import SNAPSHOT, STRATEGY, BacktestHome, copy_home
from tests.smoke.test_validation_smoke import _GAUNTLET

pytestmark = [pytest.mark.smoke, pytest.mark.usefixtures("owned_test_process")]

_RUN_LINE = re.compile(r"-> run ([0-9a-f]{16}):")


def _run_id(ran: Ran) -> str:
    match = _RUN_LINE.search(ran.stdout)
    assert match, ran.report()
    return match.group(1)


def test_classical_monte_carlo_is_published_and_recomputes_independently(
    data_home: Path, tmp_path: Path
) -> None:
    home = copy_home(data_home, tmp_path)
    source_id = _run_id(
        alpha(home, "validate", "SPY", *STRATEGY, *_GAUNTLET, "--snapshot", SNAPSHOT)
    )
    args = (
        "monte-carlo", "classical", "--from-run", source_id, "--paths", "400",
        "--seed", "19", "--regime-window", "10", "--min-state-observations", "10",
        "--min-state-transitions", "5",
    )  # fmt: skip
    ran = alpha(home, *args)
    run_id = _run_id(ran)
    run_dir = home / "data" / "runs" / run_id
    for artifact in (
        "manifest.json",
        "paths.parquet",
        "path_metrics.parquet",
        "observed_oos.parquet",
        "regime_diagnostics.parquet",
        "regime_emissions.parquet",
        "report.md",
    ):
        assert (run_dir / artifact).is_file(), artifact
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["command"] == "monte_carlo_classical"
    assert manifest["source_run_id"] == source_id
    equity = pl.read_parquet(home / "data" / "runs" / source_id / "equity_curve.parquet")[
        "equity"
    ].to_numpy()
    observed = pl.read_parquet(run_dir / "observed_oos.parquet")["equity"].to_numpy()
    np.testing.assert_array_equal(observed, equity)
    horizon = len(equity) - 1
    source_returns = equity[1:] / equity[:-1] - 1.0
    assert manifest["horizon"] == horizon
    assert {row["family"] for row in manifest["families"]} == {
        "iid_empirical",
        "regime_switching",
        "student_t",
    }
    assert len(manifest["families"]) == 3
    paths = pl.read_parquet(run_dir / "paths.parquet")
    metrics = pl.read_parquet(run_dir / "path_metrics.parquet")
    assert paths.height == 3 * 400 * horizon
    assert metrics.height == 3 * 400
    for family in manifest["families"]:
        name = family["family"]
        line = next(line for line in ran.stdout.splitlines() if line.startswith(f"  {name}:"))
        assert "median terminal" in line
        assert family["n_paths"] == 400
        assert family["horizon"] == horizon
        family_paths = paths.filter(pl.col("family") == name).sort("path_index", "step")
        returns = family_paths["account_return"].to_numpy().reshape(400, horizon)
        np.testing.assert_array_equal(
            family_paths["path_index"].to_numpy(), np.repeat(np.arange(400), horizon)
        )
        np.testing.assert_array_equal(
            family_paths["step"].to_numpy(), np.tile(np.arange(horizon), 400)
        )
        if name in {"iid_empirical", "regime_switching"}:
            assert np.isin(returns, source_returns).all()
        wealth = np.concatenate((np.ones((400, 1)), np.cumprod(1.0 + returns, axis=1)), axis=1)
        terminal = wealth[:, -1] - 1.0
        drawdown = np.max(1.0 - wealth / np.maximum.accumulate(wealth, axis=1), axis=1)
        streaks = []
        for path in returns:
            current = longest = 0
            for value in path:
                current = current + 1 if value < 0.0 else 0
                longest = max(longest, current)
            streaks.append(longest)
        for field, values, quantile in (
            ("terminal_return_q05", terminal, 0.05),
            ("terminal_return_q50", terminal, 0.50),
            ("terminal_return_q95", terminal, 0.95),
            ("maximum_drawdown_q50", drawdown, 0.50),
            ("maximum_drawdown_q95", drawdown, 0.95),
            ("longest_loss_streak_q95", streaks, 0.95),
        ):
            assert family[field] == pytest.approx(
                float(np.quantile(values, quantile)), abs=1e-12, rel=0.0
            )
        per_path = metrics.filter(pl.col("family") == name).sort("path_index")
        np.testing.assert_array_equal(per_path["path_index"].to_numpy(), np.arange(400))
        for field, expected in (("terminal_return", terminal), ("maximum_drawdown", drawdown)):
            np.testing.assert_allclose(per_path[field].to_numpy(), expected, atol=1e-12, rtol=0.0)
        np.testing.assert_array_equal(per_path["longest_loss_streak"].to_numpy(), streaks)
        for field, outcomes, column in (
            ("loss_probability", terminal < 0.0, "loss"),
            ("ruin_probability", drawdown >= 0.5, "ruined"),
        ):
            np.testing.assert_array_equal(per_path[column].to_numpy(), outcomes)
            interval = family[field]
            successes = int(np.sum(outcomes))
            n = len(outcomes)
            point = successes / n
            confidence = manifest["confidence"]
            z = NormalDist().inv_cdf(1.0 - (1.0 - confidence) / 2.0)
            denominator = 1.0 + z * z / n
            center = (point + z * z / (2.0 * n)) / denominator
            half_width = z * math.sqrt(point * (1.0 - point) / n + z * z / (4.0 * n * n))
            half_width /= denominator
            assert interval["successes"] == successes
            assert interval["trials"] == n
            assert interval["confidence"] == confidence
            for key, expected in (
                ("point", point),
                ("lower", max(0.0, center - half_width)),
                ("upper", min(1.0, center + half_width)),
            ):
                assert interval[key] == pytest.approx(expected, abs=1e-12, rel=0.0)

    emissions = pl.read_parquet(run_dir / "regime_emissions.parquet").sort("step")
    states = emissions["state"].to_numpy()
    diagnostics = manifest["regime_diagnostics"]
    assert [int(np.sum(states == state)) for state in (0, 1)] == diagnostics["state_observations"]
    counts = np.zeros((2, 2), dtype=np.int64)
    for current, following in zip(states[:-1], states[1:], strict=True):
        counts[current, following] += 1
    np.testing.assert_allclose(
        diagnostics["transition_matrix"],
        counts / counts.sum(axis=1, keepdims=True),
        atol=1e-12,
        rtol=0.0,
    )
    report = alpha(home, "report", run_id).stdout
    iid = next(row for row in manifest["families"] if row["family"] == "iid_empirical")
    iid_line = next(line for line in report.splitlines() if "family[iid_empirical]:" in line)
    assert f"median_terminal={iid['terminal_return_q50']:.4f}" in iid_line
    figures = alpha(home, "figures", "render", run_id, "--json").json()
    assert figures["failed"] == []
    assert {row["figure_id"] for row in figures["figures"]} == {
        "monte_carlo_equity_fans",
        "monte_carlo_terminal_returns",
        "monte_carlo_drawdown_ruin",
        "monte_carlo_regimes",
    }
    before = (run_dir / "paths.parquet").read_bytes()
    assert _run_id(alpha(home, *args)) == run_id
    assert (run_dir / "paths.parquet").read_bytes() == before
    different_seed = list(args)
    different_seed[different_seed.index("--seed") + 1] = "20"
    assert _run_id(alpha(home, *different_seed)) != run_id


def test_monte_carlo_refuses_a_backtest_source(backtest_home: BacktestHome, tmp_path: Path) -> None:
    home = copy_home(backtest_home.home, tmp_path)
    runs = home / "data" / "runs"
    before = set(runs.iterdir())
    refused = alpha(home, "monte-carlo", "classical", "--from-run", backtest_home.run_id, expect=2)
    assert "must be a completed validate run" in refused.stdout + refused.stderr
    assert set(runs.iterdir()) == before
