"""Strategy registry dispatch (``alpha_cli._strategies``) + per-strategy param parsing.

Pins that a ``RunSpec`` resolves to its strategy's warmup/surrogate seams, that an unknown strategy
fails loud rather than silently defaulting, and that repeatable ``--param name=value`` options parse
into the spec's fixed, order-independent shape.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_cli import _strategies
from alpha_cli._runner import RunSpec, parse_strategy_params
from alpha_core import DataError


def _spec(**overrides: object) -> RunSpec:
    base = dict(
        lookback=5,
        skip=1,
        vol_window=3,
        target_vol=0.15,
        rebalance_every=2,
        max_leverage=1.0,
        allow_short=True,
        periods_per_year=252,
        fee_bps=1.0,
        slippage_bps=2.0,
        starting_cash=100_000.0,
        account_type="CASH",
        train_size=15,
        test_size=5,
        embargo=1,
        anchored=False,
    )
    base.update(overrides)
    return RunSpec(**base)  # type: ignore[arg-type]


def test_ts_momentum_is_the_default_registered_strategy() -> None:
    assert "ts_momentum" in _strategies.known_strategies()
    assert _spec().strategy_name == "ts_momentum"


def test_warmup_for_matches_ts_momentum_formula() -> None:
    spec = _spec(lookback=10, skip=2, vol_window=20)
    assert _strategies.warmup_for(spec) == max(10 + 2 + 1, 20 + 1)
    assert spec.min_train == _strategies.warmup_for(spec)


def test_surrogate_for_runs_and_is_length_preserving() -> None:
    surrogate = _strategies.surrogate_for(_spec())
    returns = np.full(40, 0.01, dtype=np.float64)
    out = surrogate(returns)
    assert out.shape == returns.shape


def test_unknown_strategy_fails_loud() -> None:
    spec = _spec(strategy_name="does_not_exist")
    with pytest.raises(DataError):
        _strategies.warmup_for(spec)
    with pytest.raises(DataError):
        _strategies.surrogate_for(spec)


def test_param_reads_strategy_params_with_default() -> None:
    spec = _spec(strategy_params=(("entry_z", 2.0), ("window", 20.0)))
    assert spec.param("window", 99.0) == 20.0
    assert spec.param("entry_z", 99.0) == 2.0
    assert spec.param("absent", 99.0) == 99.0


def test_parse_strategy_params_sorts_and_is_order_independent() -> None:
    a = parse_strategy_params(["slow=50", "fast=10"])
    b = parse_strategy_params(["fast=10", "slow=50"])
    assert a == b == (("fast", 10.0), ("slow", 50.0))
    assert parse_strategy_params(None) == ()
    assert parse_strategy_params([]) == ()


def test_parse_strategy_params_fails_loud_on_malformed() -> None:
    with pytest.raises(DataError):
        parse_strategy_params(["nope"])
    with pytest.raises(DataError):
        parse_strategy_params(["=5"])
    with pytest.raises(DataError):
        parse_strategy_params(["fast=abc"])
