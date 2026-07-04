"""``ForecastResult``/``SampledPath`` construction-time validation (fail-loud, frozen)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from alpha_core import DataError
from alpha_forecast import ForecastResult, SampledPath

_T0 = datetime(2026, 6, 1, tzinfo=UTC)


def _steps(h: int) -> tuple[datetime, ...]:
    return tuple(_T0 + timedelta(days=i + 1) for i in range(h))


def _path(closes: tuple[float, ...]) -> SampledPath:
    return SampledPath(
        open=closes, high=closes, low=closes, close=closes, volume=tuple(0.0 for _ in closes)
    )


def test_forecast_result_valid_roundtrip() -> None:
    r = ForecastResult(
        symbol="SPY",
        origin_ts=_T0,
        horizon=3,
        step_ts=_steps(3),
        samples=(_path((101.0, 102.0, 103.0)), _path((99.0, 98.0, 97.0))),
    )
    assert r.horizon == 3
    assert len(r.samples) == 2
    assert r.samples[1].close[-1] == 97.0


def test_forecast_result_rejects_ragged_sample() -> None:
    with pytest.raises(DataError, match="length"):
        ForecastResult(
            symbol="SPY",
            origin_ts=_T0,
            horizon=3,
            step_ts=_steps(3),
            samples=(_path((101.0, 102.0)),),
        )


def test_sampled_path_rejects_internal_length_mismatch() -> None:
    with pytest.raises(DataError, match="length"):
        SampledPath(
            open=(1.0, 2.0),
            high=(1.0, 2.0),
            low=(1.0, 2.0),
            close=(1.0, 2.0, 3.0),
            volume=(0.0, 0.0),
        )


def test_forecast_result_rejects_nonfinite_close() -> None:
    with pytest.raises(DataError, match="finite"):
        ForecastResult(
            symbol="SPY",
            origin_ts=_T0,
            horizon=2,
            step_ts=_steps(2),
            samples=(_path((101.0, float("nan"))),),
        )


def test_forecast_result_rejects_nonpositive_close() -> None:
    with pytest.raises(DataError, match="close"):
        ForecastResult(
            symbol="SPY",
            origin_ts=_T0,
            horizon=2,
            step_ts=_steps(2),
            samples=(_path((101.0, -3.0)),),
        )


def test_forecast_result_rejects_disordered_step_ts() -> None:
    ts = _steps(3)
    with pytest.raises(DataError, match="increasing"):
        ForecastResult(
            symbol="SPY",
            origin_ts=_T0,
            horizon=3,
            step_ts=(ts[1], ts[0], ts[2]),
            samples=(_path((1.0, 2.0, 3.0)),),
        )


def test_forecast_result_rejects_steps_not_after_origin() -> None:
    with pytest.raises(DataError, match="origin"):
        ForecastResult(
            symbol="SPY",
            origin_ts=_T0,
            horizon=2,
            step_ts=(_T0, _T0 + timedelta(days=1)),
            samples=(_path((1.0, 2.0)),),
        )


def test_forecast_result_rejects_empty_samples_or_bad_horizon() -> None:
    with pytest.raises(DataError, match="sample"):
        ForecastResult(symbol="SPY", origin_ts=_T0, horizon=2, step_ts=_steps(2), samples=())
    with pytest.raises(DataError, match="horizon"):
        ForecastResult(symbol="SPY", origin_ts=_T0, horizon=0, step_ts=(), samples=())
