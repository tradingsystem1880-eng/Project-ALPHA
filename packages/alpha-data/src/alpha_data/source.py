"""Typed point-in-time ``DataSource`` — the seam the Phase-2 backtest engine consumes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import AwareDatetime

from alpha_core import Bar, CorporateAction
from alpha_data.pit import PointInTimeReader
from alpha_data.store import ParquetStore


class PointInTimeSource:
    """A point-in-time ``DataSource`` over a ``ParquetStore``.

    Structurally satisfies ``alpha_core.protocols.DataSource``: ``as_of`` returns validated,
    chronologically-ordered typed ``Bar`` objects — never a raw DataFrame — so the engine and
    strategies read only point-in-time-filtered data. It *composes* ``PointInTimeReader`` (no
    duplicated logic), so the same look-ahead firewall, split back-adjustment, and knowledge
    gate apply. Dividends ride the reader's separate decoupled cash channel (spec §6.1.4),
    surfaced here via ``dividends_as_of`` so the engine has a single seam for both.
    """

    def __init__(
        self, store: ParquetStore, actions: Mapping[str, Sequence[CorporateAction]]
    ) -> None:
        self._store = store
        self._reader = PointInTimeReader(store, actions)

    def available_symbols(self) -> list[str]:
        return self._store.list_symbols()

    def as_of(self, symbol: str, when: AwareDatetime) -> list[Bar]:
        """Validated, chronologically-ordered bars knowable at ``when`` (split-adjusted)."""
        frame = self._reader.as_of(symbol, when)
        return [
            Bar(
                symbol=symbol,
                ts=row["ts"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )
            for row in frame.iter_rows(named=True)
        ]

    def dividends_as_of(self, symbol: str, when: AwareDatetime) -> list[CorporateAction]:
        """Knowledge-gated cash dividends for crediting at pay_date (see ``PointInTimeReader``)."""
        return self._reader.dividends_as_of(symbol, when)
