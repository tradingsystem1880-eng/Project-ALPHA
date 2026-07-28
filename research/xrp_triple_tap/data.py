"""Loading, normalising and resampling the cached bar data — with provenance attached.

Every market-data API is blocked by this environment's egress policy (51 hosts probed: all
exchanges, all vendors, `connect_rejected`). The only reachable data path is
``raw.githubusercontent.com``, so all series here come from **third-party GitHub mirrors** of
exchange data rather than from the exchanges themselves.

That is a real limitation and it is recorded rather than hidden: :class:`Provenance` travels with
every series and carries the URL and a SHA-256 of the bytes actually read, so any figure in the
study can be traced back to an exact file. The XRP series was additionally checked against the
user's own chart before use — June 2026 low 1.0081, July 2026 low 1.0212, and a 1.0847-1.0945 range
on 2026-07-25 matching the order block they cited independently.

Three on-disk formats are handled, each with its own trap:
- ``parquet_5m``  — epoch-millisecond timestamps, ascending.
- ``cdd_csv_1h``  — CryptoDataDownload layout, **descending**, sometimes headerless.
- ``plain_csv_4h`` — ISO timestamps with a timezone suffix.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl

from alpha_patterns import OHLCV
from research.xrp_triple_tap.config import SOURCES, Source

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Provenance:
    """Where a series came from and exactly which bytes produced it."""

    key: str
    symbol: str
    url: str
    exchange: str
    market: str
    sha256: str
    n_bars_raw: int
    n_bars_4h: int
    first_ts: str
    last_ts: str
    note: str

    def line(self) -> str:
        return (
            f"{self.key:<14} {self.exchange:<9} {self.market:<12} "
            f"{self.first_ts[:10]} -> {self.last_ts[:10]}  {self.n_bars_4h:>6} 4H bars  "
            f"sha {self.sha256[:12]}"
        )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_parquet_5m(path: Path) -> pl.DataFrame:
    return (
        pl.read_parquet(path)
        .with_columns(pl.from_epoch("timestamp", time_unit="ms").alias("ts"))
        .select("ts", "open", "high", "low", "close", "volume")
    )


def _read_cdd_csv(path: Path) -> pl.DataFrame:
    """CryptoDataDownload hourly CSV — headerless or 2-line-preamble, always newest-first."""
    head = path.read_text(errors="ignore").split("\n", 3)[:3]
    if head and head[0].startswith("Timestamps are UTC"):
        raw = pl.read_csv(path, skip_rows=1, truncate_ragged_lines=True)
        cols = {c.lower(): c for c in raw.columns}
        ts = pl.col(cols["date"]).str.to_datetime("%Y-%m-%d %I-%p", strict=False)
        df = raw.select(
            ts.alias("ts"),
            pl.col(cols["open"]).cast(pl.Float64).alias("open"),
            pl.col(cols["high"]).cast(pl.Float64).alias("high"),
            pl.col(cols["low"]).cast(pl.Float64).alias("low"),
            pl.col(cols["close"]).cast(pl.Float64).alias("close"),
            pl.col([c for c in raw.columns if c.lower().startswith("volume")][0])
            .cast(pl.Float64)
            .alias("volume"),
        )
    else:
        # Headerless: unix, date, symbol, open, high, low, close, vol_base, vol_quote
        raw = pl.read_csv(path, has_header=False, truncate_ragged_lines=True)
        df = raw.select(
            pl.from_epoch(pl.col("column_1"), time_unit="s").alias("ts"),
            pl.col("column_4").cast(pl.Float64).alias("open"),
            pl.col("column_5").cast(pl.Float64).alias("high"),
            pl.col("column_6").cast(pl.Float64).alias("low"),
            pl.col("column_7").cast(pl.Float64).alias("close"),
            pl.col("column_8").cast(pl.Float64).alias("volume"),
        )
    return df.drop_nulls().sort("ts")


def _read_plain_csv(path: Path) -> pl.DataFrame:
    raw = pl.read_csv(path, truncate_ragged_lines=True)
    return (
        raw.select(
            pl.col("timestamp")
            .str.replace(r"\+00:00$", "")
            .str.to_datetime(strict=False)
            .alias("ts"),
            pl.col("open").cast(pl.Float64),
            pl.col("high").cast(pl.Float64),
            pl.col("low").cast(pl.Float64),
            pl.col("close").cast(pl.Float64),
            pl.col("volume").cast(pl.Float64),
        )
        .drop_nulls()
        .sort("ts")
    )


def _to_4h(df: pl.DataFrame) -> pl.DataFrame:
    """Resample to 4-hour bars aligned to 00:00 UTC.

    Aggregation is the only correct one for OHLCV: first open, max high, min low, last close, summed
    volume. Bars already at 4H pass through unchanged because each group holds exactly one row.
    """
    return (
        df.sort("ts")
        .group_by_dynamic("ts", every="4h", closed="left")
        .agg(
            pl.col("open").first(),
            pl.col("high").max(),
            pl.col("low").min(),
            pl.col("close").last(),
            pl.col("volume").sum(),
        )
        .drop_nulls()
    )


def load_source(src: Source) -> tuple[OHLCV, Provenance]:
    """Read one cached file, resample to 4H, and return it with its provenance record."""
    path = REPO_ROOT / src.path
    if not path.exists():
        raise FileNotFoundError(
            f"{src.key}: {path} is absent. The fetch step must run first; no network fallback "
            f"exists in this environment (all market-data hosts are egress-blocked)."
        )

    reader = {
        "parquet_5m": _read_parquet_5m,
        "cdd_csv_1h": _read_cdd_csv,
        "plain_csv_4h": _read_plain_csv,
    }[src.fmt]
    raw = reader(path)
    df = _to_4h(raw)

    bars = OHLCV(
        ts=df["ts"].to_numpy().astype("datetime64[ms]").astype(np.float64),
        open=df["open"].to_numpy().astype(np.float64),
        high=df["high"].to_numpy().astype(np.float64),
        low=df["low"].to_numpy().astype(np.float64),
        close=df["close"].to_numpy().astype(np.float64),
        volume=df["volume"].to_numpy().astype(np.float64),
        symbol=src.symbol,
    )
    prov = Provenance(
        key=src.key,
        symbol=src.symbol,
        url=src.url,
        exchange=src.exchange,
        market=src.market,
        sha256=_sha256(path),
        n_bars_raw=raw.height,
        n_bars_4h=df.height,
        first_ts=str(df["ts"][0]),
        last_ts=str(df["ts"][-1]),
        note=src.note,
    )
    return bars, prov


def load_all(keys: tuple[str, ...] | None = None) -> dict[str, tuple[OHLCV, Provenance]]:
    """Load every configured source (or a named subset), skipping any that is not cached."""
    wanted = {s.key: s for s in SOURCES}
    selected = list(wanted.values()) if keys is None else [wanted[k] for k in keys]
    out: dict[str, tuple[OHLCV, Provenance]] = {}
    for src in selected:
        try:
            out[src.key] = load_source(src)
        except FileNotFoundError as exc:  # a missing mirror must not abort the whole study
            print(f"  SKIP {src.key}: {exc}")
    return out


def bar_index_of(bars: OHLCV, iso_date: str) -> int:
    """First bar index at or after an ISO date — used to cut walk-forward splits."""
    cutoff = np.datetime64(iso_date, "ms").astype(np.float64)
    hits = np.flatnonzero(bars.ts >= cutoff)
    return int(hits[0]) if hits.size else len(bars)
