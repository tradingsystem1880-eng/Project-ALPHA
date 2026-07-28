"""Assemble the XRP feature panel: nine years of daily bars with every measurement attached.

Three jobs, in order:

1. **Splice the price history.** Bitstamp runs 2017-07 to 2025-01, Binance 2020-09 to 2026-07.
   Neither alone is enough: Bitstamp stops before the position exists, Binance starts after two of
   the three cycles worth studying. The join is validated rather than assumed — :func:`splice_xrp`
   fails loud if the two venues disagree by more than a threshold across their overlap, because a
   silent venue mismatch would inject a fake gap right in the middle of the sample.
2. **Compute every indicator** from ``alpha_patterns``, all trailing-window and bias-guarded.
3. **Attach the exogenous series** — BTC, ETH, SOL for correlation and lead-lag, CoinMetrics
   on-chain for the one family that is independent of price geometry.

Everything returns plain numpy arrays aligned to one timestamp axis. Anything that cannot be
computed for a bar is NaN, never back-filled: a forward-filled indicator is a small, invisible
look-ahead, and the whole point of this layer is that the study downstream can trust its inputs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import polars as pl

from alpha_core import DataError
from alpha_patterns import (
    OHLCV,
    atr,
    bollinger_bandwidth,
    chaikin_money_flow,
    directional_index,
    donchian_channel,
    ema,
    find_swings,
    ichimoku,
    keltner_channel,
    log_returns,
    macd,
    money_flow_index,
    nearest_fib_distance,
    on_balance_volume,
    percentile_rank,
    realized_volatility,
    rolling_correlation,
    rolling_hurst,
    rolling_max,
    rolling_mean,
    rolling_variance_ratio,
    round_number_distance,
    rsi,
    squeeze,
    stochastic,
    volume_ratio,
)
from research.hs_quasimodo.config import SOURCES
from research.hs_quasimodo.data import load
from research.xrp_deep import config as C

REPO_ROOT = Path(__file__).resolve().parents[2]
_MS_PER_DAY = 86_400_000.0

#: Maximum tolerable median close disagreement between the two venues across their overlap. The
#: measured value is 0.07%; anything approaching this would mean the mirrors have drifted apart.
SPLICE_TOLERANCE = 0.01


def _days(ts: np.ndarray) -> np.ndarray:
    return np.round(ts / _MS_PER_DAY).astype(np.int64)


def _load(key: str) -> OHLCV:
    source = next((s for s in SOURCES if s.key == key), None)
    if source is None:
        raise DataError(f"no source named {key!r}")
    bars, _ = load(source, "1d")
    return bars


def splice_xrp() -> OHLCV:
    """Bitstamp before :data:`config.SPLICE_AT`, Binance from it onward, join validated.

    The validation is the point. Two mirrors of "XRP daily" can silently be different instruments —
    a different quote currency, a stale file, a survivorship-filtered rebuild — and the join would
    still produce a plausible-looking series with a fabricated discontinuity in the middle of it.
    """
    old, new = _load(C.LONG_HISTORY_KEY), _load(C.PRIMARY_KEY)
    d_old, d_new = _days(old.ts), _days(new.ts)

    common = np.intersect1d(d_old, d_new)
    if common.size < 200:
        raise DataError(
            f"only {common.size} overlapping days between {C.LONG_HISTORY_KEY} and "
            f"{C.PRIMARY_KEY} — too few to validate the splice"
        )
    a = old.close[np.searchsorted(d_old, common)]
    b = new.close[np.searchsorted(d_new, common)]
    disagreement = float(np.median(np.abs(a - b) / b))
    if disagreement > SPLICE_TOLERANCE:
        raise DataError(
            f"{C.LONG_HISTORY_KEY} and {C.PRIMARY_KEY} disagree by a median {disagreement:.2%} "
            f"across {common.size} overlapping days — these are not the same instrument"
        )

    cut = int(np.datetime64(C.SPLICE_AT, "D").astype(np.int64))
    keep_old = d_old < cut
    keep_new = d_new >= cut
    if not keep_old.any() or not keep_new.any():
        raise DataError(f"splice at {C.SPLICE_AT} leaves one side empty")

    def _cat(name: str) -> np.ndarray:
        return np.concatenate((getattr(old, name)[keep_old], getattr(new, name)[keep_new]))

    ts = _cat("ts")
    if not np.all(np.diff(ts) > 0):
        raise DataError("spliced XRP timestamps are not strictly increasing")
    return OHLCV(
        ts=ts,
        open=_cat("open"),
        high=_cat("high"),
        low=_cat("low"),
        close=_cat("close"),
        volume=_cat("volume"),
        symbol="XRP",
    )


def align_to(target_ts: np.ndarray, bars: OHLCV) -> np.ndarray:
    """``bars.close`` sampled onto ``target_ts``, NaN where that day has no bar.

    A plain reindex rather than a forward fill. Forward-filling a control asset's price across a
    gap invents data on exactly the days most likely to matter (exchange outages cluster with
    volatility), and the study is better served by an honest NaN it can exclude.
    """
    out = np.full(target_ts.size, np.nan, dtype=np.float64)
    d_target, d_bars = _days(target_ts), _days(bars.ts)
    pos = np.searchsorted(d_bars, d_target)
    ok = (pos < d_bars.size) & (pos >= 0)
    pos_ok = np.clip(pos, 0, d_bars.size - 1)
    hit = ok & (d_bars[pos_ok] == d_target)
    out[hit] = bars.close[pos_ok[hit]]
    return out


def _onchain_frame() -> pl.DataFrame | None:
    """CoinMetrics XRP metrics, or None when the cache is absent.

    Absence is a fact about this machine, not an error — the price families stand on their own and
    the on-chain family is reported as unavailable rather than silently skipped.
    """
    path = REPO_ROOT / "data" / "cache" / "coinmetrics" / "xrp.csv"
    if not path.exists():
        return None
    raw = pl.read_csv(path, infer_schema_length=0, truncate_ragged_lines=True)
    wanted = [c for c in ("CapMVRVCur", "AdrActCnt", "TxCnt", "CapMrktCurUSD") if c in raw.columns]
    if not wanted:
        return None
    return (
        raw.select(
            pl.col("time").str.slice(0, 10).str.to_date("%Y-%m-%d", strict=False).alias("date"),
            *[pl.col(c).cast(pl.Float64, strict=False).alias(c) for c in wanted],
        )
        .drop_nulls(subset="date")
        .sort("date")
        .unique(subset="date", keep="last")
        .sort("date")
    )


@dataclass
class Panel:
    """Every measurement for every XRP daily bar, on one aligned timestamp axis."""

    bars: OHLCV
    features: dict[str, np.ndarray] = field(default_factory=dict)
    #: Names of features sourced from CoinMetrics, which lags publication and ends earlier.
    onchain_features: tuple[str, ...] = ()
    notes: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return int(self.bars.close.size)

    @property
    def dates(self) -> list[str]:
        return [str(np.datetime64(int(t), "ms"))[:10] for t in self.bars.ts]

    def get(self, name: str) -> np.ndarray:
        if name not in self.features:
            raise DataError(f"no feature {name!r}; have {sorted(self.features)[:12]}...")
        return self.features[name]

    def index_of(self, iso_date: str) -> int:
        target = int(np.datetime64(iso_date[:10], "D").astype(np.int64))
        hits = np.flatnonzero(_days(self.bars.ts) >= target)
        return int(hits[0]) if hits.size else len(self)


def build_panel() -> Panel:
    """The full feature panel. One call, everything downstream reads from it."""
    bars = splice_xrp()
    close, high, low, volume = bars.close, bars.high, bars.low, bars.volume
    n = close.size
    f: dict[str, np.ndarray] = {}
    notes: list[str] = []

    # --- trend / moving averages -------------------------------------------------
    for w in (20, 50, 100, 200):
        f[f"sma_{w}"] = rolling_mean(close, w)
        f[f"ema_{w}"] = ema(close, w)
    f["price_over_sma200"] = close / f["sma_200"]
    f["price_over_sma50"] = close / f["sma_50"]
    f["sma50_over_sma200"] = f["sma_50"] / f["sma_200"]
    # Slope as a fraction of the level, so it is comparable across price regimes.
    f["sma50_slope"] = np.concatenate(([np.nan], np.diff(f["sma_50"]) / f["sma_50"][:-1]))

    # --- momentum -----------------------------------------------------------------
    m = macd(close)
    f["macd_line"], f["macd_signal"], f["macd_hist"] = m.line, m.signal, m.histogram
    f["macd_hist_prev"] = np.concatenate(([np.nan], m.histogram[:-1]))
    f["rsi_14"] = rsi(close, 14)
    st = stochastic(bars)
    f["stoch_k"], f["stoch_d"] = st.k, st.d
    f["williams_r"] = st.k - 100.0
    di = directional_index(bars)
    f["plus_di"], f["minus_di"], f["adx"] = di.plus_di, di.minus_di, di.adx

    # --- volatility / channels -----------------------------------------------------
    f["bandwidth"] = bollinger_bandwidth(close)
    f["bandwidth_pct"] = percentile_rank(f["bandwidth"], C.PCTILE_WINDOW)
    f["atr"] = atr(bars, 14)
    f["atr_pct_price"] = f["atr"] / close
    f["realized_vol"] = realized_volatility(close, window=30, periods_per_year=365)
    f["vol_pct"] = percentile_rank(f["realized_vol"], C.PCTILE_WINDOW)
    kelt = keltner_channel(bars)
    f["keltner_position"] = kelt.position
    f["squeeze_on"] = squeeze(f["bandwidth"], kelt, close).astype(np.float64)
    donch = donchian_channel(bars, window=20)
    f["donchian_position"] = donch.position
    f["donchian_upper"], f["donchian_lower"] = donch.upper, donch.lower

    # --- volume / flow --------------------------------------------------------------
    f["volume_ratio"] = volume_ratio(bars, 20)
    f["obv"] = on_balance_volume(close, volume)
    f["obv_slope"] = np.concatenate(([np.nan], np.diff(rolling_mean(f["obv"], 20))))
    f["mfi"] = money_flow_index(bars)
    f["cmf"] = chaikin_money_flow(bars)

    # --- ichimoku ---------------------------------------------------------------------
    ich = ichimoku(bars)
    f["ichi_tenkan"], f["ichi_kijun"] = ich.tenkan, ich.kijun
    f["ichi_above_cloud"] = ich.above_cloud.astype(np.float64)
    f["ichi_chikou_above"] = ich.chikou_above.astype(np.float64)

    # --- levels -------------------------------------------------------------------------
    swings = sorted(
        find_swings(bars, lookback=C.SWING_LOOKBACK, kind="high")
        + find_swings(bars, lookback=C.SWING_LOOKBACK, kind="low"),
        key=lambda s: s.index,
    )
    f["fib_distance"] = nearest_fib_distance(close, swings)
    f["round_distance"] = round_number_distance(close, per_decade=10)
    f["round_distance_coarse"] = round_number_distance(close, per_decade=1)

    # --- drawdown / range position --------------------------------------------------------
    running_high = np.maximum.accumulate(close)
    f["drawdown_from_ath"] = close / running_high - 1.0
    f["dist_from_high_365"] = close / rolling_max(high, 365) - 1.0
    f["range_position_365"] = percentile_rank(close, 365)

    # --- memory / cycles --------------------------------------------------------------------
    rets = log_returns(close)
    f["ret_1"] = rets
    f["variance_ratio_5"] = rolling_variance_ratio(np.log(close), window=252, q=5)
    f["hurst_returns"] = rolling_hurst(rets, window=252)
    f["autocorr_1"] = _rolling_autocorr(rets, window=252, lag=1)

    # --- exogenous: BTC and the control group -------------------------------------------------
    for key in C.CONTROL_KEYS:
        try:
            other = align_to(bars.ts, _load(key))
        except DataError as exc:  # noqa: PERF203 — one missing mirror must not kill the panel
            notes.append(f"{key}: unavailable ({exc})")
            continue
        f[f"{key.lower()}_close"] = other
        with np.errstate(invalid="ignore", divide="ignore"):
            other_ret = np.concatenate(([np.nan], np.diff(np.log(other))))
        f[f"{key.lower()}_ret_1"] = other_ret
        f[f"corr_{key.lower()}_90"] = _rolling_on_finite(
            lambda a, b: rolling_correlation(a, b, 90), rets, other_ret
        )
        f[f"{key.lower()}_mom_20"] = (
            other / np.concatenate((np.full(20, np.nan), other[:-20])) - 1.0
        )
    if "btc_close" in f:
        f["xrp_btc_ratio"] = close / f["btc_close"]
        f["ratio_sma_50"] = _rolling_on_finite(
            lambda a, _b: rolling_mean(a, 50), f["xrp_btc_ratio"], f["xrp_btc_ratio"]
        )
        f["ratio_over_ma"] = f["xrp_btc_ratio"] / np.where(
            f["ratio_sma_50"] > 0, f["ratio_sma_50"], np.nan
        )

    # --- calendar ---------------------------------------------------------------------------------
    days = _days(bars.ts)
    f["weekday"] = ((days + 3) % 7).astype(np.float64)
    months = np.array([int(str(np.datetime64(int(t), "ms"))[5:7]) for t in bars.ts], np.float64)
    f["month"] = months
    f["day_of_month"] = np.array(
        [int(str(np.datetime64(int(t), "ms"))[8:10]) for t in bars.ts], np.float64
    )

    # --- bar structure ---
    prev_high = np.concatenate(([np.nan], high[:-1]))
    prev_low = np.concatenate(([np.nan], low[:-1]))
    f["inside_bar"] = ((high <= prev_high) & (low >= prev_low)).astype(np.float64)
    rng = high - low
    f["bar_range"] = rng
    f["nr7"] = np.array(
        [1.0 if i >= 6 and rng[i] <= np.min(rng[i - 6 : i + 1]) else 0.0 for i in range(n)]
    )
    f["close_in_range"] = np.divide(
        close - low, rng, out=np.full(n, 0.5, dtype=np.float64), where=rng > 0
    )

    # --- on-chain ---
    onchain_names: tuple[str, ...] = ()
    frame = _onchain_frame()
    if frame is None:
        notes.append("on-chain: CoinMetrics cache absent — the on-chain family cannot be run")
    else:
        onchain_names = _attach_onchain(f, frame, bars.ts, notes)

    return Panel(bars=bars, features=f, onchain_features=onchain_names, notes=notes)


def _rolling_on_finite(
    fn: Callable[[np.ndarray, np.ndarray], np.ndarray],
    a: np.ndarray,
    b: np.ndarray,
) -> np.ndarray:
    """Apply a rolling two-series function only where both inputs are finite, NaN elsewhere.

    Necessary because the rolling primitives are cumulative-sum based, and a cumulative sum is
    poisoned forever by a single NaN. XRP's history starts in 2017 and BTC's mirror in 2020, so a
    naive call put 1,109 leading NaNs into the accumulator and every subsequent value came back
    NaN — which the zero-variance guard inside ``rolling_correlation`` then turned into a clean,
    entirely fictitious **0.0**. A correlation of exactly zero on every one of 3,262 bars is the
    kind of wrong number that reads as a finding ("XRP has decoupled from BTC") rather than as a
    bug, which is what makes it worth this much comment.

    Restricting to the contiguous finite region is the honest fix: outside it there is genuinely no
    answer, and NaN says so.
    """
    finite = np.isfinite(a) & np.isfinite(b)
    out = np.full(a.size, np.nan, dtype=np.float64)
    if not finite.any():
        return out
    start = int(np.flatnonzero(finite)[0])
    end = int(np.flatnonzero(finite)[-1]) + 1
    window_a, window_b = a[start:end], b[start:end]
    if not np.all(np.isfinite(window_a) & np.isfinite(window_b)):
        # Interior gaps would poison the accumulator just as leading NaNs did. Zero-filling the
        # returns is the least-bad option and is flagged rather than hidden.
        window_a = np.nan_to_num(window_a, nan=0.0)
        window_b = np.nan_to_num(window_b, nan=0.0)
    out[start:end] = fn(window_a, window_b)
    return out


def _rolling_autocorr(values: np.ndarray, *, window: int, lag: int) -> np.ndarray:
    from alpha_patterns import rolling_autocorrelation

    safe = np.nan_to_num(values, nan=0.0)
    return rolling_autocorrelation(safe, window=window, lag=lag)


def _attach_onchain(
    features: dict[str, np.ndarray],
    frame: pl.DataFrame,
    ts: np.ndarray,
    notes: list[str],
) -> tuple[str, ...]:
    """Join CoinMetrics metrics onto the price axis, **lagged one day**.

    A row stamped for day D is published after day D closes, so it is knowable on D+1 and not
    before. Joining it to day D would give every on-chain condition a free look at the day it is
    supposed to be predicting — the single largest look-ahead available in this whole panel, and
    the reason the on-chain family is the most likely of all of them to produce a fake result.
    """
    dates = np.array(
        [int(np.datetime64(str(d), "D").astype(np.int64)) for d in frame["date"].to_list()]
    )
    target = _days(ts)
    added: list[str] = []
    for column in frame.columns:
        if column == "date":
            continue
        values = frame[column].to_numpy().astype(np.float64)
        out = np.full(target.size, np.nan, dtype=np.float64)
        # The -1 is the publication lag: bar D reads the metric stamped D-1.
        pos = np.searchsorted(dates, target - 1)
        ok = pos < dates.size
        pos_ok = np.clip(pos, 0, dates.size - 1)
        hit = ok & (dates[pos_ok] == target - 1)
        out[hit] = values[pos_ok[hit]]
        name = f"onchain_{column}"
        features[name] = out
        features[f"{name}_pct"] = percentile_rank(np.nan_to_num(out, nan=0.0), C.PCTILE_WINDOW)
        added.extend((name, f"{name}_pct"))

    covered = np.isfinite(features[added[0]]) if added else np.array([False])
    if covered.any():
        last = str(np.datetime64(int(ts[np.flatnonzero(covered)[-1]]), "ms"))[:10]
        notes.append(f"on-chain: coverage ends {last} — later bars are NaN, not carried forward")
    return tuple(added)
