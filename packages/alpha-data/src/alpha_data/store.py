"""Parquet source-of-truth store for raw (unadjusted) bars and corporate actions."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
from pydantic import ValidationError

from alpha_core import CorporateAction, DataError
from alpha_data._atomic import publish, write_text
from alpha_data.adapters.base import DatasetIdentity, FetchReceipt

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

    def _promotion_path(self, symbol: str) -> Path:
        if not symbol or ".." in symbol or "\\" in symbol or symbol.startswith("/"):
            raise DataError(f"invalid symbol for storage: {symbol!r}")
        return self.root / "promotions" / f"{symbol}.json"

    def promotion_pending(self, symbol: str) -> bool:
        return self._promotion_path(symbol).exists()

    def begin_promotion(self, symbol: str, payload: dict[str, object]) -> None:
        """Publish a fail-closed marker before replacing canonical peer files."""
        path = self._promotion_path(symbol)
        if path.exists():
            raise DataError(f"canonical promotion already pending for {symbol!r}")
        write_text(path, json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")

    def finish_promotion(self, symbol: str) -> None:
        path = self._promotion_path(symbol)
        if not path.exists():
            raise DataError(f"no canonical promotion pending for {symbol!r}")
        path.unlink()

    def _require_stable(self, symbol: str) -> None:
        if self.promotion_pending(symbol):
            raise DataError(
                f"canonical data for {symbol!r} has an interrupted promotion; "
                "run the explicit data repair workflow"
            )

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
        publish(path, df.select(_BAR_COLUMNS).sort("ts").write_parquet)
        return path

    def read_bars(self, symbol: str) -> pl.DataFrame:
        self._require_stable(symbol)
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
        write_text(path, json.dumps(payload, indent=2, sort_keys=True, allow_nan=False))
        return path

    def read_actions(self, symbol: str) -> list[CorporateAction]:
        self._require_stable(symbol)
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

    def _provenance_path(self, symbol: str) -> Path:
        if not symbol or ".." in symbol or "\\" in symbol or symbol.startswith("/"):
            raise DataError(f"invalid symbol for storage: {symbol!r}")
        return self.root / "provenance" / f"{symbol}.json"

    def write_provenance(
        self,
        symbol: str,
        *,
        source: str,
        adapter_version: str,
        parser_version: str,
        identity: DatasetIdentity | None = None,
        receipt: FetchReceipt | None = None,
    ) -> Path:
        """Atomically bind the current symbol bytes to the adapter that pulled them."""
        values: dict[str, object] = {
            "source": source,
            "adapter_version": adapter_version,
            "parser_version": parser_version,
        }
        if any(not value.strip() for value in (source, adapter_version, parser_version)):
            raise DataError("data provenance values must be non-empty strings")
        if (identity is None) != (receipt is None):
            raise DataError("versioned provenance requires both dataset identity and fetch receipt")
        if identity is not None and receipt is not None:
            if identity.symbol != symbol or identity.provider != source:
                raise DataError("provenance dataset does not match symbol/source")
            if (
                receipt.adapter_version != adapter_version
                or receipt.parser_version != parser_version
            ):
                raise DataError("provenance versions do not match fetch receipt")
            values = {
                "schema_version": 2,
                **values,
                "dataset": identity.to_dict(),
                "receipt": receipt.to_dict(),
            }
        path = self._provenance_path(symbol)
        write_text(path, json.dumps(values, indent=2, sort_keys=True, allow_nan=False) + "\n")
        return path

    def clear_provenance(self, symbol: str) -> None:
        """Invalidate provenance before replacing bytes so stale evidence cannot survive a crash."""
        self._provenance_path(symbol).unlink(missing_ok=True)

    def read_provenance(self, symbol: str) -> dict[str, object] | None:
        """Read strict pull provenance, or ``None`` for a legacy/manually seeded symbol."""
        self._require_stable(symbol)
        path = self._provenance_path(symbol)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise DataError(f"corrupt data provenance for {symbol!r} at {path}") from exc
        legacy_fields = {"source", "adapter_version", "parser_version"}
        if not isinstance(raw, dict):
            raise DataError(f"invalid data provenance for {symbol!r} at {path}")
        if set(raw) == legacy_fields:
            if any(
                not isinstance(raw[name], str) or not raw[name].strip() for name in legacy_fields
            ):
                raise DataError(f"invalid data provenance for {symbol!r} at {path}")
            return {name: raw[name] for name in sorted(legacy_fields)}
        versioned_fields = {*legacy_fields, "schema_version", "dataset", "receipt"}
        if set(raw) != versioned_fields or raw.get("schema_version") != 2:
            raise DataError(f"invalid data provenance for {symbol!r} at {path}")
        if any(not isinstance(raw[name], str) or not raw[name].strip() for name in legacy_fields):
            raise DataError(f"invalid data provenance for {symbol!r} at {path}")
        identity = DatasetIdentity.from_dict(raw["dataset"])
        receipt = FetchReceipt.from_dict(raw["receipt"])
        if (
            identity.symbol != symbol
            or identity.provider != raw["source"]
            or receipt.adapter_version != raw["adapter_version"]
            or receipt.parser_version != raw["parser_version"]
        ):
            raise DataError(f"mismatched data provenance for {symbol!r} at {path}")
        return raw
