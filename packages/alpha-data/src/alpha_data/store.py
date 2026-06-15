"""Parquet source-of-truth store for raw (unadjusted) bars and corporate actions."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from alpha_core import CorporateAction, DataError

_BAR_COLUMNS = ["ts", "open", "high", "low", "close", "volume"]


class ParquetStore:
    """Stores raw bars as one Parquet file per symbol under ``<root>/bars/``.

    This is a raw, unadjusted-storage layer that intentionally does NOT enforce
    ``Bar`` invariants — vendor data may legitimately contain zero volume, etc.
    Validation happens at ``Bar`` construction / ingest time, not here.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _bars_path(self, symbol: str) -> Path:
        if not symbol or ".." in symbol or "\\" in symbol or symbol.startswith("/"):
            raise DataError(f"invalid symbol for storage: {symbol!r}")
        # slash kept as a subdirectory (BTC/USD -> bars/BTC/USD.parquet) so it never
        # collides with a literal BTC_USD; `..` etc. are rejected above for traversal safety.
        return self.root / "bars" / f"{symbol}.parquet"

    def write_bars(self, symbol: str, df: pl.DataFrame) -> Path:
        missing = [c for c in _BAR_COLUMNS if c not in df.columns]
        if missing:
            raise DataError(f"bars for {symbol} missing columns: {missing}")
        path = self._bars_path(symbol)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.select(_BAR_COLUMNS).sort("ts").write_parquet(path)
        return path

    def read_bars(self, symbol: str) -> pl.DataFrame:
        path = self._bars_path(symbol)
        if not path.exists():
            raise DataError(f"no bars stored for symbol {symbol!r} at {path}")
        return pl.read_parquet(path)

    def _actions_path(self, symbol: str) -> Path:
        if not symbol or ".." in symbol or "\\" in symbol or symbol.startswith("/"):
            raise DataError(f"invalid symbol for storage: {symbol!r}")
        return self.root / "actions" / f"{symbol}.json"

    def write_actions(self, symbol: str, actions: list[CorporateAction]) -> Path:
        path = self._actions_path(symbol)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [a.model_dump(mode="json") for a in actions]
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        return path

    def read_actions(self, symbol: str) -> list[CorporateAction]:
        path = self._actions_path(symbol)
        if not path.exists():
            return []
        raw = json.loads(path.read_text())
        return [CorporateAction.model_validate(d) for d in raw]
