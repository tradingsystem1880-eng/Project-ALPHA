"""Rule explanations follow the execution evaluator, including short circuiting."""

from dataclasses import replace

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import OHLCV
from alpha_strategies import rules


def spec() -> rules.RuleSpec:
    return rules.parse_rule_spec(
        {
            "name": "checklist",
            "history": 3,
            "long_when": [{"left": {"source": "close"}, "op": ">", "right": {"value": 2}}],
            "short_when": [{"left": {"source": "close"}, "op": "<", "right": {"value": 2}}],
        }
    )


def series(close: float = 3) -> OHLCV:
    values = np.array([1.0, 2.0, close])
    return OHLCV(
        ts=np.arange(3, dtype=float),
        open=values,
        high=values,
        low=values,
        close=values,
        volume=np.ones(3),
        symbol="SPY",
    )


@pytest.mark.parametrize("close,signal", [(1.0, -1), (2.0, 0), (3.0, 1)])
def test_trace_matches_execution_with_exact_operands(close: float, signal: int) -> None:
    result = rules.explain_rules(spec(), series(close))
    assert result["signal"] == rules.evaluate_rules(spec(), series(close)) == signal
    assert result["error"] is None
    assert result["conditions"][0]["left"] == close
    assert result["conditions"][0]["right"] == 2
    assert result["conditions"][0]["side"] == "long"
    assert result["conditions"][0]["index"] == 0


def test_both_sides_true_remains_flat() -> None:
    original = spec()
    conflict = replace(original, short_when=original.long_when)
    result = rules.explain_rules(conflict, series())
    assert result["signal"] == rules.evaluate_rules(conflict, series()) == 0
    assert [row["status"] for row in result["conditions"]] == ["pass", "pass"]


def test_short_circuit_does_not_evaluate_unreachable_condition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = spec()
    unreachable = replace(original.long_when[0], left=rules.Operand(kind="value", value=999))
    combined = replace(original, long_when=(*original.long_when, unreachable))
    operand_series = rules.operand_series

    def checked(window: OHLCV, operand: rules.Operand) -> np.ndarray:
        if operand == unreachable.left:
            raise AssertionError("short circuit was lost")
        return operand_series(window, operand)

    monkeypatch.setattr(rules, "operand_series", checked)
    result = rules.explain_rules(combined, series(1))
    assert result["signal"] == rules.evaluate_rules(combined, series(1)) == -1
    assert result["conditions"][1]["status"] == "unavailable"
    assert "short-circuit" in (result["conditions"][1]["reason"] or "")


def test_unavailable_is_not_flat_and_stops_after_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*args: object) -> np.ndarray:
        raise DataError("indicator unavailable")

    monkeypatch.setattr(rules, "operand_series", broken)
    result = rules.explain_rules(spec(), series())
    assert result["signal"] is None
    assert result["error"] == "indicator unavailable"
    assert all(row["status"] == "unavailable" for row in result["conditions"])
    with pytest.raises(DataError, match="indicator unavailable"):
        rules.evaluate_rules(spec(), series())


def test_wrong_history_and_missing_bars_are_unavailable() -> None:
    result = rules.explain_rules(replace(spec(), history=4), series())
    assert result["signal"] is None and "exactly 4" in (result["error"] or "")
    missing = rules.explain_rules(spec(), None, unavailable_reason="No stored bars")
    assert missing["error"] == "No stored bars"
    assert all(row["reason"] == "No stored bars" for row in missing["conditions"])


@pytest.mark.parametrize("op,expected", [(">", False), ("<", False), (">=", True), ("<=", True)])
def test_comparison_equality_boundaries(op: rules.Op, expected: bool) -> None:
    original = spec()
    condition = replace(original.long_when[0], op=op)
    comparison = replace(original, long_when=(condition,), short_when=())
    result = rules.explain_rules(comparison, series(2))
    assert result["conditions"][0]["status"] == ("pass" if expected else "fail")
    assert result["signal"] == rules.evaluate_rules(comparison, series(2))
