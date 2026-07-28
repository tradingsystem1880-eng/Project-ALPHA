"""Unified price access for scoring Ace's calls, across two tiers of data quality.

A call record is only as good as the price series it is scored against, and the two available
sources are not equivalent:

* **Tier 1 — OHLCV mirrors** (XRP, BTC, ETH, SOL, LTC, LINK). Real bars with highs and lows, so
  "did it reach +10%" can be answered against the *extreme actually traded*.
* **Tier 2 — CoinMetrics daily reference price** (any asset the community mirror carries). Closes
  only. A move that spiked intraday and closed back does not appear, so every Tier-2 measurement is
  a **lower bound** on the excursion, and a call scored this way can be wrong in the caller's
  favour but never against them.

That distinction is carried on every result rather than being buried in a footnote, because mixing
the two silently would make a caller who happened to trade Tier-2 assets look systematically worse
than one who traded Tier-1.

Nothing here fetches at scoring time. :func:`ensure_cached` is the explicit network step; the
scoring path reads the cache and fails loud if an asset is missing.
"""

from __future__ import annotations

import hashlib
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import polars as pl

from alpha_core import DataError
from alpha_patterns import OHLCV
from research.hs_quasimodo.config import SOURCES
from research.hs_quasimodo.data import load

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE = REPO_ROOT / "data" / "cache" / "coinmetrics"
COINMETRICS_URL = "https://raw.githubusercontent.com/coinmetrics/data/master/csv/{asset}.csv"

Tier = Literal["ohlcv", "close_only", "none"]

#: Ticker aliases seen in screenshots that do not match the mirror's own naming.
ALIASES: dict[str, str] = {
    "XBT": "BTC",
    "BTCUSDT": "BTC",
    "ETHUSDT": "ETH",
    "XRPUSDT": "XRP",
    "SOLUSDT": "SOL",
    "MATIC": "POL",
}


@dataclass(frozen=True)
class Series:
    """A price series plus an honest statement of what it can and cannot answer."""

    asset: str
    tier: Tier
    ts: np.ndarray  # epoch ms, strictly increasing, daily
    close: np.ndarray
    high: np.ndarray  # equals close for a close-only series
    low: np.ndarray  # equals close for a close-only series
    source: str

    @property
    def intraday_extremes(self) -> bool:
        """Whether high/low are real. False means every excursion measured is a lower bound."""
        return self.tier == "ohlcv"

    @property
    def first_date(self) -> str:
        return _iso(self.ts[0])

    @property
    def last_date(self) -> str:
        return _iso(self.ts[-1])

    def index_of(self, iso_date: str) -> int:
        """First bar at or after an ISO date; ``len(self)`` when the date is past the end."""
        cutoff = np.datetime64(iso_date[:10], "ms").astype(np.float64)
        hits = np.flatnonzero(self.ts >= cutoff)
        return int(hits[0]) if hits.size else int(self.ts.size)

    def __len__(self) -> int:
        return int(self.ts.size)


def _iso(ts_millis: float) -> str:
    return str(np.datetime64(int(ts_millis), "ms"))[:10]


def canonical(asset: str) -> str:
    """Normalise a ticker as it appears in a screenshot to the symbol used here."""
    raw = asset.strip().upper().replace("/", "").replace("-", "")
    for suffix in ("USDT", "USD", "PERP", "USDC"):
        if raw.endswith(suffix) and len(raw) > len(suffix):
            raw = raw[: -len(suffix)]
    return ALIASES.get(raw, raw)


def _ohlcv_source(symbol: str) -> object | None:
    """The longest-history OHLCV mirror for a symbol whose file is actually on disk.

    Existence of the *file* is part of the question, not an afterthought. The mirrors are declared
    in config but gitignored, so on a fresh checkout — CI, or anyone else's machine — the source
    exists and the data does not. Reporting "ohlcv" in that situation makes every caller believe it
    has intraday extremes right up until the loader raises.
    """
    candidates = [
        s
        for s in SOURCES
        if s.symbol == symbol and s.supports("1d") and (REPO_ROOT / s.path).exists()
    ]
    if not candidates:
        return None
    # Prefer the mirror that runs latest — a call from July 2026 cannot be scored on a series that
    # stops in January 2025, and the perp mirrors run to 2026-07.
    return max(candidates, key=lambda s: 0 if s.extends else 1)


