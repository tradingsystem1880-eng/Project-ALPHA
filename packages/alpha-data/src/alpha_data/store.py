"""Parquet source-of-truth store for raw (unadjusted) bars and corporate actions."""

from __future__ import annotations

import json
import os
from pathlib import Path

import polars as pl
from pydantic import ValidationError

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
        """Write bars for symbol. REPLACES the symbol's data wholesale (no append/merge).

        Fails loud on duplicate or tz-naive timestamps: every downstream positional read (the PIT
        firewall, the feed's session math) assumes one tz-aware row per session, and a silent
        duplicate would surface much later as an inexplicable off-by-one.
        """
        missing = [c for c in _BAR_COLUMNS if c not in df.columns]
        if missing:
            raise DataError(f"bars for {symbol} missing columns: {missing}")
        ts_dtype = df.schema["ts"]
        if not isinstance(ts_dtype, pl.Datetime) or ts_dtype.time_zone is None:
            raise DataError(f"bars for {symbol} need a tz-aware ts column, got {ts_dtype}")
        if df["ts"].n_unique() != df.height:
            raise DataError(f"bars for {symbol} contain duplicate timestamps")
        path = self._bars_path(symbol)
        path.parent.mkdir(parents=True, exist_ok=True)
        # atomic wholesale replace: a crash mid-write must never destroy the only stored copy
        tmp = path.with_name(path.name + ".tmp")
        try:
            df.select(_BAR_COLUMNS).sort("ts").write_parquet(tmp)
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
        return path

    def read_bars(self, symbol: str) -> pl.DataFrame:
        path = self._bars_path(symbol)
        if not path.exists():
            raise DataError(f"no bars stored for symbol {symbol!r} at {path}")
        return pl.read_parquet(path)

    def list_symbols(self) -> list[str]:
        """Every symbol with stored bars, sorted. Slash-symbols (BTC/USD) are reconstructed
        from their subdir layout, inverting ``_bars_path``; empty when nothing is stored."""
        bars_dir = self.root / "bars"
        if not bars_dir.exists():
            return []
        return sorted(
            str(p.relative_to(bars_dir).with_suffix("")) for p in bars_dir.rglob("*.parquet")
        )

    def _actions_path(self, symbol: str) -> Path:
        if not symbol or ".." in symbol or "\\" in symbol or symbol.startswith("/"):
            raise DataError(f"invalid symbol for storage: {symbol!r}")
        return self.root / "actions" / f"{symbol}.json"

    def write_actions(self, symbol: str, actions: list[CorporateAction]) -> Path:
        """Write actions for symbol. REPLACES the symbol's data wholesale (no append/merge)."""
        path = self._actions_path(symbol)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [a.model_dump(mode="json") for a in actions]
        # atomic wholesale replace (mirrors write_bars)
        tmp = path.with_name(path.name + ".tmp")
        try:
            tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False))
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
        return path

    def read_actions(self, symbol: str) -> list[CorporateAction]:
        path = self._actions_path(symbol)
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text())
            return [CorporateAction.model_validate(d) for d in raw]
        except json.JSONDecodeError as exc:
            raise DataError(f"corrupt actions JSON for {symbol!r} at {path}") from exc
        except ValidationError as exc:
            raise DataError(f"invalid action data for {symbol!r} at {path}: {exc}") from exc
