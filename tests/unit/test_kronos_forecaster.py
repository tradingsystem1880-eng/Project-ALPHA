"""KronosForecaster behaviour with a fake predictor (no torch, no weights)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from alpha_core import Bar, BarForecaster, DataError
from alpha_forecast import KronosForecaster
from tests.fixtures.forecast_fixtures import daily_bars


class _FakePredictor:
    """Mimics the vendored KronosPredictor.predict surface deterministically."""

    def __init__(self, *, close_bump: float = 1.02, poison: float | None = None) -> None:
        self.close_bump = close_bump
        self.poison = poison
        self.calls = 0

    def predict(
        self,
        *,
        df: Any,
        x_timestamp: Any,
        y_timestamp: Any,
        pred_len: int,
        T: float,
        top_k: int,
        top_p: float,
        sample_count: int,
        verbose: bool,
    ) -> Any:
        import pandas as pd

        self.calls += 1
        last_close = float(df["close"].iloc[-1])
        rows = []
        for i in range(pred_len):
            c = self.poison if self.poison is not None else last_close * self.close_bump ** (i + 1)
            rows.append(
                # low deliberately above close: exercises the structural OHLC fix
                {
                    "open": c * 0.999,
                    "high": c * 0.99,
                    "low": c * 1.01,
                    "close": c,
                    "volume": -5.0,
                    "amount": 0.0,
                }
            )
        return pd.DataFrame(rows, index=y_timestamp)


def _forecaster(tmp_path: Path, fake: _FakePredictor, **kw: Any) -> KronosForecaster:
    f = KronosForecaster(
        model_name=kw.pop("model_name", "base"),
        weights_dir=tmp_path / "weights",
        cache_dir=kw.pop("cache_dir", None),
        seed=kw.pop("seed", 7),
        **kw,
    )
    f._predictor = fake  # bypass _load: unit tests never touch torch
    f._seed_torch = lambda value: None  # type: ignore[method-assign]
    return f


def test_satisfies_protocol_and_forecasts(tmp_path: Path) -> None:
    fake = _FakePredictor()
    f = _forecaster(tmp_path, fake)
    assert isinstance(f, BarForecaster)
    bars = daily_bars(n=20)
    out = f.forecast(bars, 5)
    assert len(out) == 5
    assert all(isinstance(b, Bar) for b in out)
    assert out[-1].close > bars[-1].close
    # structural fixes applied: OHLC consistent, volume clamped to >= 0
    assert all(b.low <= b.open <= b.high and b.low <= b.close <= b.high for b in out)
    assert all(b.volume == 0.0 for b in out)


def test_context_longer_than_max_context_fails_loud(tmp_path: Path) -> None:
    f = _forecaster(tmp_path, _FakePredictor(), model_name="base")  # max_context 512
    bars = daily_bars(n=513)
    with pytest.raises(DataError, match="max_context"):
        f.forecast(bars, 5)


def test_bad_params_fail_loud_before_torch(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="unknown Kronos model"):
        KronosForecaster(model_name="huge", weights_dir=tmp_path)
    with pytest.raises(DataError, match="temperature"):
        KronosForecaster(model_name="mini", weights_dir=tmp_path, temperature=0.0)
    with pytest.raises(DataError, match="top_p"):
        KronosForecaster(model_name="mini", weights_dir=tmp_path, top_p=1.5)
    with pytest.raises(DataError, match="sample_count"):
        KronosForecaster(model_name="mini", weights_dir=tmp_path, sample_count=0)
    f = _forecaster(tmp_path, _FakePredictor())
    with pytest.raises(DataError, match="horizon"):
        f.forecast(daily_bars(n=10), 0)
    with pytest.raises(DataError, match=">= 2 context bars"):
        f.forecast(daily_bars(n=1), 3)


def test_mixed_symbols_fail_loud(tmp_path: Path) -> None:
    f = _forecaster(tmp_path, _FakePredictor())
    bars = daily_bars(n=10)
    bars[-1] = bars[-1].model_copy(update={"symbol": "OTHER"})
    with pytest.raises(DataError, match="mixes symbols"):
        f.forecast(bars, 3)


def test_non_tradable_forecast_fails_loud_never_clamped(tmp_path: Path) -> None:
    f = _forecaster(tmp_path, _FakePredictor(poison=-1.0))
    with pytest.raises(DataError, match="non-tradable"):
        f.forecast(daily_bars(n=10), 3)
    f_nan = _forecaster(tmp_path, _FakePredictor(poison=float("nan")))
    with pytest.raises(DataError, match="non-tradable"):
        f_nan.forecast(daily_bars(n=10), 3)


def test_cache_hit_skips_predictor(tmp_path: Path) -> None:
    bars = daily_bars(n=15)
    fake = _FakePredictor()
    f = _forecaster(tmp_path, fake, cache_dir=tmp_path / "cache")
    first = f.forecast_full(bars, 4)
    assert fake.calls == 1
    again = f.forecast_full(bars, 4)
    assert fake.calls == 1  # served from cache
    assert [b.close for b in again.path] == [b.close for b in first.path]
    # a fresh forecaster with an un-loadable model also hits the cache, never torch
    cold = KronosForecaster(
        model_name="base", weights_dir=tmp_path / "nowhere", cache_dir=tmp_path / "cache"
    )
    cached = cold.forecast_full(bars, 4)
    assert [b.close for b in cached.path] == [b.close for b in first.path]


def test_sample_count_gt_1_yields_band(tmp_path: Path) -> None:
    fake = _FakePredictor()
    f = _forecaster(tmp_path, fake, sample_count=3)
    result = f.forecast_full(daily_bars(n=12), 4)
    assert fake.calls == 3
    assert result.close_p10 is not None and result.close_p90 is not None
    assert len(result.close_p10) == 4 == len(result.close_p90)
    assert all(lo <= hi for lo, hi in zip(result.close_p10, result.close_p90, strict=True))


def test_seeding_is_call_order_independent(tmp_path: Path) -> None:
    seen: list[int] = []

    bars_a = daily_bars(n=10)
    bars_b = daily_bars(n=11)

    def record(value: int) -> None:
        seen.append(value)

    fake = _FakePredictor()
    f1 = _forecaster(tmp_path, fake)
    f1._seed_torch = record  # type: ignore[method-assign]
    f1.forecast(bars_a, 3)
    f1.forecast(bars_b, 3)
    a_then_b = list(seen)

    seen.clear()
    f2 = _forecaster(tmp_path, _FakePredictor())
    f2._seed_torch = record  # type: ignore[method-assign]
    f2.forecast(bars_b, 3)
    f2.forecast(bars_a, 3)
    assert sorted(a_then_b) == sorted(seen)
    assert a_then_b == list(reversed(seen))


def test_missing_weights_error_is_instructional(tmp_path: Path) -> None:
    f = KronosForecaster(model_name="mini", weights_dir=tmp_path / "empty")
    pytest.importorskip("torch", reason="torch stack not installed (uv sync --group kronos)")
    with pytest.raises(DataError, match="alpha forecast pull --model mini"):
        f.forecast(daily_bars(n=10), 2)


def test_package_import_does_not_load_torch() -> None:
    code = "import sys, alpha_forecast; sys.exit(0 if 'torch' not in sys.modules else 1)"
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
