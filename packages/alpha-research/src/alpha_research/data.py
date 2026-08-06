"""Research-only dataset identity and equal-duration point-in-time bars."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from alpha_core import DataError

_SHA256 = re.compile(r"[0-9a-f]{64}")


def _nonempty(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DataError(f"ResearchDatasetRef.{name} must be a non-empty string")
    return value


def _sha256(name: str, value: str) -> None:
    if _SHA256.fullmatch(value) is None:
        raise DataError(f"{name} must be a lowercase 64-character SHA-256 digest")


def _aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DataError(f"ResearchBar.{name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ResearchDatasetRef:
    """A content-bound external dataset that is categorically ineligible for execution evidence."""

    dataset_id: str
    provider: str
    provider_symbol: str
    symbol: str
    venue: str
    timeframe: str
    timezone: str
    session: str
    content_sha256: str
    scope: Literal["research_only"] = field(default="research_only", init=False)

    def __post_init__(self) -> None:
        for name in (
            "dataset_id",
            "provider",
            "provider_symbol",
            "symbol",
            "venue",
            "timeframe",
            "timezone",
            "session",
        ):
            _nonempty(name, getattr(self, name))
        _sha256("ResearchDatasetRef.content_sha256", self.content_sha256)

    def to_dict(self) -> dict[str, str]:
        return {
            "content_sha256": self.content_sha256,
            "dataset_id": self.dataset_id,
            "provider": self.provider,
            "provider_symbol": self.provider_symbol,
            "scope": self.scope,
            "session": self.session,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timezone": self.timezone,
            "venue": self.venue,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ResearchDatasetRef:
        expected = {
            "content_sha256",
            "dataset_id",
            "provider",
            "provider_symbol",
            "scope",
            "session",
            "symbol",
            "timeframe",
            "timezone",
            "venue",
        }
        if set(value) != expected:
            raise DataError("ResearchDatasetRef payload has unexpected fields")
        fields = {name: _nonempty(name, value[name]) for name in expected}
        if fields["scope"] != "research_only":
            raise DataError("ResearchDatasetRef.scope is permanently research_only")
        return cls(
            dataset_id=fields["dataset_id"],
            provider=fields["provider"],
            provider_symbol=fields["provider_symbol"],
            symbol=fields["symbol"],
            venue=fields["venue"],
            timeframe=fields["timeframe"],
            timezone=fields["timezone"],
            session=fields["session"],
            content_sha256=fields["content_sha256"],
        )


@dataclass(frozen=True, slots=True)
class ResearchBar:
    """One fixed-duration OHLCV observation with an explicit knowledge timestamp."""

    dataset_id: str
    start: datetime
    end: datetime
    available_at: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        if not isinstance(self.dataset_id, str) or not self.dataset_id.strip():
            raise DataError("ResearchBar.dataset_id must be non-empty")
        for name in ("start", "end", "available_at"):
            _aware(name, getattr(self, name))
        if self.end <= self.start:
            raise DataError("ResearchBar.end must occur after start")
        if self.available_at < self.end:
            raise DataError("ResearchBar.available_at cannot precede the bar end")
        values = {
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }
        for name, value in values.items():
            if not math.isfinite(value):
                raise DataError(f"ResearchBar.{name} must be finite, got {value!r}")
        if min(self.open, self.high, self.low, self.close) <= 0.0:
            raise DataError("ResearchBar prices must be positive")
        if self.volume < 0.0:
            raise DataError("ResearchBar.volume must be non-negative")
        if not (
            self.low <= self.open <= self.high
            and self.low <= self.close <= self.high
            and self.low <= self.high
        ):
            raise DataError("ResearchBar OHLC values are inconsistent")

    @property
    def duration(self) -> timedelta:
        return self.end - self.start


@dataclass(frozen=True, slots=True)
class EqualDurationResearchBars:
    """An immutable, ordered collection that rejects mixed-duration or overlapping bars."""

    dataset: ResearchDatasetRef
    bars: tuple[ResearchBar, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.bars, tuple) or not self.bars:
            raise DataError("EqualDurationResearchBars requires a non-empty tuple of bars")
        duration = self.bars[0].duration
        for index, bar in enumerate(self.bars):
            if bar.dataset_id != self.dataset.dataset_id:
                raise DataError(
                    f"bar {index} dataset_id {bar.dataset_id!r} does not match "
                    f"{self.dataset.dataset_id!r}"
                )
            if bar.duration != duration:
                raise DataError("all research bars must have exactly equal duration")
            if index and bar.start < self.bars[index - 1].end:
                raise DataError("research bars must be strictly ordered and non-overlapping")

    @property
    def duration(self) -> timedelta:
        return self.bars[0].duration