def tier_for(asset: str) -> Tier:
    """What quality of data is actually available for an asset, without parsing it."""
    symbol = canonical(asset)
    if _ohlcv_source(symbol) is not None:
        return "ohlcv"
    if (CACHE / f"{symbol.lower()}.csv").exists():
        return "close_only"
    return "none"


def ensure_cached(asset: str, *, timeout: int = 120) -> bool:
    """Fetch an asset's CoinMetrics CSV if it is not already cached. The one network call.

    Returns True when a usable file is present afterwards. A 404 from the mirror means the asset is
    simply not covered — that is a fact about coverage, not an error, so it returns False rather
    than raising and stopping a batch of thirty assets on the first obscure ticker.
    """
    symbol = canonical(asset)
    if _ohlcv_source(symbol) is not None:
        return True
    dest = CACHE / f"{symbol.lower()}.csv"
    if dest.exists():
        return True

    CACHE.mkdir(parents=True, exist_ok=True)
    url = COINMETRICS_URL.format(asset=symbol.lower())
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 — pinned https
            payload = resp.read()
    except Exception:  # noqa: BLE001 — absence of coverage is an outcome, not a failure
        return False
    if len(payload) < 5_000 or b"PriceUSD" not in payload.split(b"\n", 1)[0]:
        return False
    dest.write_bytes(payload)
    return True


def sha256_of(asset: str) -> str:
    """Hash of the cached CoinMetrics file backing an asset ('' for OHLCV-tier assets)."""
    path = CACHE / f"{canonical(asset).lower()}.csv"
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def load_series(asset: str) -> Series:
    """The best available daily series for an asset. Fails loud when there is none."""
    symbol = canonical(asset)
    src = _ohlcv_source(symbol)
    if src is not None:
        bars, prov = load(src, "1d")  # type: ignore[arg-type]
        return Series(
            asset=symbol,
            tier="ohlcv",
            ts=bars.ts,
            close=bars.close,
            high=bars.high,
            low=bars.low,
            source=f"{prov.exchange}:{prov.key} ({prov.first_ts[:10]}..{prov.last_ts[:10]})",
        )

    path = CACHE / f"{symbol.lower()}.csv"
    if not path.exists():
        raise DataError(
            f"no price data for {symbol!r}: not an OHLCV mirror and not cached from CoinMetrics. "
            "Call ensure_cached() first, or accept that this call cannot be scored."
        )

    raw = pl.read_csv(path, infer_schema_length=0, truncate_ragged_lines=True)
    if "PriceUSD" not in raw.columns:
        raise DataError(f"{symbol}: CoinMetrics file has no PriceUSD column")
    df = (
        raw.select(
            pl.col("time").str.slice(0, 10).str.to_date("%Y-%m-%d", strict=False).alias("date"),
            pl.col("PriceUSD").cast(pl.Float64, strict=False).alias("close"),
        )
        .drop_nulls()
        .sort("date")
        .unique(subset="date", keep="last")
        .sort("date")
    )
    if df.height < 100:
        raise DataError(f"{symbol}: only {df.height} daily closes — too few to score against")

    close = df["close"].to_numpy().astype(np.float64)
    ts = df["date"].to_numpy().astype("datetime64[ms]").astype(np.float64)
    # high == low == close is the honest encoding: this source knows nothing about intraday range,
    # and pretending otherwise would silently turn a lower bound into a point estimate.
    return Series(
        asset=symbol,
        tier="close_only",
        ts=ts,
        close=close,
        high=close.copy(),
        low=close.copy(),
        source=f"coinmetrics:{symbol.lower()} ({_iso(ts[0])}..{_iso(ts[-1])})",
    )


def as_ohlcv(series: Series) -> OHLCV:
    """Wrap a Series as an OHLCV container so the pattern detectors can consume it.

    A close-only series produces zero-range bars. Every detector in ``alpha_patterns`` reads highs
    and lows, so structure detected on such a series is not comparable with structure detected on
    real bars — callers must check ``intraday_extremes`` before drawing that conclusion.
    """
    return OHLCV(
        ts=series.ts,
        open=series.close,
        high=series.high,
        low=series.low,
        close=series.close,
        volume=np.ones(series.ts.size, dtype=np.float64),
        symbol=series.asset,
    )
