"""Frozen domain value types shared across all packages."""

from __future__ import annotations

import math
from collections.abc import Mapping

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator


class Bar(BaseModel):
    """A single OHLCV bar for one instrument.

    ``ts`` is the tz-aware bar timestamp; daily bars are date-keyed and stamped at the session
    date at 00:00 UTC (see ``alpha_data`` ingestion), not an intraday close instant.
    """

    model_config = ConfigDict(frozen=True)

    symbol: str
    ts: AwareDatetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @model_validator(mode="after")
    def _check_invariants(self) -> Bar:
        prices = {"open": self.open, "high": self.high, "low": self.low, "close": self.close}
        for name, v in {**prices, "volume": self.volume}.items():
            if math.isnan(v) or math.isinf(v):
                raise ValueError(f"Bar.{name} must be finite, got {v!r}")
        if self.volume < 0:
            raise ValueError(f"Bar.volume must be >= 0, got {self.volume}")
        for name, v in prices.items():
            if v <= 0:
                raise ValueError(f"Bar.{name} must be > 0, got {v}")
        if not (self.low <= self.open <= self.high and self.low <= self.close <= self.high):
            raise ValueError(
                f"OHLC inconsistent: low={self.low} open={self.open}"
                f" high={self.high} close={self.close}"
            )
        return self


class ValidationOutcome(BaseModel):
    """The result of a single validation gate."""

    model_config = ConfigDict(frozen=True)

    name: str
    passed: bool
    detail: Mapping[str, float] = {}
