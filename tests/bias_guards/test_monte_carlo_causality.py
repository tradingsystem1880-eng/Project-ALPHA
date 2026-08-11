"""Future observations cannot alter frozen Monte Carlo inputs or physical projections."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import numpy as np
import pytest

from alpha_cli.monte_carlo_cmds import _causal_regime_states, _project_forecast_path
from alpha_core import Bar, DataError


def _bars(count: int = 100) -> list[Bar]:
    rng = np.random.default_rng(9)
    closes = 100.0 * np.cumprod(1.0 + rng.normal(0.0002, 0.01, count))
    start = datetime(2020, 1, 1, tzinfo=UTC)
    return [
        Bar(
            symbol="SPY",
            ts=start + timedelta(days=index),
            open=float(close),
            high=float(close * 1.01),
            low=float(close * 0.99),
            close=float(close),
            volume=1_000_000.0,
        )
        for index, close in enumerate(closes)
    ]


def test_future_bars_cannot_change_frozen_regime_labels_or_threshold() -> None:
    bars = _bars()
    scored_timestamps = [bar.ts for bar in bars[40:70]]
    states, threshold, volatility = _causal_regime_states(
        bars, scored_timestamps, train_size=35, window=5
    )
    poisoned = [*bars]
    for index in range(70, len(poisoned)):
        prior = poisoned[index - 1].close
        close = prior * (1.5 if index % 2 else 0.55)
        poisoned[index] = Bar(
            symbol="SPY",
            ts=poisoned[index].ts,
            open=prior,
            high=max(prior, close) * 1.01,
            low=min(prior, close) * 0.99,
            close=close,
            volume=1_000_000.0,
        )
    poisoned_states, poisoned_threshold, poisoned_volatility = _causal_regime_states(
        poisoned, scored_timestamps, train_size=35, window=5
    )
    assert poisoned_threshold == threshold
    assert np.array_equal(poisoned_states, states)
    assert np.array_equal(poisoned_volatility, volatility)


def test_kronos_projection_preserves_raw_values_and_only_expands_enclosure() -> None:
    timestamp = datetime(2026, 1, 2, tzinfo=UTC)
    sample = SimpleNamespace(
        open=(100.0,), high=(99.0,), low=(102.0,), close=(101.0,), volume=(5.0,)
    )
    bars, rows, adjustments = _project_forecast_path(
        symbol="SPY", timestamps=(timestamp,), sample=sample, path_index=3
    )
    assert bars[0].high == 101.0 and bars[0].low == 100.0
    assert rows[0]["raw_high"] == 99.0 and rows[0]["raw_low"] == 102.0
    assert rows[0]["high_adjusted"] is True and rows[0]["low_adjusted"] is True
    assert adjustments == 2


@pytest.mark.parametrize(
    "sample",
    [
        SimpleNamespace(open=(0.0,), high=(1.0,), low=(1.0,), close=(1.0,), volume=(1.0,)),
        SimpleNamespace(open=(1.0,), high=(1.0,), low=(1.0,), close=(1.0,), volume=(-1.0,)),
    ],
)
def test_kronos_projection_rejects_invalid_model_values(sample: SimpleNamespace) -> None:
    with pytest.raises(DataError):
        _project_forecast_path(
            symbol="SPY",
            timestamps=(datetime(2026, 1, 2, tzinfo=UTC),),
            sample=sample,
            path_index=0,
        )


def test_kronos_projection_rejects_component_length_mismatch() -> None:
    sample = SimpleNamespace(
        open=(1.0,), high=(1.0, 1.0), low=(1.0, 1.0), close=(1.0, 1.0), volume=(1.0, 1.0)
    )
    timestamps = (
        datetime(2026, 1, 2, tzinfo=UTC),
        datetime(2026, 1, 3, tzinfo=UTC),
    )
    with pytest.raises(DataError, match="open length 1 differs from horizon 2"):
        _project_forecast_path(symbol="SPY", timestamps=timestamps, sample=sample, path_index=4)
