"""Frozen domain value types shared across all packages."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Literal

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


class DecisionTrace(BaseModel):
    """One observed strategy decision at the close-time event that produced a target."""

    model_config = ConfigDict(frozen=True)

    ts: AwareDatetime
    instrument_id: str
    signal: int | None
    target_quantity: float
    reason: str

    @model_validator(mode="after")
    def _check_decision(self) -> DecisionTrace:
        if self.signal not in (-1, 0, 1, None):
            raise ValueError(f"DecisionTrace.signal must be -1, 0, 1, or None, got {self.signal}")
        if not math.isfinite(self.target_quantity):
            raise ValueError("DecisionTrace.target_quantity must be finite")
        if not self.instrument_id or not self.reason:
            raise ValueError("DecisionTrace instrument_id and reason must be non-empty")
        return self


class IndicatorTrace(BaseModel):
    """One causal indicator value emitted from the prefix available at a decision timestamp."""

    model_config = ConfigDict(frozen=True)

    ts: AwareDatetime
    instrument_id: str
    name: str
    value: float
    unit: str

    @model_validator(mode="after")
    def _check_indicator(self) -> IndicatorTrace:
        if not self.instrument_id or not self.name or not self.unit:
            raise ValueError("IndicatorTrace instrument_id, name, and unit must be non-empty")
        if not math.isfinite(self.value):
            raise ValueError("IndicatorTrace.value must be finite")
        return self


class ChartAnchor(BaseModel):
    """One causal point in a deterministic vector chart annotation."""

    model_config = ConfigDict(frozen=True)

    ts: AwareDatetime
    value: float

    @model_validator(mode="after")
    def _check_anchor(self) -> ChartAnchor:
        if not math.isfinite(self.value):
            raise ValueError("ChartAnchor.value must be finite")
        return self


class ChartAnnotationTrace(BaseModel):
    """A vector annotation emitted by strategy code at decision time, never reconstructed."""

    model_config = ConfigDict(frozen=True)

    decision_ts: AwareDatetime
    instrument_id: str
    kind: Literal["line", "polyline", "zone"]
    label: str
    unit: str
    reason: str
    anchors: tuple[ChartAnchor, ...]

    @model_validator(mode="after")
    def _check_annotation(self) -> ChartAnnotationTrace:
        if not self.instrument_id or not self.label or not self.unit or not self.reason:
            raise ValueError(
                "ChartAnnotationTrace instrument_id, label, unit, and reason must be non-empty"
            )
        if len(self.anchors) < 2:
            raise ValueError("ChartAnnotationTrace requires at least two anchors")
        if any(anchor.ts > self.decision_ts for anchor in self.anchors):
            raise ValueError("ChartAnnotationTrace anchors cannot occur after decision_ts")
        return self


class ValidationOutcome(BaseModel):
    """The result of a single validation gate."""

    model_config = ConfigDict(frozen=True)

    name: str
    passed: bool
    detail: Mapping[str, float] = {}
