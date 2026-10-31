"""Hand-specified causal source-lag examples; these are artificial engineering fixtures."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_strategies.rules import (
    MAX_HISTORY,
    canonical_json,
    explain_rules,
    operand_series,
    parse_operand,
    parse_rule_spec,
    rule_signal,
    spec_sha256,
    trailing_ohlcv,
)


def _momentum(lag: object = 20, *, history: int = 21) -> dict[str, object]:
    return {
        "version": 1,
        "name": "twenty-day-long-or-flat",
        "history": history,
        "long_when": [
            {"left": {"source": "close"}, "op": ">", "right": {"source": "close", "lag": lag}}
        ],
        "short_when": [],
    }


def test_unlagged_source_identity_is_unchanged_and_explicit_zero_is_canonical() -> None:
    document = {
        "name": "unchanged",
        "history": 2,
        "long_when": [{"left": {"source": "close"}, "op": ">", "right": {"value": 10}}],
    }
    spec = parse_rule_spec(document)
    assert spec_sha256(spec) == "4c41542b53184cba7934da8d3c315882a9378a32d2174ed29d3f6cd2c19941fb"
    zero = parse_operand({"source": "close", "lag": 0}, "source")
    assert zero.to_json() == {"source": "close"}
    assert '"lag"' not in canonical_json(spec)


@pytest.mark.parametrize("lag", [True, False, -1, 1.0, 1.5, "1", None, MAX_HISTORY])
def test_source_lag_is_a_strict_bounded_nonnegative_integer(lag: object) -> None:
    with pytest.raises(DataError, match="lag"):
        parse_rule_spec(_momentum(lag))


@pytest.mark.parametrize(
    "operand",
    [{"value": 1, "lag": 1}, {"indicator": "sma", "params": [2], "lag": 1}],
)
def test_lag_does_not_silently_apply_to_other_operand_kinds(operand: dict[str, object]) -> None:
    with pytest.raises(DataError, match="unknown keys"):
        parse_operand(operand, "operand")


def test_lag_sets_required_history_and_has_distinct_identity_and_label() -> None:
    spec = parse_rule_spec(_momentum())
    assert spec.warmup == 21
    assert spec.long_when[0].right.label == "close:lag:20"
    assert spec.long_when[0].right.to_json() == {"source": "close", "lag": 20}
    assert spec_sha256(spec) != spec_sha256(parse_rule_spec(_momentum(19)))
    with pytest.raises(DataError, match="between 21"):
        parse_rule_spec(_momentum(history=20))
    maximum = parse_operand({"source": "high", "lag": MAX_HISTORY - 1}, "operand")
    assert maximum.bars_needed == MAX_HISTORY


@pytest.mark.parametrize("source", ["high", "low", "close"])
def test_lag_series_reads_prior_values_and_leaves_warmup_unavailable(source: str) -> None:
    series = trailing_ohlcv([12, 13, 14], [8, 9, 10], [10, 11, 12], history=3)
    operand = parse_operand({"source": source, "lag": 1}, "operand")
    values = operand_series(series, operand)
    assert np.isnan(values[0])
    np.testing.assert_array_equal(values[1:], getattr(series, source)[:2])


def test_lag_as_long_as_series_is_entirely_unavailable() -> None:
    series = trailing_ohlcv([10, 11, 12], [10, 11, 12], [10, 11, 12], history=3)
    operand = parse_operand({"source": "close", "lag": 3}, "operand")
    assert np.isnan(operand_series(series, operand)).all()


def test_twenty_day_rule_matches_independently_written_chronology() -> None:
    # At decisions 20,21,22: compare [11,12,8] with exactly [10,12,8], respectively.
    # Equality is flat; a 19- or 21-bar shift gives a different answer on this path.
    closes = [10.0, 12.0, 8.0] + [9.0] * 17 + [11.0, 12.0, 8.0]
    spec = parse_rule_spec(_momentum())
    actual = [rule_signal(spec, closes[:n], closes[:n], closes[:n]) for n in (21, 22, 23)]
    assert actual == [1, 0, 0]
    explanation = explain_rules(spec, trailing_ohlcv(closes, closes, closes, history=21))
    assert explanation["signal"] == 0
    assert explanation["conditions"][0]["right"] == pytest.approx(8.0)
    assert explanation["conditions"][0]["label"] == "close > close:lag:20"


@pytest.mark.bias_guard
def test_source_lag_future_poison_and_deliberately_leaky_control() -> None:
    spec = parse_rule_spec(_momentum())
    closes = [10.0] * 20 + [11.0]
    clean = closes + [12.0]
    poisoned = closes + [0.01]

    def at_decision(path: list[float]) -> int:
        visible = path[:21]
        return rule_signal(spec, visible, visible, visible)

    assert at_decision(clean) == at_decision(poisoned) == 1
    # The deliberately leaky twin evaluates the appended bar but calls it decision 20.
    # This assertion must fail, proving the poison can detect future consumption.
    with pytest.raises(AssertionError):
        assert rule_signal(spec, clean, clean, clean) == rule_signal(
            spec, poisoned, poisoned, poisoned
        )
