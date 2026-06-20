"""Prop-firm Monte Carlo simulator (QuantPad-style funded-trader evaluation).

``simulate_propfirm`` resamples a strategy's daily *return* series with the stationary
bootstrap and walks each synthetic path through a prop firm's EVAL → FUNDED → payout state
machine. It is return-scaled (applied to a configurable prop-account balance), seeded and
deterministic, and fails loud on degenerate input. The walk is end-of-day granularity — the
honest limit of a daily-bar backtest (intraday excursions are invisible).
"""

from __future__ import annotations

import dataclasses
import math

import pytest

from alpha_core import DataError
from alpha_validation import (
    FIRM_PRESETS,
    PropFirmResult,
    PropFirmRules,
    simulate_propfirm,
)


def _rules(**overrides: object) -> PropFirmRules:
    base: dict[str, object] = dict(
        account_size=50_000.0,
        profit_target=3_000.0,
        max_drawdown=2_000.0,
        trailing=True,
        lock_at_profit=None,
        daily_loss_limit=None,
        min_trading_days=1,
        profit_split=1.0,
        min_payout=1_000.0,
        min_funded_days=1,
        eval_fee=0.0,
    )
    base.update(overrides)
    return PropFirmRules(**base)  # type: ignore[arg-type]


def test_strong_edge_passes_often() -> None:
    # +1%/day on a 50k account clears a 6% ($3k) target in ~6 days; 0.5% vol rarely digs a 4% hole.
    rets = [0.01] * 80
    out = simulate_propfirm(rets, _rules(), n_paths=400, seed=7)
    assert isinstance(out, PropFirmResult)
    assert out.pass_probability > 0.8
    assert out.horizon_days == 80
    assert out.n_paths == 400


def test_negative_edge_busts_and_rarely_passes() -> None:
    rets = [-0.01] * 80  # steady bleed -> trips the 4% trailing drawdown, never reaches target
    out = simulate_propfirm(rets, _rules(), n_paths=400, seed=7)
    assert out.pass_probability < 0.1
    assert out.bust_probability > 0.5


def test_daily_loss_limit_busts_a_catastrophic_day() -> None:
    # A lone -5% day = -$2.5k on a 50k account. With a $1k daily-loss limit it busts whenever the
    # bootstrap lands that day; with no daily limit (and a roomy drawdown / unreachable target) the
    # same stream essentially never busts. Isolates the daily-loss rule.
    rets = [0.001] * 60
    rets[30] = -0.05
    loud = _rules(daily_loss_limit=1_000.0, max_drawdown=10_000.0, profit_target=100_000.0)
    quiet = _rules(daily_loss_limit=None, max_drawdown=10_000.0, profit_target=100_000.0)
    assert simulate_propfirm(rets, loud, n_paths=400, seed=7).bust_probability > 0.5
    assert simulate_propfirm(rets, quiet, n_paths=400, seed=7).bust_probability < 0.05


def test_trailing_drawdown_breach_busts() -> None:
    # Zero-drift +/-2% whipsaw against a tight 4% trailing drawdown and an unreachable target ->
    # only the drawdown can resolve the path, and on a random walk it usually does.
    rets = [(-0.02 if i % 2 else 0.02) for i in range(80)]
    out = simulate_propfirm(rets, _rules(profit_target=100_000.0), n_paths=400, seed=7)
    assert out.bust_probability > 0.5


def test_min_trading_days_blocks_an_early_pass() -> None:
    # Monotone +10%/day clears the $3k target on day 1; every resample is identical, so the only
    # thing gating the pass day is min_trading_days.
    rets = [0.10] * 30
    fast = simulate_propfirm(rets, _rules(min_trading_days=1), n_paths=10, seed=7)
    slow = simulate_propfirm(rets, _rules(min_trading_days=10), n_paths=10, seed=7)
    assert fast.pass_probability == 1.0 and slow.pass_probability == 1.0
    assert fast.median_days_to_pass == 1.0
    assert slow.median_days_to_pass == 10.0


def test_passing_path_accrues_expected_payout() -> None:
    # Monotone +10%/day: pass on day 1, then each funded day grows 50k->55k, withdraws the $5k
    # profit (reset to start), trader keeps 50%. 19 funded days -> 0.5 * 5_000 * 19 = 47_500.
    rets = [0.10] * 20
    out = simulate_propfirm(rets, _rules(profit_split=0.5), n_paths=10, seed=7)
    assert out.payout_probability == 1.0
    assert out.expected_payout == pytest.approx(47_500.0)


def test_eval_fee_is_netted_from_expected_payout() -> None:
    rets = [0.10] * 20
    free = simulate_propfirm(rets, _rules(profit_split=0.5, eval_fee=0.0), n_paths=10, seed=7)
    paid = simulate_propfirm(rets, _rules(profit_split=0.5, eval_fee=150.0), n_paths=10, seed=7)
    assert paid.expected_payout == pytest.approx(free.expected_payout - 150.0)


def test_deterministic_under_a_seed() -> None:
    rets = [0.01] * 80
    a = simulate_propfirm(rets, _rules(), n_paths=200, seed=7)
    b = simulate_propfirm(rets, _rules(), n_paths=200, seed=7)
    assert a == b  # finite median (some paths pass) -> full dataclass equality holds


def test_flat_stream_yields_zero_metrics() -> None:
    # No edge, no risk: the account never moves -> never passes, never busts, never pays out.
    out = simulate_propfirm([0.0] * 40, _rules(eval_fee=0.0), n_paths=100, seed=7)
    assert out.pass_probability == 0.0
    assert out.bust_probability == 0.0
    assert out.payout_probability == 0.0
    assert out.expected_payout == 0.0
    assert math.isnan(out.median_days_to_pass)


def test_simulate_fails_loud_on_degenerate_input() -> None:
    with pytest.raises(DataError):
        simulate_propfirm([0.01], _rules(), n_paths=10, seed=7)  # < 2 returns
    with pytest.raises(DataError):
        simulate_propfirm([0.01, math.nan], _rules(), n_paths=10, seed=7)  # non-finite


def test_rules_validate_their_invariants() -> None:
    with pytest.raises(DataError):
        _rules(account_size=-1.0)
    with pytest.raises(DataError):
        _rules(profit_split=1.5)  # must be in [0, 1]
    with pytest.raises(DataError):
        _rules(max_drawdown=0.0)  # must be > 0
    with pytest.raises(DataError):
        _rules(daily_loss_limit=0.0)  # None or > 0


def test_firm_presets_are_well_formed() -> None:
    assert {"topstep", "apex", "takeprofit"} <= set(FIRM_PRESETS)
    for name, rules in FIRM_PRESETS.items():
        assert isinstance(rules, PropFirmRules), name
        assert rules.account_size > 0 and rules.profit_target > 0 and rules.max_drawdown > 0
        assert 0.0 <= rules.profit_split <= 1.0


def test_result_is_frozen() -> None:
    out = simulate_propfirm([0.01] * 40, _rules(), n_paths=50, seed=7)
    with pytest.raises(dataclasses.FrozenInstanceError):
        out.pass_probability = 0.0  # type: ignore[misc]
