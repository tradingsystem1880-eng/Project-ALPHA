"""CoinMetrics daily network data — the one predictor family independent of price geometry.

Everything else in this study is a transformation of the same OHLCV series, which means a
"confluence" of compression, momentum and correlation signals can be four views of one number. Chain
activity is not: address counts and transfer counts are measured on the ledger, and MVRV compares
market cap against the cost basis of coins that actually moved. If anything here lifts the odds of a
pump, it is genuinely additional information rather than the price chart wearing a different hat.

**Three things about this data can silently corrupt a study, and each is handled explicitly.**

1. **Publication lag.** A row stamped ``D`` summarises activity *during* day D and exists only after
   D closes. Conditioning a decision taken on D on that row reads the future. Every series is
   shifted forward by :data:`~research.xrp_pumps.config.ONCHAIN_PUBLICATION_LAG_DAYS` before it is
   used, and the bias-guard test poisons the tail to prove it.
2. **Staleness.** The mirror ends 2026-05-23, two months before the price data. That is fine for a
   historical study and useless for a live read, so :func:`latest_available` reports the true end
   date and the scorecard marks on-chain rows unavailable rather than carrying the last value
   forward.
3. **Cross-source disagreement.** CoinMetrics' reference price and the Binance perp mirror are
   independent measurements of the same asset. :func:`validate_against_price` correlates them and
   fails loud on a large divergence — if the two disagree, one of the mirrors is not what it claims.

Run ``python -m research.xrp_pumps.onchain --fetch`` to download and pin; the study reads the cache.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl

from alpha_core import DataError
from research.xrp_pumps import config as C

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE = REPO_ROOT / C.RAW_DIR

_MS_PER_DAY = 86_400_000


@dataclass(frozen=True)
class OnchainProvenance:
    """Where one asset's chain data came from and exactly which bytes produced it."""

    asset: str
    url: str
    sha256: str
    n_rows: int
    first_date: str
    last_date: str

    def line(self) -> str:
        return (
            f"{self.asset:<6} {self.first_date} -> {self.last_date} "
            f"{self.n_rows:>6,} rows  sha {self.sha256[:12]}"
        )


def fetch(asset: str, *, timeout: int = 120) -> OnchainProvenance:
    """Download one asset's CSV into the cache. Network-touching; the study never calls it."""
    CACHE.mkdir(parents=True, exist_ok=True)
    url = C.COINMETRICS_URL.format(asset=asset)
    dest = CACHE / f"{asset}.csv"
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 — pinned https URL
        payload = resp.read()
    if len(payload) < 10_000:
        raise DataError(f"{asset}: response was {len(payload)} bytes — not a full CSV")
    dest.write_bytes(payload)
    return provenance(asset)


def provenance(asset: str) -> OnchainProvenance:
    """Hash and summarise a cached file without parsing it into features."""
    path = CACHE / f"{asset}.csv"
    if not path.exists():
        raise FileNotFoundError(f"{asset}: {path} absent — run `--fetch` first")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    df = _read(asset)
    return OnchainProvenance(
        asset=asset,
        url=C.COINMETRICS_URL.format(asset=asset),
        sha256=digest,
        n_rows=df.height,
        first_date=str(df["date"][0])[:10],
        last_date=str(df["date"][-1])[:10],
    )


def _read(asset: str) -> pl.DataFrame:
    """Parse one cached CSV to a date-indexed frame of the columns the study uses.

    Read as text and cast explicitly rather than letting polars infer: these files carry a decade of
    history in which several columns start as integers and later become fractional, and inference
    from the first rows then fails deep in the file. The same defect bit the OHLCV loader.
    """
    path = CACHE / f"{asset}.csv"
    if not path.exists():
        raise FileNotFoundError(f"{asset}: {path} absent — run `--fetch` first")

    raw = pl.read_csv(path, infer_schema_length=0, truncate_ragged_lines=True)
    if "time" not in raw.columns:
        raise DataError(f"{asset}: CSV has no 'time' column — mirror layout changed")

    present = [c for c in C.ONCHAIN_COLUMNS if c in raw.columns]
    if "PriceUSD" not in present:
        raise DataError(f"{asset}: no PriceUSD column — cannot use this asset")

    return (
        raw.select(
            pl.col("time").str.slice(0, 10).str.to_date("%Y-%m-%d", strict=False).alias("date"),
            *[pl.col(c).cast(pl.Float64, strict=False).alias(c) for c in present],
        )
        .drop_nulls("date")
        .filter(pl.col("PriceUSD").is_not_null())
        .sort("date")
        .unique(subset="date", keep="last")
        .sort("date")
    )


def load_panel() -> pl.DataFrame:
    """One wide daily frame: every asset's chain metrics, **already lagged for publication**.

    Columns are ``{asset}_{metric}``. The date column is the date on which the row's contents were
    *knowable*, not the date they describe — that shift is applied here, once, so no downstream
    caller can forget it.
    """
    frames: list[pl.DataFrame] = []
    for asset in C.ONCHAIN_ASSETS:
        try:
            df = _read(asset)
        except (FileNotFoundError, DataError) as exc:
            print(f"  skip {asset}: {exc}")
            continue
        cols = [c for c in C.ONCHAIN_COLUMNS if c in df.columns]
        frames.append(
            df.select(
                # The publication shift: a row describing day D becomes knowable on D + lag.
                (pl.col("date") + pl.duration(days=C.ONCHAIN_PUBLICATION_LAG_DAYS)).alias("date"),
                *[pl.col(c).alias(f"{asset}_{c}") for c in cols],
            )
        )
    if not frames:
        raise DataError("no on-chain files could be read — run `--fetch`")

    panel = frames[0]
    for f in frames[1:]:
        panel = panel.join(f, on="date", how="full", coalesce=True)
    return panel.sort("date")


