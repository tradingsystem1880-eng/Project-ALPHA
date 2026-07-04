"""Offline test double for the ``Forecaster`` protocol (deterministic, window-pure)."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from alpha_core import Bar, DataError
from alpha_forecast.timestamps import future_session_ts
from alpha_forecast.types import ForecastResult, SampledPath

# Degenerate (constant-return) windows still get usable sample spread: this is a test
# double, not a statistic — a tiny vol floor beats failing every drift-only fixture.
_SIGMA_FLOOR = 1e-4


def _window_fingerprint(bars: Sequence[Bar]) -> int:
    payload = "|".join(
        f"{b.ts.isoformat()},{b.open!r},{b.high!r},{b.low!r},{b.close!r},{b.volume!r}"
        for b in bars
    )
    return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8], "big")


@dataclass(frozen=True)
class FakeForecaster:
    """GBM-ish sampled paths with drift/vol estimated from the input window.

    Pure function of ``(bars, params, seed)``: the RNG is keyed on the seed AND a content
    fingerprint of the window, so identical windows give identical forecasts and any
    in-window change perturbs every path. ``temperature`` scales the sampling vol so the
    knob is observable in offline runs.
    """

    vol_scale: float = 1.0

    def forecast(
        self,
        bars: Sequence[Bar],
        *,
        horizon: int,
        sample_count: int,
        temperature: float = 1.0,
        top_p: float = 0.9,
        top_k: int = 0,
        seed: int = 0,
    ) -> ForecastResult:
        if len(bars) < 2:
            raise DataError(f"FakeForecaster needs >= 2 bars for return stats, got {len(bars)}")
        if horizon < 1:
            raise DataError(f"horizon must be >= 1, got {horizon}")
        if sample_count < 1:
            raise DataError(f"sample_count must be >= 1, got {sample_count}")

        closes = np.array([b.close for b in bars], dtype=np.float64)
        log_returns = np.diff(np.log(closes))
        mu = float(np.mean(log_returns))
        sigma = max(float(np.std(log_returns)), _SIGMA_FLOOR) * self.vol_scale * temperature

        rng = np.random.default_rng([seed & 0xFFFFFFFF, _window_fingerprint(bars)])
        steps = rng.normal(loc=mu, scale=sigma, size=(sample_count, horizon))
        paths = closes[-1] * np.exp(np.cumsum(steps, axis=1))  # (S, H)

        last_volume = float(bars[-1].volume)
        samples = []
        for s in range(sample_count):
            close_path = paths[s]
            open_path = np.concatenate(([closes[-1]], close_path[:-1]))
            high_path = np.maximum(open_path, close_path) * (1.0 + 0.25 * sigma)
            low_path = np.minimum(open_path, close_path) * (1.0 - 0.25 * sigma)
            samples.append(
                SampledPath(
                    open=tuple(float(v) for v in open_path),
                    high=tuple(float(v) for v in high_path),
                    low=tuple(float(v) for v in low_path),
                    close=tuple(float(v) for v in close_path),
                    volume=tuple(last_volume for _ in range(horizon)),
                )
            )

        recent_ts = [b.ts for b in bars[-10:]]
        return ForecastResult(
            symbol=bars[-1].symbol,
            origin_ts=bars[-1].ts,
            horizon=horizon,
            step_ts=tuple(future_session_ts(recent_ts, horizon)),
            samples=tuple(samples),
        )
