"""``close_quantiles``: per-step close quantiles across sampled paths."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from alpha_core import DataError
from alpha_forecast import ForecastResult, SampledPath, close_quantiles

_T0 = datetime(2026, 6, 1, tzinfo=UTC)


def _result(closes_by_sample: Sequence[tuple[float, ...]]) -> ForecastResult:
    h = len(closes_by_sample[0])
    return ForecastResult(
        symbol="X",
        origin_ts=_T0,
        horizon=h,
        step_ts=tuple(_T0 + timedelta(days=i + 1) for i in range(h)),
        samples=tuple(
            SampledPath(open=c, high=c, low=c, close=c, volume=tuple(0.0 for _ in c))
            for c in closes_by_sample
        ),
    )


def test_matches_numpy_quantile_per_step() -> None:
    closes = [(100.0, 110.0), (102.0, 90.0), (98.0, 130.0), (101.0, 105.0)]
    r = _result(closes)
    out = close_quantiles(r, qs=(0.25, 0.5, 0.75))
    arr = np.array(closes)
    for q in (0.25, 0.5, 0.75):
        expected = np.quantile(arr, q, axis=0)
        assert out[q] == pytest.approx(tuple(expected))


def test_monotone_across_qs() -> None:
    closes = [(100.0 + i, 200.0 - 3.0 * i) for i in range(9)]
    out = close_quantiles(_result(closes))
    for step in range(2):
        vals = [out[q][step] for q in sorted(out)]
        assert vals == sorted(vals)


def test_default_quantile_set() -> None:
    out = close_quantiles(_result([(100.0,), (101.0,)]))
    assert sorted(out) == [0.05, 0.25, 0.5, 0.75, 0.95]


def test_rejects_bad_qs() -> None:
    r = _result([(100.0,)])
    with pytest.raises(DataError, match="quantile"):
        close_quantiles(r, qs=())
    with pytest.raises(DataError, match="quantile"):
        close_quantiles(r, qs=(0.0, 0.5))
    with pytest.raises(DataError, match="quantile"):
        close_quantiles(r, qs=(0.5, 1.0))