def derive_market_aggregates(panel: pl.DataFrame) -> pl.DataFrame:
    """Add the market-wide series: total cap, BTC dominance, and the XRP/BTC ratio.

    Dominance is computed over the eight assets present rather than the whole market, so it is
    strictly a *majors* dominance. That is a narrower quantity than the figure quoted on data sites,
    and calling it BTC dominance without the caveat would be wrong — the report states it.
    """
    cap_cols = [
        f"{a}_CapMrktCurUSD" for a in C.ONCHAIN_ASSETS if f"{a}_CapMrktCurUSD" in panel.columns
    ]
    if not cap_cols:
        raise DataError("no market-cap columns present — cannot derive dominance")

    total = pl.sum_horizontal([pl.col(c).fill_null(0.0) for c in cap_cols])
    # Only define the aggregates once enough constituents report: in 2011 the basket is BTC alone,
    # and "100% dominance" would be a true statement about the basket and a false one about crypto.
    reporting = pl.sum_horizontal([pl.col(c).is_not_null().cast(pl.Int32) for c in cap_cols])
    defined = reporting >= C.MIN_ASSETS_FOR_AGGREGATE
    btc_cap = (
        pl.col("btc_CapMrktCurUSD").fill_null(0.0)
        if "btc_CapMrktCurUSD" in panel.columns
        else pl.lit(0.0)
    )
    out = panel.with_columns(
        reporting.alias("n_reporting"),
        pl.when(defined).then(total).otherwise(None).alias("majors_cap"),
        pl.when(defined & (total > 0)).then(btc_cap / total).otherwise(None).alias("btc_dominance"),
    )
    if "xrp_PriceBTC" in out.columns:
        out = out.with_columns(pl.col("xrp_PriceBTC").alias("xrp_btc_ratio"))
    return out


def validate_against_price(
    panel: pl.DataFrame, price_ts: np.ndarray, price_close: np.ndarray, *, tolerance: float = 0.15
) -> float:
    """Cross-check CoinMetrics' XRP reference price against the independent OHLCV mirror.

    Two mirrors sourced from different places should agree on the price of XRP. Correlating them is
    the cheapest possible check that neither file is mislabelled, truncated, or a different asset —
    the failure mode that silently invalidates everything downstream.

    Returns the median absolute relative difference over the overlap; raises when it exceeds
    ``tolerance``, because at that point one of the two series is not what it says it is.
    """
    if "xrp_PriceUSD" not in panel.columns:
        raise DataError("panel has no xrp_PriceUSD to validate")

    # Undo the publication lag for this comparison: we are checking the price *of* a day against
    # the bar *for* that day, not what was knowable when.
    cm = panel.select(
        (pl.col("date") - pl.duration(days=C.ONCHAIN_PUBLICATION_LAG_DAYS)).alias("date"),
        pl.col("xrp_PriceUSD"),
    ).drop_nulls()

    days = (price_ts // _MS_PER_DAY).astype(np.int64)
    bars_df = (
        pl.DataFrame({"day": days, "close": price_close})
        .group_by("day")
        .agg(pl.col("close").last())
    )
    cm = cm.with_columns((pl.col("date").cast(pl.Int64)).alias("day"))

    merged = cm.join(bars_df, on="day", how="inner").drop_nulls()
    if merged.height < 100:
        raise DataError(f"only {merged.height} overlapping days — too few to validate the mirrors")

    a = merged["xrp_PriceUSD"].to_numpy()
    b = merged["close"].to_numpy()
    rel = float(np.median(np.abs(a / b - 1.0)))
    if rel > tolerance:
        raise DataError(
            f"CoinMetrics XRP price and the OHLCV mirror differ by a median {rel:.1%} over "
            f"{merged.height} days — one of the two sources is not XRP/USD. Refusing to proceed."
        )
    return rel


def latest_available(panel: pl.DataFrame, column: str = "xrp_PriceUSD") -> str:
    """The last date at which a column actually has data — the honest end of the on-chain record."""
    sub = panel.filter(pl.col(column).is_not_null())
    return "" if sub.height == 0 else str(sub["date"][-1])[:10]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="CoinMetrics chain data for the XRP pump study")
    ap.add_argument("--fetch", action="store_true", help="download all assets into the cache")
    args = ap.parse_args(argv)

    provs: list[OnchainProvenance] = []
    for asset in C.ONCHAIN_ASSETS:
        try:
            provs.append(fetch(asset) if args.fetch else provenance(asset))
        except Exception as exc:  # noqa: BLE001 — one bad mirror must not stop the rest
            print(f"  FAIL {asset}: {exc}")
    print("-" * 78)
    for p in provs:
        print(p.line())

    if provs:
        panel = derive_market_aggregates(load_panel())
        print("-" * 78)
        print(f"panel: {panel.height:,} days x {panel.width} cols")
        print(
            f"chain data describes days through {C.ONCHAIN_ENDS}, knowable from "
            f"{latest_available(panel)} (+{C.ONCHAIN_PUBLICATION_LAG_DAYS}d publication lag)"
        )
        dom = panel.filter(pl.col("btc_dominance").is_not_null())
        if dom.height:
            as_of = dom.select(pl.col("date").cast(pl.Utf8))["date"][-1][:10]
            # Explicit float(): polars' stubs type Series.min()/max() loosely enough that mypy
            # cannot rule out bytes, and a percent format spec on bytes would fail at runtime.
            latest = float(dom["btc_dominance"][-1])
            lo = float(dom["btc_dominance"].min())  # type: ignore[arg-type]
            hi = float(dom["btc_dominance"].max())  # type: ignore[arg-type]
            print(f"majors BTC dominance: {latest:.1%} on {as_of}  (range {lo:.1%}-{hi:.1%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
