"""``alpha_strategies.rules`` — strict parsing, canonical bytes and stateless evaluation."""

from __future__ import annotations

import json

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import OHLCV
from alpha_strategies.rules import (
    RuleSpec,
    canonical_json,
    evaluate_rules,
    parse_rule_spec,
    rule_signal,
    rule_spec_from_json,
    spec_sha256,
    trailing_ohlcv,
)


def sma(window: int) -> dict[str, object]:
    return {"indicator": "sma", "params": [window]}


TREND = {
    "name": "trend",
    "history": 40,
    "long_when": [{"left": sma(5), "op": ">", "right": sma(20)}],
    "short_when": [{"left": sma(5), "op": "<", "right": sma(20)}],
}


def _series(closes: list[float]) -> OHLCV:
    return trailing_ohlcv(closes, closes, closes, history=len(closes))


def test_parse_fills_defaults_and_computes_warmup() -> None:
    spec = parse_rule_spec(
        {"name": "x", "long_when": [{"left": {"source": "close"}, "op": ">", "right": sma(20)}]}
    )
    assert spec.version == 1 and spec.warmup == 20 and spec.history == 80  # 4 × warmup
    rsi_spec = parse_rule_spec(
        {
            "name": "x",
            "long_when": [
                {"left": {"indicator": "rsi", "params": [14]}, "op": "<", "right": {"value": 30}}
            ],
        }
    )
    assert rsi_spec.warmup == 15 and rsi_spec.history == 60  # RSI needs window+1; floor 60
    macd_spec = parse_rule_spec(
        {
            "name": "x",
            "long_when": [
                {
                    "left": {"indicator": "macd", "params": [12, 26, 9], "field": "histogram"},
                    "op": ">",
                    "right": {"value": 0},
                }
            ],
        }
    )
    assert macd_spec.warmup == 34


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("nope", "must be an object"),
        ({"name": "x", "long_when": [], "short_when": []}, "at least one condition"),
        ({"long_when": [{"left": sma(5), "op": ">", "right": sma(20)}]}, "non-empty 'name'"),
        (
            {"name": "x", "extra": 1, "long_when": [{"left": sma(5), "op": ">", "right": sma(20)}]},
            "unknown keys",
        ),
        (
            {
                "name": "x",
                "version": 2,
                "long_when": [{"left": sma(5), "op": ">", "right": sma(20)}],
            },
            "version must be 1",
        ),
        (
            {"name": "x", "long_when": [{"left": sma(5), "op": "crosses_above", "right": sma(20)}]},
            "op must be one of",
        ),
        (
            {"name": "x", "long_when": [{"left": {"value": 1}, "op": ">", "right": {"value": 2}}]},
            "two constants",
        ),
        (
            {
                "name": "x",
                "long_when": [{"left": {"source": "volume"}, "op": ">", "right": {"value": 2}}],
            },
            "source must be one of",
        ),
        (
            {
                "name": "x",
                "long_when": [
                    {"left": {"indicator": "vwap", "params": [5]}, "op": ">", "right": {"value": 2}}
                ],
            },
            "indicator must be one of",
        ),
        (
            {
                "name": "x",
                "long_when": [
                    {
                        "left": {"indicator": "sma", "params": [5, 6]},
                        "op": ">",
                        "right": {"value": 2},
                    }
                ],
            },
            "takes 1 parameter",
        ),
        (
            {
                "name": "x",
                "long_when": [
                    {"left": {"indicator": "sma", "params": [1]}, "op": ">", "right": {"value": 2}}
                ],
            },
            ">= 2",
        ),
        (
            {
                "name": "x",
                "long_when": [
                    {
                        "left": {"indicator": "sma", "params": [2.5]},
                        "op": ">",
                        "right": {"value": 2},
                    }
                ],
            },
            "whole number",
        ),
        (
            {
                "name": "x",
                "long_when": [
                    {
                        "left": {"indicator": "bbands", "params": [20, 0]},
                        "op": ">",
                        "right": {"value": 2},
                    }
                ],
            },
            "width",
        ),
        (
            {
                "name": "x",
                "long_when": [
                    {
                        "left": {"indicator": "bbands", "params": [20, 2]},
                        "op": ">",
                        "right": {"value": 2},
                    }
                ],
            },
            "needs field",
        ),
        (
            {
                "name": "x",
                "long_when": [
                    {
                        "left": {"indicator": "sma", "params": [20], "field": "upper"},
                        "op": ">",
                        "right": {"value": 2},
                    }
                ],
            },
            "drop 'field'",
        ),
        (
            {
                "name": "x",
                "long_when": [
                    {
                        "left": {"indicator": "macd", "params": [26, 12, 9], "field": "line"},
                        "op": ">",
                        "right": {"value": 2},
                    }
                ],
            },
            "fast window",
        ),
        (
            {
                "name": "x",
                "history": 10,
                "long_when": [{"left": sma(5), "op": ">", "right": sma(20)}],
            },
            "history must be",
        ),
        (
            {
                "name": "x",
                "history": 5000,
                "long_when": [{"left": sma(5), "op": ">", "right": sma(20)}],
            },
            "history must be",
        ),
        (
            {"name": "x", "long_when": [{"left": sma(5), "op": ">", "right": sma(20)}] * 13},
            "limit is 12",
        ),
        (
            {"name": "x", "long_when": [{"left": sma(5), "op": ">", "right": sma(20), "and": []}]},
            "unknown keys",
        ),
        (
            {
                "name": "x",
                "long_when": [{"left": {"value": float("nan")}, "op": ">", "right": sma(20)}],
            },
            "finite",
        ),
    ],
)
def test_parse_rejects_every_defect_with_its_path(payload: object, message: str) -> None:
    with pytest.raises(DataError, match=message):
        parse_rule_spec(payload)


