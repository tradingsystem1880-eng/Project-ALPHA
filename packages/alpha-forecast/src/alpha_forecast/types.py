"""Frozen forecast value types + the ``Forecaster`` protocol (numpy-free public seam)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from alpha_core import Bar, DataError

_PATH_FIELDS = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class SampledPath:
    """One sampled OHLCV forecast path (parallel per-step tuples).

    All values must be finite and ``close`` strictly positive (returns math depends on it).
    OHLC consistency is deliberately NOT enforced: paths are raw model output and the model
    carries no such constraint — consumers use ``close`` (and quantiles of it), never assume
    a coherent candle.
    """

    open: tuple[float, ...]
    high: tuple[float, ...]
    low: tuple[float, ...]
    close: tuple[float, ...]
    volume: tuple[float, ...]

    def __post_init__(self) -> None:
        n = len(self.close)
        for name in _PATH_FIELDS:
            values: tuple[float, ...] = getattr(self, name)
            if len(values) != n:
                raise DataError(f"SampledPath.{name} length {len(values)} != close length {n}")
            for v in values:
                if not math.isfinite(v):
                    raise DataError(f"SampledPath.{name} must be finite, got {v!r}")
        for v in self.close:
            if v <= 0.0:
                raise DataError(f"SampledPath.close must be > 0, got {v}")


@dataclass(frozen=True)
class ForecastResult:
    """``len(samples)`` sampled paths of the ``horizon`` sessions after ``origin_ts``."""

    symbol: str
    origin_ts: datetime
    horizon: int
    step_ts: tuple[datetime, ...]
    samples: tuple[SampledPath, ...]

    def __post_init__(self) -> None:
        if self.horizon < 1:
            raise DataError(f"horizon must be >= 1, got {self.horizon}")
        if not self.samples:
            raise DataError("ForecastResult needs at least one sample path")
        if len(self.step_ts) != self.horizon:
            raise DataError(f"step_ts length {len(self.step_ts)} != horizon {self.horizon}")
        if any(b <= a for a, b in zip(self.step_ts, self.step_ts[1:], strict=False)):
            raise DataError("step_ts must be strictly increasing")
        if self.step_ts[0] <= self.origin_ts:
            raise DataError(f"step_ts must start after origin_ts {self.origin_ts.isoformat()}")
        for i, path in enumerate(self.samples):
            if len(path.close) != self.horizon:
                raise DataError(f"samples[{i}] length {len(path.close)} != horizon {self.horizon}")


@runtime_checkable
class Forecaster(Protocol):
    """Anything that turns a trailing bar window into sampled future paths."""

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
    ) -> ForecastResult: ...
