"""Point-in-time split adjustment for OHLCV bars. See spec §6.1."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

import polars as pl

from alpha_core import CorporateAction
from alpha_data.corporate import known_actions, split_factor


def adjust_bars(
    bars: pl.DataFrame,
    actions: Sequence[CorporateAction],
    as_of: datetime,
) -> pl.DataFrame:
    """Return ``bars`` back-adjusted for all splits known as of ``as_of``.

    Only SPLITs whose knowledge_time <= as_of are applied (knowledge gate).
    Each bar's price columns are multiplied by split_factor(ts.date(), known).
    """
    known = known_actions(actions, as_of.date())
    if not known:
        return bars

    price_cols = ["open", "high", "low", "close"]

    def _factor(ts: datetime) -> float:
        return split_factor(ts.date(), known)

    factors = pl.Series(
        "factor",
        [_factor(ts) for ts in bars["ts"].to_list()],
    )

    adjusted = bars.with_columns([pl.col(c) * factors for c in price_cols])
    return adjusted
