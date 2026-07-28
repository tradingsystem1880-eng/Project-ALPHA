"""Assemble the per-bar feature panel: compression, market structure, chain activity, calendar.

One row per bar, every column strictly causal as of that bar. This is the feature matrix the whole
study conditions on, and its correctness is load-bearing in a way the statistics are not: a single
column that peeks one bar ahead produces confident, well-intervalled, entirely false findings.

Three sources are joined:

* **Own-asset price** — Bollinger bandwidth, realized volatility, ATR, volume ratio, consolidation
  duration, and wedge state, each converted to a *trailing percentile rank* so a threshold means the
  same thing in 2018 and 2026.
* **Cross-asset price** — correlation with BTC, BTC's own trailing momentum, the asset/BTC ratio's
  position in its range, and market breadth: how many of the majors are simultaneously compressed.
  This is the machinery that makes "the whole crypto market is on the verge of a breakout" a
  measurable proposition rather than a mood.
* **Chain data** — MVRV, active addresses, transfer counts, and majors dominance, joined on the day
  a row became *knowable* (the publication lag is applied in ``onchain.load_panel``, not here).

The joins are all backward as-of joins on timestamp: a bar takes the most recent value that already
existed. Never a forward fill from the future, never an interpolation across a gap.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from alpha_core import DataError
from alpha_patterns import (
    OHLCV,
    WedgeConfig,
    atr,
    bollinger_bandwidth,
    calendar_features,
    consolidation_length,
    detect_wedges,
    log_returns,
    percentile_rank,
    realized_volatility,
    rolling_correlation,
    volume_ratio,
    wedge_panel,
)
from research.hs_quasimodo.config import SOURCES
from research.hs_quasimodo.data import load
from research.xrp_pumps import config as C
from research.xrp_pumps import onchain

_MS_PER_DAY = 86_400_000.0


def source_for(key: str) -> object:
    """The head-and-shoulders study's Source record for a key — same mirrors, same SHA pins."""
    for s in SOURCES:
        if s.key == key:
            return s
    raise KeyError(f"unknown price source {key!r}")


def own_features(bars: OHLCV, timeframe: str) -> pl.DataFrame:
    """Compression, momentum and wedge state computed from one asset's own bars.

    Everything that could be an absolute threshold is expressed as a percentile rank against the
    asset's own trailing year instead. "Bandwidth below 0.04" is a different statement about XRP at
    $0.30 and XRP at $3.00; "bandwidth in its own bottom decile" is the same statement, which is the
    only version that can be pooled across assets or across a decade.
    """
    w = C.WINDOWS
    n = len(bars)
    rank_w = C.bars(w.rank, timeframe)

    bandwidth = bollinger_bandwidth(bars.close, C.bars(w.bandwidth, timeframe))
    realvol = realized_volatility(bars.close, C.bars(w.realvol, timeframe))
    atr_pct = atr(bars, C.bars(w.atr, timeframe)) / np.maximum(bars.close, 1e-12)
    mom = C.bars(w.momentum, timeframe)
    ret_mom = np.concatenate((np.full(mom, np.nan), bars.close[mom:] / bars.close[:-mom] - 1.0))

    wedges = detect_wedges(bars, WedgeConfig(track_bars=C.bars(250, "1d")))
    wp = wedge_panel(bars, wedges)
    # Split the signed apex distance into the two populations that mean different things: still
    # coiling (apex ahead) versus drifted through the apex with nothing having happened.
    #
    # These are emitted as 0/1 flags rather than as a distance with NaN outside a formation. "Not
    # in a wedge" is a *known* state, not a missing measurement, and encoding it as NaN would push
    # every non-wedge bar out of both arms of the comparison — leaving the condition tested against
    # a complement made only of other wedges, which is not the question anyone is asking.
    near = C.bars(30, "1d")
    is_near_apex = wp.active & (wp.bars_past_apex < 0) & (wp.bars_past_apex >= -near)
    is_past_apex = wp.active & (wp.bars_past_apex >= 0)
    apex_distance = np.where(wp.active, wp.bars_past_apex.astype(np.float64), np.nan)

    cal = calendar_features(bars.ts)
    return pl.DataFrame(
        {
            "ts": bars.ts,
            "close": bars.close,
            "volume": bars.volume,
            "log_ret": log_returns(bars.close),
            "bandwidth": bandwidth,
            "bandwidth_pct": percentile_rank(bandwidth, rank_w),
            "realvol": realvol,
            "realvol_pct": percentile_rank(realvol, rank_w),
            "atr_pct": atr_pct,
            "atr_pct_rank": percentile_rank(atr_pct, rank_w),
            "volume_ratio_20": volume_ratio(bars, C.bars(w.volume, timeframe)),
            "consolidation_bars": consolidation_length(
                bars.close,
                C.bars(w.consolidation, timeframe),
                threshold=w.consolidation_threshold,
            ).astype(np.float64),
            "ret_momentum": ret_mom,
            "wedge_active": wp.active,
            "wedge_kind": wp.kind_code.astype(np.float64),
            "wedge_near_apex": is_near_apex.astype(np.float64),
            "wedge_past_apex": is_past_apex.astype(np.float64),
            "apex_distance": apex_distance,
            "month": cal.month.astype(np.float64),
            "day_of_week": cal.day_of_week.astype(np.float64),
            "hour": cal.hour.astype(np.float64),
            "year": cal.year.astype(np.float64),
            "years_since_halving": _years_since_halving(bars.ts),
            "n_bars": np.full(n, float(n)),
        }
    )


