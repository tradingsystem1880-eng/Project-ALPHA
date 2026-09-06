"""The rules strategy is part of run identity: the spec bytes are in the payload and the rule
modules are in the strategy fingerprint."""

from __future__ import annotations

import re

from alpha_cli import _identity, _runner
from alpha_cli._strategies import STRATEGIES, warmup_for
from alpha_strategies.rules import canonical_json, parse_rule_spec


def _spec(rules_spec: str | None) -> _runner.RunSpec:
    return _runner.RunSpec(
        lookback=10,
        skip=1,
        vol_window=10,
        target_vol=0.1,
        rebalance_every=1,
        max_leverage=1.0,
        allow_short=True,
        periods_per_year=252,
        fee_bps=1.0,
        slippage_bps=1.0,
        starting_cash=1e6,
        account_type="MARGIN",
        train_size=100,
        test_size=20,
        embargo=2,
        anchored=False,
        strategy_name="rules",
        rules_spec=rules_spec,
    )


def _rules(fast: int) -> str:
    sma_fast = {"indicator": "sma", "params": [fast]}
    sma_slow = {"indicator": "sma", "params": [20]}
    return canonical_json(
        parse_rule_spec(
            {
                "name": "t",
                "history": 40,
                "long_when": [{"left": sma_fast, "op": ">", "right": sma_slow}],
                "short_when": [{"left": sma_fast, "op": "<", "right": sma_slow}],
            }
        )
    )


def test_run_id_changes_with_the_rule_bytes_only() -> None:
    a = _runner.run_id_for({"command": "backtest_run", "symbol": "ZZ", **vars(_spec(_rules(5)))})
    b = _runner.run_id_for({"command": "backtest_run", "symbol": "ZZ", **vars(_spec(_rules(6)))})
    again = _runner.run_id_for(
        {"command": "backtest_run", "symbol": "ZZ", **vars(_spec(_rules(5)))}
    )
    assert a == again and a != b
    assert "rules_spec" in vars(_spec(_rules(5)))


def test_rules_modules_are_fingerprinted_and_patterns_is_an_execution_package() -> None:
    assert _identity._STRATEGY_MODULES["rules"] == ("rules.py", "rule_strategy.py")
    assert "alpha_patterns" in _identity._EXECUTION_PACKAGES
    fingerprint = _identity.strategy_fingerprint("rules")
    assert fingerprint is not None and re.fullmatch(r"[0-9a-f]{64}", fingerprint)
    assert fingerprint != _identity.strategy_fingerprint("breakout")


def test_tier1_surrogate_agrees_with_the_engine_rule_signal_bar_for_bar() -> None:
    """A close-only rule must decide identically in the surrogate and in the engine: the
    surrogate's weight sign at every rebalance bar equals ``rule_signal`` on the same closes."""
    import numpy as np

    from alpha_cli._strategies import surrogate_for
    from alpha_strategies.rules import rule_signal, rule_spec_from_json

    spec = _spec(_rules(5))
    rules = rule_spec_from_json(_rules(5))
    surrogate = surrogate_for(spec)
    rng = np.random.default_rng(11)
    pr = rng.normal(0.0005, 0.01, 300)
    weights, _costs = surrogate.weights_and_costs(pr)
    closes = np.concatenate([[1.0], np.cumprod(1.0 + pr)])
    warmup = spec.min_train - 1
    checked = 0
    for t in range(warmup, pr.size):  # rebalance_every=1: every bar after warm-up decides
        prefix = closes[: t + 1].tolist()
        expected = rule_signal(rules, prefix, prefix, prefix)
        assert int(np.sign(weights[t])) == expected, f"bar {t}"
        checked += 1
    assert checked > 200 and {int(np.sign(w)) for w in weights[warmup:]} >= {1, -1}


def test_rules_registry_entry_reads_the_spec_for_its_warmup() -> None:
    assert "rules" in STRATEGIES and STRATEGIES["rules"].params == frozenset()
    assert STRATEGIES["rules"].supports_live_paper is False
    assert warmup_for(_spec(_rules(5))) == 40  # history 40 > vol_window + 1
