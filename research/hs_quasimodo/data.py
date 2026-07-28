"""Timeframe-aware loading with provenance, native-resolution floors, and history splicing.

Extends the triple-tap loader in three ways the multi-timeframe study needs:

1. **A ``timeframe`` argument.** Resampling is only ever *downward* — 5-minute bars aggregate to
   15m/1h/4h/1d, but a 1-hour CSV can never produce a 15-minute bar. Asking for one raises rather
   than silently upsampling, because a fabricated bar would flow straight into a detector and out
   into a result.
2. **History splicing.** The 2017 CryptoDataDownload files extend the Bitstamp series back roughly
   eighteen months. They are the same exchange and quote currency, so the seam is a continuation
   rather than a venue change — but it is still a seam, and it is recorded in provenance and
   validated on the overlap before being used.
3. **Provenance carries both files' hashes**, so any figure traces to exact bytes.

Every market-data API is egress-blocked in this environment, so all series come from third-party
GitHub mirrors. That is a real limitation, recorded rather than hidden.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl

from alpha_core import DataError
from alpha_patterns import OHLCV
from research.hs_quasimodo.config import TF_MINUTES, Source

REPO_ROOT = Path(__file__).resolve().parents[2]

_EVERY = {"15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}


@dataclass(frozen=True)
class Provenance:
    """Where a series came from, and exactly which bytes produced it."""

    key: str
    symbol: str
    timeframe: str
    url: str
    exchange: str
    market: str
    sha256: str
    sha256_extension: str  # "" when no earlier history was spliced
    splice_ts: str  # boundary timestamp, "" when unspliced
    n_bars_raw: int
    n_bars: int
    first_ts: str
    last_ts: str
    note: str

    def line(self) -> str:
        seam = f" +ext@{self.splice_ts[:10]}" if self.splice_ts else ""
        return (
            f"{self.key:<14} {self.timeframe:<4} {self.exchange:<9} "
            f"{self.first_ts[:10]} -> {self.last_ts[:10]} {self.n_bars:>8,} bars"
            f"  sha {self.sha256[:10]}{seam}"
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
    """CryptoDataDownload hourly CSV — headerless or 2-line preamble, always newest-first."""
    head = path.read_text(errors="ignore").split("\n", 3)[:3]
    if head and head[0].startswith("Timestamps are UTC"):
        raw = pl.read_csv(path, skip_rows=1, truncate_ragged_lines=True, infer_schema_length=0)
        cols = {c.lower(): c for c in raw.columns}
        vol_col = next(c for c in raw.columns if c.lower().startswith("volume"))
        # These files stamp the hour as "2017-07-01 11-AM". polars refuses %I-%p (it wants hour and
        # minute together, or neither), so normalise to "11:00 AM" before parsing.
        stamp = (
            pl.col(cols["date"])
            .str.replace(r"-(AM|PM)$", ":00 $1")
            .str.to_datetime("%Y-%m-%d %I:%M %p", strict=False)
        )
        df = raw.select(
            stamp.alias("ts"),
            pl.col(cols["open"]).cast(pl.Float64).alias("open"),
            pl.col(cols["high"]).cast(pl.Float64).alias("high"),
            pl.col(cols["low"]).cast(pl.Float64).alias("low"),
            pl.col(cols["close"]).cast(pl.Float64).alias("close"),
            pl.col(vol_col).cast(pl.Float64).alias("volume"),
        )
    else:
        # Read every column as text and cast explicitly. Schema inference on the first rows is
        # unsafe here: BTC traded at whole-number prices in early 2025, so polars types the high
        # column as an integer and then fails on the first fractional price deeper in the file.
        raw = pl.read_csv(path, has_header=False, truncate_ragged_lines=True, infer_schema_length=0)
        df = raw.select(
            pl.from_epoch(pl.col("column_1").cast(pl.Int64), time_unit="s").alias("ts"),
            pl.col("column_4").cast(pl.Float64).alias("open"),
            pl.col("column_5").cast(pl.Float64).alias("high"),
            pl.col("column_6").cast(pl.Float64).alias("low"),
            pl.col("column_7").cast(pl.Float64).alias("close"),
            pl.col("column_8").cast(pl.Float64).alias("volume"),
        )
    return df.drop_nulls().sort("ts")


def _read_plain_csv(path: Path) -> pl.DataFrame:
    return (
        pl.read_csv(path, truncate_ragged_lines=True)
        .select(
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


_READERS = {
    "parquet_5m": _read_parquet_5m,
    "cdd_csv_1h": _read_cdd_csv,
    "plain_csv_4h": _read_plain_csv,
}


def _resample(df: pl.DataFrame, timeframe: str) -> pl.DataFrame:
    """Aggregate to ``timeframe``. The only correct OHLCV reduction, aligned to the epoch."""
    return (
        df.sort("ts")
        .group_by_dynamic("ts", every=_EVERY[timeframe], closed="left")
        .agg(
            pl.col("open").first(),
            pl.col("high").max(),
            pl.col("low").min(),
            pl.col("close").last(),
            pl.col("volume").sum(),
        )
        .drop_nulls()
    )


def load(src: Source, timeframe: str) -> tuple[OHLCV, Provenance]:
    """Read one source at one timeframe, splicing earlier history when configured.

    Raises ``DataError`` if ``timeframe`` is finer than the source's native resolution — the whole
    point of ``Source.native_minutes``.
    """
    if timeframe not in TF_MINUTES:
        raise DataError(f"unknown timeframe {timeframe!r}")
    if not src.supports(timeframe):
        raise DataError(
            f"{src.key} is {src.native_minutes}-minute native; {timeframe} would require "
            f"upsampling, which would fabricate bars. Refusing."
        )

    path = REPO_ROOT / src.path
    if not path.exists():
        raise FileNotFoundError(f"{src.key}: {path} is absent (fetch step must run first)")

    reader = _READERS[src.fmt]
    raw = reader(path)
    ext_sha, splice_ts = "", ""

    if src.extends:
        ext_path = REPO_ROOT / src.extends
        if ext_path.exists():
            older = reader(ext_path)
            boundary = raw["ts"].min()
            older = older.filter(pl.col("ts") < boundary)
            if older.height:
                _validate_splice(older, raw, src.key)
                raw = pl.concat([older, raw]).sort("ts")
                ext_sha = _sha256(ext_path)
                splice_ts = str(boundary)

    df = _resample(raw, timeframe)
    if df.height < 100:
        raise DataError(f"{src.key} at {timeframe}: only {df.height} bars — too few to study")

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
        timeframe=timeframe,
        url=src.url,
        exchange=src.exchange,
        market=src.market,
        sha256=_sha256(path),
        sha256_extension=ext_sha,
        splice_ts=splice_ts,
        n_bars_raw=raw.height,
        n_bars=df.height,
        first_ts=str(df["ts"][0]),
        last_ts=str(df["ts"][-1]),
        note=src.note,
    )
    return bars, prov


def _validate_splice(older: pl.DataFrame, newer: pl.DataFrame, key: str) -> None:
    """Fail loud if the two segments disagree wildly at the seam.

    Same exchange and quote currency, so the last close of the old segment and the first close of
    the new one should be close. A large jump means the files are not the series we think they are —
    a different venue, a redenomination, or a corrupt mirror.
    """
    last_old = float(older["close"][-1])
    first_new = float(newer["close"][0])
    if last_old <= 0.0 or first_new <= 0.0:
        raise DataError(f"{key}: non-positive close at the splice seam")
    jump = abs(first_new / last_old - 1.0)
    if jump > 0.5:
        raise DataError(
            f"{key}: {jump:.1%} price jump at the splice seam ({last_old} -> {first_new}). "
            "Refusing to splice — the two files are probably not the same series."
        )


def bar_index_of(bars: OHLCV, iso_date: str) -> int:
    """First bar index at or after an ISO date — used to cut the walk-forward split."""
    cutoff = np.datetime64(iso_date, "ms").astype(np.float64)
    hits = np.flatnonzero(bars.ts >= cutoff)
    return int(hits[0]) if hits.size else len(bars)


def iso_of(bars: OHLCV, index: int) -> str:
    """ISO timestamp of a bar index, for human-readable event rows."""
    if not 0 <= index < len(bars):
        return ""
    return str(np.datetime64(int(bars.ts[index]), "ms"))
