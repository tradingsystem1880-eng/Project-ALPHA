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
    a = parse_strategy_params("ma_crossover", ["slow=50", "fast=10"])
    b = parse_strategy_params("ma_crossover", ["fast=10", "slow=50"])
    assert a == b == (("fast", 10.0), ("slow", 50.0))
    assert parse_strategy_params("ts_momentum", None) == ()
    assert parse_strategy_params("ts_momentum", []) == ()


def test_parse_strategy_params_fails_loud_on_malformed() -> None:
    with pytest.raises(DataError):
        parse_strategy_params("ma_crossover", ["nope"])
    with pytest.raises(DataError):
        parse_strategy_params("ma_crossover", ["=5"])
    with pytest.raises(DataError):
        parse_strategy_params("ma_crossover", ["fast=abc"])


@pytest.mark.parametrize(
    ("strategy", "item", "message"),
    [
        ("ma_crossover", "fast=2.5", "integer"),
        ("ma_crossover", "fast=nan", "finite"),
        ("ma_crossover", "fast=inf", "finite"),
        ("ma_crossover", "fast=0", "minimum"),
        ("mean_reversion", "entry_z=0", "greater than"),
        ("kronos", "top_p=1.01", "maximum"),
        ("kronos", "band=2", "maximum"),
    ],
)
def test_parse_strategy_params_enforces_schema(strategy: str, item: str, message: str) -> None:
    with pytest.raises(DataError, match=message):
        parse_strategy_params(strategy, [item])


def test_parse_strategy_params_rejects_duplicate_and_unknown_names() -> None:
    with pytest.raises(DataError, match="duplicate"):
        parse_strategy_params("ma_crossover", ["fast=10", "fast=11"])
    with pytest.raises(DataError, match="unknown"):
        parse_strategy_params("ma_crossover", ["fasst=10"])
    with pytest.raises(DataError, match="unknown strategy"):
        parse_strategy_params("nope", [])


def test_valid_param_serialization_is_unchanged() -> None:
    assert parse_strategy_params("mean_reversion", ["entry_z=1.5", "window=20"]) == (
        ("entry_z", 1.5),
        ("window", 20.0),
    )


def test_unknown_strategy_param_fails_loud() -> None:
    # A typo'd --param was silently ignored, attributing results to a knob never applied.
    import pytest

    from alpha_cli._strategies import build_strategy, surrogate_for, warmup_for
    from alpha_core import DataError

    spec = _spec(strategy_name="mean_reversion", strategy_params=(("windoww", 10.0),))
    with pytest.raises(DataError, match="windoww"):
        warmup_for(spec)
    with pytest.raises(DataError, match="known strategy params"):
        surrogate_for(spec)
    with pytest.raises(DataError, match="windoww"):
        build_strategy(spec, None, None)  # fails at validation, before construction
    # a VALID param passes validation
    ok = _spec(strategy_name="mean_reversion", strategy_params=(("window", 10.0),))
    assert warmup_for(ok) > 0
    ts = _spec(strategy_name="ts_momentum", strategy_params=(("anything", 1.0),))
    with pytest.raises(DataError, match="first-class"):
        warmup_for(ts)


def test_cash_sizing_capital_reserves_friction_headroom() -> None:
    # CASH boundary fills consume notional*(1+slip)*(1+fee); sizing must reserve that headroom
    # (nautilus otherwise stops the run on the negative balance - see the engine guard test).
    from alpha_cli._strategies import _sizing_capital

    cash = _spec(account_type="CASH", allow_short=False, fee_bps=1.0, slippage_bps=2.0)
    expected = 100_000.0 / ((1.0 + 0.0002) * (1.0 + 0.0001))
    assert _sizing_capital(cash) == pytest.approx(expected)
    margin = _spec(account_type="MARGIN", fee_bps=1.0, slippage_bps=2.0)
    assert _sizing_capital(margin) == 100_000.0