def _years_since_halving(ts_millis: np.ndarray) -> np.ndarray:
    """Fractional years since the most recent Bitcoin halving at or before each bar.

    Crypto's most-repeated seasonal story. Included because a trader will ask; read last and with
    the correction applied, because with four cycles in the record the effective sample size for a
    halving-phase claim is four, whatever the bar count says.
    """
    events = np.array([np.datetime64(d, "ms").astype(np.float64) for d in C.HALVINGS])
    idx = np.searchsorted(events, ts_millis, side="right") - 1
    idx = np.clip(idx, 0, events.size - 1)
    return (ts_millis - events[idx]) / (365.25 * _MS_PER_DAY)


def market_features(timeframe: str, subject_key: str) -> pl.DataFrame:
    """Cross-asset structure: BTC correlation and momentum, the /BTC ratio, and market breadth.

    ``breadth_compressed`` is the fraction of the majors whose Bollinger bandwidth sits in the
    bottom quartile of its own trailing year *at that moment*. It is the direct operationalisation
    of "the whole crypto market is on the verge of a breakout": if that claim carries information,
    a high breadth reading should raise the odds of a subsequent move.

    The denominator is the number of assets with data on that bar, so the measure stays defined as
    the basket fills in over the years rather than reading 0 for everything before 2020.
    """
    w = C.WINDOWS
    breadth_keys, leader_key = C.basket_for(subject_key)
    frames: dict[str, pl.DataFrame] = {}
    for key in dict.fromkeys((*breadth_keys, leader_key, subject_key)):
        try:
            bars, _ = load(source_for(key), timeframe)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001 — a missing control must not sink the subject
            print(f"    market: skip {key} ({exc})")
            continue
        bw = bollinger_bandwidth(bars.close, C.bars(w.bandwidth, timeframe))
        frames[key] = pl.DataFrame(
            {
                "ts": bars.ts,
                f"{key}_close": bars.close,
                f"{key}_bw_pct": percentile_rank(bw, C.bars(w.rank, timeframe)),
            }
        ).sort("ts")

    if leader_key not in frames:
        raise DataError(f"market features need {leader_key}; it failed to load")

    merged = frames[leader_key]
    for key, f in frames.items():
        if key != leader_key:
            merged = merged.join_asof(f, on="ts", strategy="backward")

    breadth_cols = [f"{k}_bw_pct" for k in breadth_keys if f"{k}_bw_pct" in merged.columns]
    present = pl.sum_horizontal([pl.col(c).is_not_null().cast(pl.Int32) for c in breadth_cols])
    compressed = pl.sum_horizontal(
        [(pl.col(c) < w.compression_quantile).fill_null(False).cast(pl.Int32) for c in breadth_cols]
    )

    mom = C.bars(w.momentum, timeframe)
    leader_close = merged[f"{leader_key}_close"].to_numpy()
    btc_ret = np.concatenate((np.full(mom, np.nan), leader_close[mom:] / leader_close[:-mom] - 1.0))

    out = merged.with_columns(
        pl.when(present > 0)
        .then(compressed.cast(pl.Float64) / present.cast(pl.Float64))
        .otherwise(None)
        .alias("breadth_compressed"),
        pl.Series("btc_ret_30", btc_ret),
        pl.Series("btc_close", leader_close),
    )

    # Correlation and the ratio only mean something for a non-BTC subject. For BTC itself they are
    # 1.0 and constant by construction, so they are left null rather than fabricated.
    if subject_key != leader_key and f"{subject_key}_close" in merged.columns:
        subj = merged[f"{subject_key}_close"].to_numpy()
        a = log_returns(subj)
        b = log_returns(leader_close)
        corr = rolling_correlation(a, b, C.bars(w.correlation, timeframe))
        ratio = subj / np.maximum(leader_close, 1e-18)
        out = out.with_columns(
            pl.Series("btc_corr_60", corr),
            pl.Series("ratio", ratio),
            pl.Series("ratio_pct", percentile_rank(ratio, C.bars(w.rank, timeframe))),
        )
    return out.select(
        "ts",
        "breadth_compressed",
        "btc_ret_30",
        "btc_close",
        *[c for c in ("btc_corr_60", "ratio", "ratio_pct") if c in out.columns],
    )


