"""Point-in-time reader — the look-ahead firewall. Strategies read ONLY here."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC

import polars as pl
from pydantic import AwareDatetime

from alpha_core import CorporateAction
from alpha_data.corporate import cash_dividends, known_actions, split_factor
from alpha_data.store import ParquetStore

_PRICE_COLS = ("open", "high", "low", "close")


class PointInTimeReader:
    """Returns split-adjusted bars visible at ``when`` — future bars are physically excluded.

    This is the **frame-returning** point-in-time firewall and is intentionally distinct from
    the abstract ``DataSource`` protocol (which returns typed ``Bar`` objects and is reserved
    for a later phase).  A ``PointInTimeReader`` does not need to structurally satisfy
    ``DataSource``.
    """

    def __init__(
        self, store: ParquetStore, actions: Mapping[str, Sequence[CorporateAction]]
    ) -> None:
        self._store = store
        self._actions = actions

    def as_of(self, symbol: str, when: AwareDatetime) -> pl.DataFrame:
        # bars arrive ts-sorted from the store; downstream positional reads depend on it
        bars = self._store.read_bars(symbol).filter(pl.col("ts") <= when)  # firewall
        when_date = when.astimezone(UTC).date()
        known = known_actions(self._actions.get(symbol, []), when_date)  # knowledge gate
        # Price channel: only actions that have already gone ex may rescale prices. A split that
        # is announced but still in the future has not happened yet - every visible bar trades at
        # the old basis, so applying it would return prices nobody traded (spec 6.1 two clocks:
        # knowledge gates visibility, ex_date gates application).
        occurred = [a for a in known if a.ex_date <= when_date]
        if not occurred:
            return bars
        factor = pl.col("ts").map_elements(
            lambda ts: split_factor(ts.date(), occurred), return_dtype=pl.Float64
        )
        adjusted = bars.with_columns(
            [(pl.col(c) * factor).alias(c) for c in _PRICE_COLS]
            + [(pl.col("volume") / factor).alias("volume")]
        )
        return adjusted

    def dividends_as_of(self, symbol: str, when: AwareDatetime) -> list[CorporateAction]:
        """Cash dividends knowable at ``when`` (knowledge-gated), for crediting at pay_date.

        The price channel (``as_of``) adjusts ONLY for splits — an ex-date dividend price
        drop is a real move, left intact. Dividends ride this separate channel as decoupled
        cash events (spec §6.1.4): a dividend is visible once ``knowledge_time <= when`` (on
        the UTC session date, matching the bar/knowledge gate), regardless of whether it has
        gone ex yet, and the engine schedules the cash credit for its ``pay_date``.
        """
        known = known_actions(self._actions.get(symbol, []), when.astimezone(UTC).date())
        return cash_dividends(known)
