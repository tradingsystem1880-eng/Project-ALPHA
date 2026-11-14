"""Canonical time bars and their shared UTC-midnight alignment grid."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from alpha_core import DataError

_ACCEPTED = (
    "accepted forms: 1D, D1, 1day, day, daily; <n>m, <n>min, <n>minute(s), <n>T, M<n>; "
    "<n>h, <n>hour(s), H<n> (1..59 minutes, whole hours 1..23, or one day); "
    "bars longer than one day are a design limit: resample stored daily bars instead"
)
_NO_HFT = (
    "ALPHA uses time bars of one minute or longer only; sub-minute bars and tick, "
    "trade, quote or order-book data are excluded by the owner's no-high-frequency-trading rule"
)
_EXCLUDED = {
    "tick",
    "ticks",
    "trade",
    "trades",
    "aggtrades",
    "quote",
    "quotes",
    "book",
    "orderbook",
    "order_book",
    "depth",
    "l2",
    "l3",
}


@dataclass(frozen=True, order=True)
class BarTimeframe:
    minutes: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.minutes, int)
            or isinstance(self.minutes, bool)
            or not (
                1 <= self.minutes <= 59 or 60 <= self.minutes <= 1440 and self.minutes % 60 == 0
            )
        ):
            raise DataError(f"{self.minutes}: {_ACCEPTED}")

    @property
    def canonical(self) -> str:
        return "1D" if self.is_daily else self.ccxt

    @property
    def duration(self) -> timedelta:
        return timedelta(minutes=self.minutes)

    @property
    def is_daily(self) -> bool:
        return self.minutes == 1440

    @property
    def seconds(self) -> int:
        return self.minutes * 60

    @property
    def alpaca(self) -> str:
        if self.is_daily:
            return "1Day"
        return f"{self.minutes // 60}Hour" if self.minutes % 60 == 0 else f"{self.minutes}Min"

    @property
    def ccxt(self) -> str:
        if self.is_daily:
            return "1d"
        return f"{self.minutes // 60}h" if self.minutes % 60 == 0 else f"{self.minutes}m"

    @property
    def nautilus(self) -> str:
        if self.is_daily:
            return "1-DAY"
        return f"{self.minutes // 60}-HOUR" if self.minutes % 60 == 0 else f"{self.minutes}-MINUTE"

    def is_aligned(self, ts: datetime) -> bool:
        """Whole-minute starts on the grid that restarts at every UTC midnight."""
        if ts.tzinfo is None or ts.utcoffset() is None:
            raise DataError("bar alignment requires a timezone-aware timestamp")
        ts = ts.astimezone(UTC)
        return (
            ts.second == 0
            and ts.microsecond == 0
            and (ts.hour * 60 + ts.minute) % self.minutes == 0
        )


DAILY = BarTimeframe(1440)


def parse_timeframe(text: str) -> BarTimeframe:
    """Parse a time-bar spelling, enforcing the owner's no-HFT boundary."""
    if not isinstance(text, str):
        raise DataError(f"{text}: {_ACCEPTED}")
    if re.fullmatch(r"\d+M(?:onths?)?|\d+(?:w|W|weeks?)|\d+(?:y|Y|years?)", text.strip()):
        # "1M" is one month in pandas and CCXT, never one minute: refuse rather than guess.
        raise DataError(f"{text}: {_ACCEPTED}")
    value = text.strip().lower()
    if value in _EXCLUDED or re.fullmatch(
        r"(?:\d+(?:\.\d+)?(?:s|sec(?:ond)?s?|ms|milliseconds?)|(?:s|ms)\d+)", value
    ):
        raise DataError(f"{text}: {_NO_HFT}")
    if value in {"1d", "d1", "1day", "day", "daily"}:
        return DAILY
    match = re.fullmatch(r"(\d+)(m|min|minutes?|t|h|hours?)", value)
    prefix = re.fullmatch(r"([mh])(\d+)", value)
    if match:
        number, unit = match.groups()
    elif prefix:
        unit, number = prefix.groups()
    else:
        raise DataError(f"{text}: {_ACCEPTED}")
    try:
        return BarTimeframe(int(number) * (60 if unit.startswith("h") else 1))
    except (DataError, ValueError) as exc:
        raise DataError(f"{text}: {_ACCEPTED}") from exc


def store_dir(data_dir: Path, timeframe: BarTimeframe) -> Path:
    """Each timeframe owns a complete, independently promoted store root."""
    return data_dir / ("store" if timeframe.is_daily else f"store-{timeframe.canonical}")
