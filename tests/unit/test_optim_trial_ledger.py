"""Failure-complete deterministic grid outcomes and ledger round trips."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from alpha_cli import _optim
from alpha_cli._runner import RunSpec
from alpha_core import Bar, DataError


def _bars(n: int = 90) -> list[Bar]:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    return [
        Bar(
            symbol="SPY",
            ts=start + timedelta(days=index),
            open=100.0 + index,
            high=101.0 + index,
            low=99.0 + index,
            close=100.5 + index,
            volume=1_000.0,
        )
        for index in range(n)
    ]


def _base() -> RunSpec:
    return RunSpec(
        lookback=3,
        skip=1,
        vol_window=3,
        target_vol=0.15,
        rebalance_every=2,
        max_leverage=1.0,
        allow_short=False,
        periods_per_year=252,
        fee_bps=0.0,
        slippage_bps=0.0,
        starting_cash=100_000.0,
        account_type="CASH",
        train_size=15,
        test_size=5,
        embargo=1,
        anchored=False,
    )


def _returns_for(task: _optim._ConfigTask) -> np.ndarray:
    if task.spec.lookback == 7:
        raise DataError("deliberate configuration failure")
    offset = task.spec.lookback * 0.00001
    return (
        np.asarray(
            [
                0.01,
                -0.004,
                0.006,
                -0.002,
                0.008,
                -0.003,
                0.005,
                -0.001,
                0.007,
                -0.002,
                0.004,
                0.003,
            ],
            dtype=np.float64,
        )
        + offset
    )


def test_grid_retains_ordered_success_and_failure_outcomes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_optim, "_oos_returns_for", _returns_for)

    result = _optim.run_optimization(
        _bars(),
        _base(),
        {"lookback": [3, 5, 7]},
        pbo_blocks=6,
        n_resamples=40,
        seed=7,
    )

    assert [outcome.trial_index for outcome in result.outcomes] == [0, 1, 2]
    assert [outcome.status for outcome in result.outcomes] == ["passed", "passed", "failed"]
    assert result.outcomes[2].error == "DataError: deliberate configuration failure"
    assert result.outcomes[2].oos_returns == ()
    assert result.successful_trial_indices == (0, 1)
    assert result.oos_matrix.shape == (12, 2)
    assert result.sharpes.shape == (3,)
    assert np.isnan(result.sharpes[2])
    assert result.analysis_error is None


def test_invalid_config_is_rejected_without_hiding_other_trials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_optim, "_oos_returns_for", _returns_for)

    result = _optim.run_optimization(
        _bars(),
        _base(),
        {"lookback": [3, 5.5, 5]},
        pbo_blocks=6,
        n_resamples=40,
        seed=7,
    )

    assert [outcome.status for outcome in result.outcomes] == ["passed", "rejected", "passed"]
    assert "integer-valued" in (result.outcomes[1].error or "")
    assert result.successful_trial_indices == (0, 2)


def test_insufficient_successes_return_explicit_failed_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def one_success(task: _optim._ConfigTask) -> np.ndarray:
        if task.spec.lookback == 5:
            raise DataError("unrunnable trial")
        return _returns_for(task)

    monkeypatch.setattr(_optim, "_oos_returns_for", one_success)
    result = _optim.run_optimization(
        _bars(),
        _base(),
        {"lookback": [3, 5]},
        pbo_blocks=6,
        n_resamples=40,
        seed=7,
    )

    assert result.passed is False
    assert result.analysis_error == (
        "optimization analysis requires >= 2 successful aligned configs, got 1 of 2"
    )
    assert result.dsr is None
    assert result.pbo is None
    assert result.reality_check is None
    assert result.spa is None
    assert result.oos_matrix.shape == (12, 1)


def test_trial_ledger_is_deterministic_and_round_trips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_optim, "_oos_returns_for", _returns_for)
    result = _optim.run_optimization(
        _bars(),
        _base(),
        {"lookback": [3, 5, 7]},
        pbo_blocks=6,
        n_resamples=40,
        seed=7,
    )
    rdir = tmp_path / "0123456789abcdef"

    _optim.write_trial_ledger(rdir, result.outcomes)
    first = (rdir / "trial_ledger.parquet").read_bytes()
    _optim.write_trial_ledger(rdir, result.outcomes)

    assert (rdir / "trial_ledger.parquet").read_bytes() == first
    restored = _optim.read_trial_ledger(rdir)
    assert [row.status for row in restored] == ["passed", "passed", "failed"]
    assert restored[0].config == (("lookback", 3.0),)
    assert restored[0].oos_returns == result.outcomes[0].oos_returns
    assert restored[2].error == "DataError: deliberate configuration failure"
