"""The adapter seam: every data source returns raw bars + corporate actions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

import polars as pl

from alpha_core import CorporateAction


@dataclass(frozen=True)
class FetchResult:
    """Raw (unadjusted) bars plus the corporate actions for one symbol."""

    symbol: str
    bars: pl.DataFrame  # schema: ts, open, high, low, close, volume
    actions: list[CorporateAction]


class DataAdapter(Protocol):
    """A source of raw market data. `name`/`version` feed snapshot provenance."""

    name: str
    version: str

    def fetch(self, symbol: str, start: date, end: date) -> FetchResult: ...
