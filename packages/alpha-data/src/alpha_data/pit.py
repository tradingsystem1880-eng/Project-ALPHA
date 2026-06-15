"""Point-in-time reader — the look-ahead firewall. Strategies read ONLY here."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

import polars as pl

from alpha_core import CorporateAction
from alpha_data.corporate import known_actions, split_factor
from alpha_data.store import ParquetStore

_PRICE_COLS = ("open", "high", "low", "close")


class PointInTimeReader:
    """Returns split-adjusted bars visible at ``when`` — future bars are physically excluded."""

    def __init__(
        self, store: ParquetStore, actions: Mapping[str, Sequence[CorporateAction]]
    ) -> None:
        self._store = store
        self._actions = actions

    def as_of(self, symbol: str, when: datetime) -> pl.DataFrame:
        bars = self._store.read_bars(symbol).filter(pl.col("ts") <= when)  # firewall
        known = known_actions(self._actions.get(symbol, []), when.date())  # knowledge gate
        if not known:
            return bars
        factor = pl.col("ts").map_elements(
            lambda ts: split_factor(ts.date(), known), return_dtype=pl.Float64
        )
        adjusted = bars.with_columns(
            [(pl.col(c) * factor).alias(c) for c in _PRICE_COLS]
            + [(pl.col("volume") / factor).alias("volume")]
        )
        return adjusted
