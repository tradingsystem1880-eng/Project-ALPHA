"""A rule reads exactly the value the chart draws: ``operand_series`` equals the
``alpha chart overlays`` series for every indicator once warm-up is over."""

from __future__ import annotations

import math

import numpy as np
import pytest

from alpha_cli.chart_cmds import indicator_series, parse_indicator
from alpha_patterns import OHLCV
from alpha_strategies.rules import Operand, operand_series


def _bars(n: int = 120) -> OHLCV:
    rng = np.random.default_rng(3)
    close = np.asarray(100.0 * np.cumprod(1.0 + rng.normal(0.0005, 0.01, n)), dtype=np.float64)
    spread = np.asarray(np.abs(rng.normal(0.0, 0.5, n)) + 0.1, dtype=np.float64)
    return OHLCV(
        ts=np.arange(n, dtype=np.float64) * 86_400_000.0,
        open=close - 0.1,
        high=close + spread,
        low=close - spread,
        close=close,
        volume=np.ones(n),
        symbol="ZZ",
    )


@pytest.mark.parametrize(
    ("operand", "spec", "series_index"),
    [
        (Operand("indicator", indicator="sma", params=(20.0,)), "sma:20", 0),
        (Operand("indicator", indicator="ema", params=(20.0,)), "ema:20", 0),
        (Operand("indicator", indicator="rsi", params=(14.0,)), "rsi:14", 0),
        (Operand("indicator", indicator="atr", params=(14.0,)), "atr:14", 0),
        (
            Operand("indicator", indicator="bbands", params=(20.0, 2.0), field="upper"),
            "bbands:20:2",
            0,
        ),
        (
            Operand("indicator", indicator="bbands", params=(20.0, 2.0), field="middle"),
            "bbands:20:2",
            1,
        ),
        (
            Operand("indicator", indicator="bbands", params=(20.0, 2.0), field="lower"),
            "bbands:20:2",
            2,
        ),
        (
            Operand("indicator", indicator="macd", params=(12.0, 26.0, 9.0), field="line"),
            "macd:12:26:9",
            0,
        ),
        (
            Operand("indicator", indicator="macd", params=(12.0, 26.0, 9.0), field="signal"),
            "macd:12:26:9",
            1,
        ),
        (
            Operand("indicator", indicator="macd", params=(12.0, 26.0, 9.0), field="histogram"),
            "macd:12:26:9",
            2,
        ),
    ],
)
def test_rule_operand_equals_chart_series(operand: Operand, spec: str, series_index: int) -> None:
    bars = _bars()
    chart = indicator_series(bars, parse_indicator(spec))[series_index]
    values = operand_series(bars, operand)
    assert chart["warmup"] == operand.bars_needed - 1 or operand.indicator in {"rsi", "macd"}
    for i, (drawn, read) in enumerate(zip(chart["values"], values.tolist(), strict=True)):
        if drawn is None:
            assert math.isnan(read), f"bar {i}: chart blank but rule reads {read}"
        else:
            assert read == pytest.approx(drawn), f"bar {i}"


def test_source_and_value_operands() -> None:
    bars = _bars(10)
    assert operand_series(bars, Operand("source", source="high")).tolist() == bars.high.tolist()
    assert operand_series(bars, Operand("value", value=30.0)).tolist() == [30.0] * 10
