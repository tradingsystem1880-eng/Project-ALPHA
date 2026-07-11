"""BarForecaster protocol + weights_dir setting."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from alpha_core import Bar, BarForecaster
from alpha_core.config import AlphaSettings


def _bar(ts: datetime, price: float) -> Bar:
    return Bar(
        symbol="TEST",
        ts=ts,
        open=price,
        high=price * 1.01,
        low=price * 0.99,
        close=price,
        volume=1_000.0,
    )


class _DriftForecaster:
    """Minimal structural implementation: extends the last close by +1% per bar."""

    def forecast(self, bars: Sequence[Bar], horizon: int) -> list[Bar]:
        last = bars[-1]
        out: list[Bar] = []
        price = last.close
        for i in range(horizon):
            price *= 1.01
            out.append(_bar(last.ts.replace(hour=1 + i % 20), price))
        return out


def test_protocol_is_runtime_checkable() -> None:
    assert isinstance(_DriftForecaster(), BarForecaster)
    assert not isinstance(object(), BarForecaster)


def test_structural_impl_forecasts_bars() -> None:
    bars = [_bar(datetime(2026, 1, 2, tzinfo=UTC), 100.0)]
    out = _DriftForecaster().forecast(bars, 3)
    assert len(out) == 3
    assert all(isinstance(b, Bar) for b in out)
    assert out[-1].close > bars[-1].close


def test_weights_dir_defaults_under_data_dir() -> None:
    s = AlphaSettings(data_dir=Path("/tmp/x"), weights_dir=None)
    assert s.resolved_weights_dir == Path("/tmp/x/models")


def test_weights_dir_explicit_override() -> None:
    s = AlphaSettings(weights_dir=Path("/opt/weights"))
    assert s.resolved_weights_dir == Path("/opt/weights")


def test_weights_dir_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_WEIGHTS_DIR", "/env/weights")
    s = AlphaSettings()
    assert s.resolved_weights_dir == Path("/env/weights")