def test_canonical_json_is_order_independent_and_hashes_stably() -> None:
    spec = parse_rule_spec(TREND)
    shuffled = parse_rule_spec(
        {
            "short_when": TREND["short_when"],
            "long_when": TREND["long_when"],
            "history": 40,
            "name": "trend",
        }
    )
    assert canonical_json(spec) == canonical_json(shuffled)
    assert spec_sha256(spec) == spec_sha256(shuffled)
    assert json.loads(canonical_json(spec))["long_when"][0]["left"] == {
        "indicator": "sma",
        "params": [5],
    }
    assert rule_spec_from_json(canonical_json(spec)) == spec
    with pytest.raises(DataError, match="not valid JSON"):
        rule_spec_from_json("{")


def test_labels_read_like_the_builder_rows() -> None:
    spec = parse_rule_spec(
        {
            "name": "x",
            "long_when": [
                {
                    "left": {"indicator": "bbands", "params": [20, 2.5], "field": "lower"},
                    "op": ">=",
                    "right": {"source": "close"},
                }
            ],
        }
    )
    assert spec.long_when[0].label == "bbands:20:2.5:lower >= close"


def test_evaluate_is_long_short_or_flat_on_conflict() -> None:
    spec = parse_rule_spec(TREND)
    up = [100.0 + i for i in range(40)]
    down = [140.0 - i for i in range(40)]
    assert evaluate_rules(spec, _series(up)) == 1
    assert evaluate_rules(spec, _series(down)) == -1
    flat = RuleSpec(name="flat", long_when=spec.long_when, short_when=spec.long_when, history=40)
    assert evaluate_rules(flat, _series(up)) == 0  # both sides hold → conflict → flat
    long_only = RuleSpec(name="lo", long_when=spec.long_when, short_when=(), history=40)
    assert evaluate_rules(long_only, _series(down)) == 0


def test_evaluate_requires_exactly_the_declared_history() -> None:
    spec = parse_rule_spec(TREND)
    with pytest.raises(DataError, match="exactly 40 trailing bars, got 39"):
        evaluate_rules(spec, _series([100.0 + i for i in range(39)]))
    with pytest.raises(DataError, match="need 40 bars of history, have 30"):
        rule_signal(spec, [1.0] * 30, [1.0] * 30, [1.0] * 30)


def test_warmup_value_on_the_decision_bar_is_a_typed_error_not_a_zero() -> None:
    spec = RuleSpec(
        name="x",
        long_when=parse_rule_spec(TREND).long_when,
        short_when=(),
        history=10,  # shorter than the 20-bar SMA: the operand is still NaN on the last bar
    )
    with pytest.raises(DataError, match="no finite value on the decision bar"):
        evaluate_rules(spec, _series([100.0 + i for i in range(10)]))


def test_trailing_ohlcv_keeps_bars_consistent_and_uses_only_the_window() -> None:
    closes = [100.0 + i for i in range(50)]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    window = trailing_ohlcv(highs, lows, closes, history=40)
    assert len(window) == 40 and window.close[0] == closes[10]
    assert np.all(window.high >= window.close) and np.all(window.low <= window.close)
    with pytest.raises(DataError, match="same length"):
        trailing_ohlcv(highs[:-1], lows, closes, history=40)
    with pytest.raises(DataError, match="high is below its low"):
        trailing_ohlcv(lows, highs, closes, history=40)  # swapped: never silently repaired


def test_default_history_is_bounded() -> None:
    from alpha_strategies.rules import MAX_HISTORY, default_history

    assert default_history(5) == 60 and default_history(100) == 400
    assert default_history(600) == MAX_HISTORY
    spec = parse_rule_spec(
        {"name": "x", "long_when": [{"left": {"source": "close"}, "op": ">", "right": sma(600)}]}
    )
    assert spec.history == MAX_HISTORY
