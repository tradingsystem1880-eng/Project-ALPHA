"""kronos_forecast registry wiring: params, warmup, surrogate skip, leakage warnings."""

from __future__ import annotations

import pytest

from alpha_cli._runner import RunSpec, parse_strategy_params
from alpha_cli._strategies import (
    has_tier1_surrogate,
    known_strategies,
    pre_run_warnings,
    surrogate_for,
    warmup_for,
)
from alpha_core import DataError
from tests.fixtures.forecast_fixtures import daily_bars


def _spec(*params: str, strategy_name: str = "kronos_forecast") -> RunSpec:
    return RunSpec(
        lookback=5,
        skip=1,
        vol_window=63,
        target_vol=0.15,
        rebalance_every=21,
        max_leverage=1.0,
        allow_short=True,
        periods_per_year=252,
        fee_bps=1.0,
        slippage_bps=2.0,
        starting_cash=100_000.0,
        account_type="CASH",
        train_size=504,
        test_size=63,
        embargo=5,
        anchored=False,
        strategy_name=strategy_name,
        strategy_params=parse_strategy_params(list(params)),
    )


def test_registered() -> None:
    assert "kronos_forecast" in known_strategies()


def test_warmup_is_max_of_context_and_vol_window() -> None:
    assert warmup_for(_spec("context=400")) == 400  # default vol_window 63
    assert warmup_for(_spec("context=10")) == 64  # vol_window + 1 dominates


def test_default_model_is_base_and_bounds_enforced() -> None:
    # base max_context is 512: context=600 must fail loud under the default model
    with pytest.raises(DataError, match=r"context=600 out of range \[2, 512\]"):
        warmup_for(_spec("context=600"))
    # mini (model=0) allows a 600-bar context (max 2048)
    assert warmup_for(_spec("model=0", "context=600")) == 600


def test_invalid_model_index_fails_loud() -> None:
    with pytest.raises(DataError, match="0=mini, 1=small, 2=base"):
        warmup_for(_spec("model=3"))


def test_bad_horizon_fails_loud() -> None:
    with pytest.raises(DataError, match="horizon"):
        warmup_for(_spec("horizon=0"))


def test_no_tier1_surrogate_is_explicit() -> None:
    spec = _spec()
    assert not has_tier1_surrogate(spec)
    with pytest.raises(DataError, match="no engine-free Tier-1 surrogate"):
        surrogate_for(spec)
    # the classical strategies still have one
    assert has_tier1_surrogate(_spec(strategy_name="ts_momentum"))


def test_pre_run_warnings_only_for_kronos_pre_cutoff() -> None:
    bars = daily_bars(n=10)  # fixture dates are 2026 -> post-cutoff
    assert pre_run_warnings(_spec(), bars) == []
    old = [b.model_copy(update={"ts": b.ts.replace(year=b.ts.year - 6)}) for b in bars]
    warnings = pre_run_warnings(_spec(), old)
    assert len(warnings) == 1 and "UPPER BOUND" in warnings[0]
    # other strategies never warn
    assert pre_run_warnings(_spec(strategy_name="ts_momentum"), old) == []
