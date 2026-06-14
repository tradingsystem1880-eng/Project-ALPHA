"""Frozen domain value types shared across all packages."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import AwareDatetime, BaseModel, ConfigDict


class Bar(BaseModel):
    """A single OHLCV bar for one instrument. `ts` is the tz-aware bar-close time."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    ts: AwareDatetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class ValidationOutcome(BaseModel):
    """The result of a single validation gate."""

    model_config = ConfigDict(frozen=True)

    name: str
    passed: bool
    detail: Mapping[str, float] = {}
