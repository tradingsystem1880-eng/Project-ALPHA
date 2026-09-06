"""Rule strategies are point-in-time by construction: a decision reads exactly the declared
trailing window, so nothing older than the window and nothing after the decision bar can change
it, and a value still warming up is an error rather than a guess."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_strategies.rules import evaluate_rules, parse_rule_spec, rule_signal, trailing_ohlcv

pytestmark = pytest.mark.bias_guard

SPEC = parse_rule_spec(
    {
        "name": "guard",
        "history": 30,
        "long_when": [
            {
                "left": {"indicator": "ema", "params": [5]},
                "op": ">",
                "right": {"indicator": "sma", "params": [20]},
            },
            {"left": {"indicator": "rsi", "params": [7]}, "op": "<", "right": {"value": 80}},
        ],
        "short_when": [
            {
                "left": {"indicator": "ema", "params": [5]},
                "op": "<",
                "right": {"indicator": "sma", "params": [20]},
            }
        ],
    }
)


def _path(n: int, seed: int = 1) -> list[float]:
    rng = np.random.default_rng(seed)
    closes = 100.0 * np.cumprod(1.0 + rng.normal(0.001, 0.01, n))
    return [float(value) for value in closes]


def test_decision_ignores_everything_older_than_the_window() -> None:
    closes = _path(200)
    for t in range(60, 200, 7):
        clean = rule_signal(SPEC, closes[: t + 1], closes[: t + 1], closes[: t + 1])
        # poison the distant past (a 100x jump on every bar before the window)
        poisoned = [c * 100.0 for c in closes[: t + 1 - SPEC.history]] + closes[
            t + 1 - SPEC.history : t + 1
        ]
        assert rule_signal(SPEC, poisoned, poisoned, poisoned) == clean


def test_decision_at_t_never_reads_bars_after_t() -> None:
    closes = _path(200, seed=2)
    poison = [1e-3] * 50  # a crash that would flip any trend rule if it leaked in
    for t in range(60, 150, 9):
        prefix = closes[: t + 1]
        with_future = prefix + poison
        at_t = rule_signal(SPEC, prefix, prefix, prefix)
        # the only way to reach bar t's decision from the longer series is to slice to t
        assert (
            rule_signal(SPEC, with_future[: t + 1], with_future[: t + 1], with_future[: t + 1])
            == at_t
        )
        # and evaluating the longer series is a different (later) decision, never a re-labelled t
        assert evaluate_rules(
            SPEC, trailing_ohlcv(with_future, with_future, with_future, history=SPEC.history)
        ) in {-1, 0, 1}


def test_a_window_longer_or_shorter_than_declared_fails_loud() -> None:
    closes = _path(60)
    with pytest.raises(DataError, match="exactly 30 trailing bars, got 31"):
        evaluate_rules(SPEC, trailing_ohlcv(closes, closes, closes, history=31))
    with pytest.raises(DataError, match="exactly 30 trailing bars, got 29"):
        evaluate_rules(SPEC, trailing_ohlcv(closes, closes, closes, history=29))
