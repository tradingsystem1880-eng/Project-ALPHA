"""Persist a FetchResult to the store (bars + actions)."""

from __future__ import annotations

from alpha_data.adapters.base import FetchResult
from alpha_data.store import ParquetStore


def store_fetch_result(store: ParquetStore, result: FetchResult) -> None:
    store.write_bars(result.symbol, result.bars)
    store.write_actions(result.symbol, result.actions)