def onchain_features() -> pl.DataFrame:
    """Chain metrics for XRP and majors dominance, as a daily frame keyed by knowable date.

    Every column here is already publication-lagged by ``onchain.load_panel``. Growth rates are
    computed over trailing windows on that lagged series, so a 30-day address-growth reading at bar
    ``t`` uses only rows that had been published by ``t``.
    """
    panel = onchain.derive_market_aggregates(onchain.load_panel())
    subj = C.ONCHAIN_SUBJECT
    w = C.WINDOWS

    def col(name: str) -> pl.Expr:
        full = f"{subj}_{name}"
        if full not in panel.columns:
            raise DataError(f"on-chain panel is missing {full}")
        return pl.col(full)

    df = panel.select(
        pl.col("date"),
        col("CapMVRVCur").alias("mvrv"),
        col("AdrActCnt").alias("adr"),
        col("TxCnt").alias("tx"),
        col("PriceUSD").alias("cm_price"),
        col("volume_reported_spot_usd_1d").alias("cm_volume"),
        pl.col("btc_dominance"),
        pl.col("majors_cap"),
    ).sort("date")

    arrays = {name: df[name].to_numpy().astype(np.float64) for name in df.columns if name != "date"}
    mom = w.momentum

    def growth(x: np.ndarray, window: int) -> np.ndarray:
        base = np.concatenate((np.full(window, np.nan), x[:-window]))
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(base > 0.0, x / base - 1.0, np.nan)

    adr_growth = growth(arrays["adr"], mom)
    price_growth = growth(arrays["cm_price"], mom)
    dom = arrays["btc_dominance"]

    return df.with_columns(
        pl.Series("mvrv_pct", _rank_ignoring_nan(arrays["mvrv"], w.mvrv_rank)),
        pl.Series("adr_pct", _rank_ignoring_nan(arrays["adr"], w.rank)),
        pl.Series("adr_growth_30", adr_growth),
        pl.Series("tx_growth_30", growth(arrays["tx"], mom)),
        # Chain use rising while price is not: the classic "accumulation" read, made explicit as a
        # difference of two growth rates rather than left as a vibe about a chart overlay.
        pl.Series("adr_price_divergence", adr_growth - price_growth),
        pl.Series("cm_volume_pct", _rank_ignoring_nan(arrays["cm_volume"], w.rank)),
        pl.Series("dominance_pct", _rank_ignoring_nan(dom, w.rank)),
        pl.Series("dominance_chg_30", growth(dom, mom)),
    )


def _rank_ignoring_nan(values: np.ndarray, window: int) -> np.ndarray:
    """Trailing percentile rank that treats missing values as absent rather than as zero.

    The chain series start at different dates, so a naive rank would put a decade of NaN in the
    denominator and report every early reading as a record high.
    """
    n = values.size
    out = np.full(n, np.nan, dtype=np.float64)
    for i in range(n):
        if not np.isfinite(values[i]):
            continue
        seg = values[max(0, i - window + 1) : i + 1]
        seg = seg[np.isfinite(seg)]
        if seg.size < 2:
            continue
        out[i] = float(np.count_nonzero(seg <= values[i])) / float(seg.size)
    return out


def build(subject_key: str, timeframe: str, *, with_onchain: bool = True) -> pl.DataFrame:
    """The full feature panel for one asset at one timeframe.

    On-chain columns are joined **as-of backward on the day**, and are deliberately left null past
    the end of the chain record rather than forward-filled. A null propagates into the ``valid``
    mask downstream and drops those bars from the on-chain family's sample, which is the honest
    outcome — the alternative is a scorecard confidently reporting a two-month-old MVRV as current.
    """
    bars, prov = load(source_for(subject_key), timeframe)  # type: ignore[arg-type]
    own = own_features(bars, timeframe).sort("ts")
    mkt = market_features(timeframe, subject_key).sort("ts")
    panel = own.join_asof(mkt, on="ts", strategy="backward")

    if with_onchain:
        chain = onchain_features().with_columns(
            (pl.col("date").cast(pl.Int64) * _MS_PER_DAY).cast(pl.Float64).alias("ts")
        )
        panel = panel.join_asof(
            chain.drop("date").sort("ts"),
            on="ts",
            strategy="backward",
            # Past the end of the chain record an as-of join would carry the final row forward for
            # ever. The tolerance caps that at a few days, after which the columns go null.
            tolerance=float(5 * _MS_PER_DAY),
        )

    return panel.with_columns(
        pl.lit(subject_key).alias("asset"),
        pl.lit(timeframe).alias("timeframe"),
        pl.lit(prov.sha256[:16]).alias("source_sha"),
    )
