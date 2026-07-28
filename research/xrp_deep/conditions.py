"""The condition battery: every "is the market in state X?" test, grouped into families.

Each condition is a boolean array plus a validity mask. The mask matters as much as the condition:
a warm-up NaN, a missing BTC bar or an on-chain gap must exclude a bar from the denominator rather
than counting as False. Counting undefined as False is the quiet way a study inflates its base rate
and shrinks every lift toward zero.

**Families are the unit of multiplicity control**, so membership is not cosmetic. MACD, RSI and the
stochastic all read the same momentum through different arithmetic; grouping them into one family
would understate how many independent bets are being placed, and spreading them across three
families overstates it. The compromise taken here — one family per *construction*, with the
correlation between families measured and reported rather than assumed away — is imperfect and is
the reason the empirical null calibration exists. BH within a family assumes the tests inside it are
independent-ish; they emphatically are not, so the surrogate run is what actually bounds the
false-discovery count.

Every threshold is from ``config``. No condition is allowed to pick its own cut, because a
condition that gets to choose the percentile at which it fires will always find one that works.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from research.xrp_deep import config as C
from research.xrp_deep.panel import Panel


@dataclass(frozen=True)
class Condition:
    """One named market state, its family, and where it is defined."""

    key: str
    family: str
    mask: np.ndarray  # bool
    valid: np.ndarray  # bool
    description: str

    @property
    def n_true(self) -> int:
        return int((self.mask & self.valid).sum())


def _cond(
    key: str, family: str, mask: np.ndarray, *, valid: np.ndarray, description: str
) -> Condition:
    return Condition(
        key, family, np.asarray(mask, dtype=bool), np.asarray(valid, bool), description
    )


def _finite(*arrays: np.ndarray) -> np.ndarray:
    out: np.ndarray = np.isfinite(arrays[0])
    for a in arrays[1:]:
        out = out & np.isfinite(a)
    return out


def build_conditions(panel: Panel) -> list[Condition]:  # noqa: PLR0915 — a flat, auditable list
    """Every condition in the battery, in family order.

    Deliberately one long function rather than twenty-four small ones. The whole point of this file
    is that a reader can see the *entire* hypothesis space at once and count it; splitting it up
    would make the multiplicity easier to lose track of, which is the failure mode being guarded
    against.
    """
    f = panel.features
    n = len(panel)
    always = np.ones(n, dtype=bool)
    out: list[Condition] = []
    add = out.append

    # --- 1. moving averages ---------------------------------------------------------------
    p200, p50 = f["price_over_sma200"], f["price_over_sma50"]
    cross = f["sma50_over_sma200"]
    add(
        _cond(
            "ma_price_above_200",
            "ma",
            p200 > 1.0,
            valid=_finite(p200),
            description="close above the 200-day SMA",
        )
    )
    add(
        _cond(
            "ma_price_below_200",
            "ma",
            p200 < 1.0,
            valid=_finite(p200),
            description="close below the 200-day SMA",
        )
    )
    add(
        _cond(
            "ma_price_above_50",
            "ma",
            p50 > 1.0,
            valid=_finite(p50),
            description="close above the 50-day SMA",
        )
    )
    add(
        _cond(
            "ma_golden_cross",
            "ma",
            cross > 1.0,
            valid=_finite(cross),
            description="50-day SMA above the 200-day (golden-cross regime)",
        )
    )
    add(
        _cond(
            "ma_death_cross",
            "ma",
            cross < 1.0,
            valid=_finite(cross),
            description="50-day SMA below the 200-day (death-cross regime)",
        )
    )
    slope = f["sma50_slope"]
    add(
        _cond(
            "ma_50_rising",
            "ma",
            slope > 0,
            valid=_finite(slope),
            description="50-day SMA sloping up",
        )
    )
    add(
        _cond(
            "ma_stack_bullish",
            "ma",
            (p50 > 1.0) & (cross > 1.0),
            valid=_finite(p50, cross),
            description="price above 50 and 50 above 200 — the full bullish stack",
        )
    )

    # --- 2. MACD ---------------------------------------------------------------------------
    hist, prev, line = f["macd_hist"], f["macd_hist_prev"], f["macd_line"]
    add(
        _cond(
            "macd_hist_positive",
            "macd",
            hist > 0,
            valid=_finite(hist),
            description="MACD histogram above zero",
        )
    )
    add(
        _cond(
            "macd_bull_cross",
            "macd",
            (hist > 0) & (prev <= 0),
            valid=_finite(hist, prev),
            description="MACD histogram crossed up through zero this bar",
        )
    )
    add(
        _cond(
            "macd_bear_cross",
            "macd",
            (hist < 0) & (prev >= 0),
            valid=_finite(hist, prev),
            description="MACD histogram crossed down through zero this bar",
        )
    )
    add(
        _cond(
            "macd_above_zero",
            "macd",
            line > 0,
            valid=_finite(line),
            description="MACD line above zero",
        )
    )
    add(
        _cond(
            "macd_rising",
            "macd",
            hist > prev,
            valid=_finite(hist, prev),
            description="MACD histogram rising",
        )
    )

    # --- 3. RSI -------------------------------------------------------------------------------
    r = f["rsi_14"]
    add(_cond("rsi_oversold", "rsi", r < 30, valid=_finite(r), description="RSI(14) below 30"))
    add(_cond("rsi_overbought", "rsi", r > 70, valid=_finite(r), description="RSI(14) above 70"))
    add(_cond("rsi_above_50", "rsi", r > 50, valid=_finite(r), description="RSI(14) above 50"))
    add(_cond("rsi_deep_oversold", "rsi", r < 20, valid=_finite(r), description="RSI(14) below 20"))

    # --- 4. stochastic / Williams %R -------------------------------------------------------------
    k, d = f["stoch_k"], f["stoch_d"]
    add(
        _cond("stoch_oversold", "stoch", k < 20, valid=_finite(k), description="stochastic %K < 20")
    )
    add(
        _cond(
            "stoch_overbought", "stoch", k > 80, valid=_finite(k), description="stochastic %K > 80"
        )
    )
    add(_cond("stoch_bull_cross", "stoch", k > d, valid=_finite(k, d), description="%K above %D"))
    wr = f["williams_r"]
    add(
        _cond(
            "williams_oversold",
            "stoch",
            wr < -80,
            valid=_finite(wr),
            description="Williams %R below -80",
        )
    )

    # --- 5. Bollinger ----
    bw = f["bandwidth_pct"]
    add(
        _cond(
            "boll_compressed",
            "bollinger",
            bw < C.LOW_PCTILE,
            valid=_finite(bw),
            description=f"Bollinger bandwidth in its bottom {C.LOW_PCTILE:.0%} of the past year",
        )
    )
    add(
        _cond(
            "boll_expanded",
            "bollinger",
            bw > C.HIGH_PCTILE,
            valid=_finite(bw),
            description=f"bandwidth in its top {1 - C.HIGH_PCTILE:.0%}",
        )
    )
    add(
        _cond(
            "boll_extreme_compressed",
            "bollinger",
            bw < 0.05,
            valid=_finite(bw),
            description="bandwidth in its bottom 5% — the tightest coil",
        )
    )

    # --- 6. Keltner squeeze ----
    sq = f["squeeze_on"]
    prev_sq = np.concatenate(([np.nan], sq[:-1]))
    add(
        _cond(
            "squeeze_on",
            "squeeze",
            sq > 0.5,
            valid=_finite(sq),
            description="Bollinger bands inside the Keltner channel",
        )
    )
    add(
        _cond(
            "squeeze_fired",
            "squeeze",
            (sq < 0.5) & (prev_sq > 0.5),
            valid=_finite(sq, prev_sq),
            description="squeeze released this bar — the classic trigger",
        )
    )

    # --- 7. Donchian ----
    dp, du, dl = f["donchian_position"], f["donchian_upper"], f["donchian_lower"]
    close = panel.bars.close
    add(
        _cond(
            "donch_breakout_up",
            "donchian",
            close > du,
            valid=_finite(du),
            description="close above the prior 20-day high",
        )
    )
    add(
        _cond(
            "donch_breakout_down",
            "donchian",
            close < dl,
            valid=_finite(dl),
            description="close below the prior 20-day low",
        )
    )
    add(
        _cond(
            "donch_upper_half",
            "donchian",
            dp > 0.5,
            valid=_finite(dp),
            description="close in the upper half of the 20-day channel",
        )
    )

    # --- 8. ADX ----
    adx, pdi, mdi = f["adx"], f["plus_di"], f["minus_di"]
    add(_cond("adx_trending", "adx", adx > 25, valid=_finite(adx), description="ADX above 25"))
    add(_cond("adx_quiet", "adx", adx < 20, valid=_finite(adx), description="ADX below 20"))
    add(
        _cond("adx_bull_di", "adx", pdi > mdi, valid=_finite(pdi, mdi), description="+DI above -DI")
    )
    add(
        _cond(
            "adx_strong_bull",
            "adx",
            (adx > 25) & (pdi > mdi),
            valid=_finite(adx, pdi, mdi),
            description="ADX above 25 with +DI leading",
        )
    )

    # --- 9. OBV ----
    obv_slope = f["obv_slope"]
    add(
        _cond(
            "obv_rising",
            "obv",
            obv_slope > 0,
            valid=_finite(obv_slope),
            description="20-day OBV average rising",
        )
    )
    ret20 = np.concatenate((np.full(20, np.nan), close[20:] / close[:-20] - 1.0))
    add(
        _cond(
            "obv_bull_divergence",
            "obv",
            (obv_slope > 0) & (ret20 < 0),
            valid=_finite(obv_slope, ret20),
            description="OBV rising while price fell over 20 days",
        )
    )
    add(
        _cond(
            "obv_bear_divergence",
            "obv",
            (obv_slope < 0) & (ret20 > 0),
            valid=_finite(obv_slope, ret20),
            description="OBV falling while price rose over 20 days",
        )
    )

    # --- 10. money flow ----
    cmf, mfi = f["cmf"], f["mfi"]
    add(
        _cond(
            "cmf_positive",
            "flow",
            cmf > 0,
            valid=_finite(cmf),
            description="Chaikin money flow above zero",
        )
    )
    add(
        _cond(
            "cmf_strong",
            "flow",
            cmf > 0.1,
            valid=_finite(cmf),
            description="Chaikin money flow above 0.10",
        )
    )
    add(
        _cond(
            "mfi_oversold",
            "flow",
            mfi < 20,
            valid=_finite(mfi),
            description="money-flow index below 20",
        )
    )
    add(
        _cond(
            "mfi_overbought",
            "flow",
            mfi > 80,
            valid=_finite(mfi),
            description="money-flow index above 80",
        )
    )

    # --- 11. volume ----
    vr = f["volume_ratio"]
    add(
        _cond(
            "volume_dryup",
            "volume",
            vr < 0.7,
            valid=_finite(vr),
            description="volume below 70% of its 20-day average",
        )
    )
    add(
        _cond(
            "volume_spike",
            "volume",
            vr > 2.0,
            valid=_finite(vr),
            description="volume above twice its 20-day average",
        )
    )
    add(
        _cond(
            "volume_normal",
            "volume",
            (vr >= 0.7) & (vr <= 2.0),
            valid=_finite(vr),
            description="volume within the ordinary band",
        )
    )

    # --- 12. volatility regime ----
    vp = f["vol_pct"]
    add(
        _cond(
            "vol_low",
            "volatility",
            vp < C.LOW_PCTILE,
            valid=_finite(vp),
            description=f"realized vol in its bottom {C.LOW_PCTILE:.0%} of the past year",
        )
    )
    add(
        _cond(
            "vol_high",
            "volatility",
            vp > C.HIGH_PCTILE,
            valid=_finite(vp),
            description=f"realized vol in its top {1 - C.HIGH_PCTILE:.0%}",
        )
    )
    atr_p = f["atr_pct_price"]
    add(
        _cond(
            "atr_tight",
            "volatility",
            atr_p < np.nanpercentile(atr_p, 20),
            valid=_finite(atr_p),
            description="ATR small relative to price",
        )
    )

    # --- 13. Ichimoku ----
    above, chikou = f["ichi_above_cloud"], f["ichi_chikou_above"]
    tk, kj = f["ichi_tenkan"], f["ichi_kijun"]
    add(
        _cond(
            "ichi_above_cloud",
            "ichimoku",
            above > 0.5,
            valid=_finite(above),
            description="close above both cloud edges",
        )
    )
    add(
        _cond(
            "ichi_below_cloud",
            "ichimoku",
            above < 0.5,
            valid=_finite(above),
            description="close not above the cloud",
        )
    )
    add(
        _cond(
            "ichi_tk_cross",
            "ichimoku",
            tk > kj,
            valid=_finite(tk, kj),
            description="tenkan above kijun",
        )
    )
    add(
        _cond(
            "ichi_chikou_clear",
            "ichimoku",
            chikou > 0.5,
            valid=_finite(chikou),
            description="close above its own value 26 bars ago",
        )
    )

    # --- 14. Fibonacci ----
    fd = f["fib_distance"]
    add(
        _cond(
            "fib_at_level",
            "fib",
            fd < C.LEVEL_TOLERANCE,
            valid=_finite(fd),
            description=f"within {C.LEVEL_TOLERANCE:.0%} of a swing span of a retracement level",
        )
    )
    add(
        _cond(
            "fib_far_from_level",
            "fib",
            fd > 0.2,
            valid=_finite(fd),
            description="far from any retracement level",
        )
    )

    # --- 15. round numbers ----
    rd, rdc = f["round_distance"], f["round_distance_coarse"]
    add(
        _cond(
            "round_near",
            "round",
            rd < 0.1,
            valid=_finite(rd),
            description="within 10% of a step of a two-significant-figure round number",
        )
    )
    add(
        _cond(
            "round_near_coarse",
            "round",
            rdc < 0.05,
            valid=_finite(rdc),
            description="within 5% of a step of a big round number",
        )
    )
    add(
        _cond(
            "round_far",
            "round",
            rd > 0.4,
            valid=_finite(rd),
            description="as far from a round number as the grid allows",
        )
    )

    # --- 16. BTC ----
    if "btc_mom_20" in f:
        bm, bc = f["btc_mom_20"], f["corr_btc_90"]
        add(
            _cond(
                "btc_up_20d",
                "btc",
                bm > 0,
                valid=_finite(bm),
                description="BTC higher than 20 days ago",
            )
        )
        add(
            _cond(
                "btc_strong_20d",
                "btc",
                bm > 0.10,
                valid=_finite(bm),
                description="BTC up more than 10% over 20 days",
            )
        )
        add(
            _cond(
                "btc_weak_20d",
                "btc",
                bm < -0.10,
                valid=_finite(bm),
                description="BTC down more than 10% over 20 days",
            )
        )
        add(
            _cond(
                "corr_btc_high",
                "btc",
                bc > 0.8,
                valid=_finite(bc),
                description="90-day XRP/BTC return correlation above 0.8",
            )
        )
        add(
            _cond(
                "corr_btc_low",
                "btc",
                bc < 0.5,
                valid=_finite(bc),
                description="90-day correlation below 0.5 — XRP trading on its own",
            )
        )

    # --- 17. XRP/BTC ratio ----
    if "ratio_over_ma" in f:
        rom = f["ratio_over_ma"]
        add(
            _cond(
                "ratio_above_ma",
                "ratio",
                rom > 1.0,
                valid=_finite(rom),
                description="XRP/BTC ratio above its own 50-day average",
            )
        )
        add(
            _cond(
                "ratio_strong",
                "ratio",
                rom > 1.05,
                valid=_finite(rom),
                description="XRP/BTC ratio 5% above its average — alt strength",
            )
        )
        add(
            _cond(
                "ratio_weak",
                "ratio",
                rom < 0.95,
                valid=_finite(rom),
                description="XRP/BTC ratio 5% below its average",
            )
        )

    # --- 18. seasonality ----
    month, weekday, dom = f["month"], f["weekday"], f["day_of_month"]
    add(_cond("month_q4", "season", month >= 10, valid=always, description="October to December"))
    add(_cond("month_q1", "season", month <= 3, valid=always, description="January to March"))
    add(
        _cond(
            "month_summer",
            "season",
            (month >= 6) & (month <= 8),
            valid=always,
            description="June to August",
        )
    )
    add(_cond("weekday_monday", "season", weekday == 0, valid=always, description="Monday"))
    add(
        _cond(
            "weekday_weekend",
            "season",
            weekday >= 5,
            valid=always,
            description="Saturday or Sunday",
        )
    )
    add(
        _cond(
            "turn_of_month",
            "season",
            (dom >= 28) | (dom <= 3),
            valid=always,
            description="the turn-of-month window",
        )
    )

    # --- 19. memory / cycles ----
    vr5, hurst, ac1 = f["variance_ratio_5"], f["hurst_returns"], f["autocorr_1"]
    add(
        _cond(
            "vr_trending",
            "memory",
            vr5 > 1.0,
            valid=_finite(vr5),
            description="variance ratio above 1 — returns trending over 5 days",
        )
    )
    add(
        _cond(
            "vr_mean_reverting",
            "memory",
            vr5 < 1.0,
            valid=_finite(vr5),
            description="variance ratio below 1 — returns mean-reverting",
        )
    )
    add(
        _cond(
            "hurst_persistent",
            "memory",
            hurst > 0.55,
            valid=_finite(hurst),
            description="rolling Hurst above 0.55",
        )
    )
    add(
        _cond(
            "autocorr_positive",
            "memory",
            ac1 > 0,
            valid=_finite(ac1),
            description="positive lag-1 return autocorrelation over the past year",
        )
    )

    # --- 20. drawdown / range position ----
    dd, rp = f["drawdown_from_ath"], f["range_position_365"]
    add(
        _cond(
            "deep_drawdown",
            "drawdown",
            dd < -0.60,
            valid=_finite(dd),
            description="more than 60% below the all-time high",
        )
    )
    add(
        _cond(
            "extreme_drawdown",
            "drawdown",
            dd < -0.80,
            valid=_finite(dd),
            description="more than 80% below the all-time high",
        )
    )
    add(
        _cond(
            "near_ath",
            "drawdown",
            dd > -0.20,
            valid=_finite(dd),
            description="within 20% of the all-time high",
        )
    )
    add(
        _cond(
            "range_bottom",
            "drawdown",
            rp < 0.10,
            valid=_finite(rp),
            description="in the bottom decile of the past year's range",
        )
    )
    add(
        _cond(
            "range_top",
            "drawdown",
            rp > 0.90,
            valid=_finite(rp),
            description="in the top decile of the past year's range",
        )
    )

    # --- 21. on-chain ----
    mvrv = f.get("onchain_CapMVRVCur_pct")
    if mvrv is not None:
        add(
            _cond(
                "mvrv_low",
                "onchain",
                mvrv < C.LOW_PCTILE,
                valid=_finite(mvrv),
                description="MVRV in its bottom quintile — historically cheap",
            )
        )
        add(
            _cond(
                "mvrv_high",
                "onchain",
                mvrv > C.HIGH_PCTILE,
                valid=_finite(mvrv),
                description="MVRV in its top quintile — historically expensive",
            )
        )
    addr = f.get("onchain_AdrActCnt_pct")
    if addr is not None:
        add(
            _cond(
                "addresses_high",
                "onchain",
                addr > C.HIGH_PCTILE,
                valid=_finite(addr),
                description="active addresses in their top quintile",
            )
        )
        add(
            _cond(
                "addresses_low",
                "onchain",
                addr < C.LOW_PCTILE,
                valid=_finite(addr),
                description="active addresses in their bottom quintile",
            )
        )
    txc = f.get("onchain_TxCnt_pct")
    if txc is not None:
        add(
            _cond(
                "tx_high",
                "onchain",
                txc > C.HIGH_PCTILE,
                valid=_finite(txc),
                description="transaction count in its top quintile",
            )
        )

    # --- 22. bar structure ----
    ib, nr7, cir = f["inside_bar"], f["nr7"], f["close_in_range"]
    add(
        _cond(
            "inside_bar",
            "bar",
            ib > 0.5,
            valid=_finite(ib),
            description="an inside bar — range contained by the prior bar",
        )
    )
    add(
        _cond(
            "nr7",
            "bar",
            nr7 > 0.5,
            valid=_finite(nr7),
            description="narrowest range of the past seven bars",
        )
    )
    add(
        _cond(
            "close_strong",
            "bar",
            cir > 0.8,
            valid=_finite(cir),
            description="closed in the top fifth of its own range",
        )
    )
    add(
        _cond(
            "close_weak",
            "bar",
            cir < 0.2,
            valid=_finite(cir),
            description="closed in the bottom fifth of its own range",
        )
    )

    # --- 23. chart patterns ------------------------------------------------------------------
    # Every pattern condition is stamped at ``confirmed_index``, never at the bar the shape sits
    # on. A wedge apex is obvious in hindsight and invisible in real time, and marking the apex bar
    # itself would hand the condition the very future it is supposed to be predicting.
    for key, indices, desc in _pattern_events(panel):
        flag = np.zeros(n, dtype=bool)
        for i in indices:
            if 0 <= i < n:
                flag[i : min(i + 5, n)] = True  # the five bars a trader could act on
        add(_cond(key, "pattern", flag, valid=always, description=desc))

    # --- 24. perp-spot basis ----
    basis, basis_pct, share = _flow_series(panel)
    if basis is not None and basis_pct is not None and share is not None:
        # NOT a raw sign test. The measured median basis is -4bp with 16bp of dispersion, which is
        # a constant offset between the two 5-minute mirrors — almost certainly close-stamping,
        # not backwardation. "Basis is negative" would therefore be true on 70% of bars and would
        # be reporting a data artefact as a market state. Comparing against the asset's own
        # trailing median cancels any constant offset and asks the question actually intended:
        # is leverage cheaper than it usually is?
        trailing_median = _trailing_median(basis, C.PCTILE_WINDOW)
        add(
            _cond(
                "basis_below_trailing",
                "basis",
                basis < trailing_median,
                valid=_finite(basis, trailing_median),
                description="perp-spot basis below its own trailing-year median — leverage cheap",
            )
        )
        add(
            _cond(
                "basis_rich",
                "basis",
                basis_pct > C.HIGH_PCTILE,
                valid=_finite(basis_pct),
                description="perp-spot basis in its top quintile of the past year — crowded long",
            )
        )
        add(
            _cond(
                "basis_cheap",
                "basis",
                basis_pct < C.LOW_PCTILE,
                valid=_finite(basis_pct),
                description="basis in its bottom quintile — leverage has been flushed out",
            )
        )
        add(
            _cond(
                "perp_share_high",
                "basis",
                share > 0.8,
                valid=_finite(share),
                description="perps are over 80% of notional — the move is leverage, not spot",
            )
        )
        add(
            _cond(
                "perp_share_low",
                "basis",
                share < 0.6,
                valid=_finite(share),
                description="spot is carrying an unusual share of volume",
            )
        )

    return out


def _pattern_events(panel: Panel) -> list[tuple[str, list[int], str]]:
    """Confirmation bars for each detected chart pattern, or nothing when detection fails.

    Detection is comparatively expensive and entirely optional to the rest of the battery, so a
    detector that raises on this series degrades the pattern family to empty rather than taking
    the whole study down with it.
    """
    from alpha_patterns import detect_head_shoulders, detect_triple_taps, detect_wedges

    bars = panel.bars
    events: list[tuple[str, list[int], str]] = []
    try:
        wedges = detect_wedges(bars)
    except Exception:  # noqa: BLE001 — an optional family, reported empty rather than fatal
        wedges = []
    if wedges:
        events.append(
            (
                "wedge_confirmed",
                [w.confirmed_index for w in wedges],
                "a converging-trendline wedge was confirmed",
            )
        )
        events.append(
            (
                "wedge_apex_passed",
                [w.confirmed_index for w in wedges if w.apex_passed_unbroken],
                "a wedge whose apex passed without a break — where the live setup sits",
            )
        )
        events.append(
            (
                "wedge_falling",
                [w.confirmed_index for w in wedges if w.kind == "falling"],
                "a falling wedge was confirmed",
            )
        )
    try:
        taps = detect_triple_taps(bars)
    except Exception:  # noqa: BLE001
        taps = []
    if taps:
        events.append(
            (
                "triple_tap_confirmed",
                [t.confirmed_index for t in taps],
                "a third tap of the same level was confirmed",
            )
        )
    try:
        hs = detect_head_shoulders(bars)
    except Exception:  # noqa: BLE001
        hs = []
    if hs:
        events.append(
            (
                "inverse_hs_confirmed",
                [e.confirmed_index for e in hs if e.direction == "bullish"],
                "an inverse head-and-shoulders was confirmed",
            )
        )
        events.append(
            (
                "hs_confirmed",
                [e.confirmed_index for e in hs if e.direction == "bearish"],
                "a head-and-shoulders top was confirmed",
            )
        )
    return events


def _trailing_median(values: np.ndarray, window: int) -> np.ndarray:
    """Causal trailing median, NaN until the window is full.

    A median rather than a mean because the basis has fat tails on both sides and a single
    liquidation cascade would drag a mean around for a year.
    """
    out = np.full(values.size, np.nan, dtype=np.float64)
    for i in range(values.size):
        if i + 1 < window:
            continue
        chunk = values[i - window + 1 : i + 1]
        finite = chunk[np.isfinite(chunk)]
        if finite.size:
            out[i] = float(np.median(finite))
    return out


def _flow_series(
    panel: Panel,
) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
    """Raw perp-spot basis, its trailing percentile rank, and perp share of notional.

    The basis is a **sound funding proxy** — funding exists precisely to close this spread — and
    the perp share is a direct measure of how much of a move is leveraged rather than spot. Both
    only exist from 2020-09, so they are NaN across the Bitstamp era rather than back-filled.

    ``basis`` and ``basis_pct`` are returned separately because they answer different questions and
    are trivially confusable: the first is a signed fraction ("is the perp above or below spot?"),
    the second a rank in [0, 1] ("is that spread unusual?"). Reading the rank as a fraction makes
    "basis below zero" impossible by construction and "basis above 20bp" true on every single bar —
    which is exactly the pair of degenerate counts that exposed the mix-up here.
    """
    try:
        from research.xrp_pumps.flow import load_flow

        flow = load_flow("XRP")
    except Exception:  # noqa: BLE001 — absence of the 5m mirrors is a fact, not a failure
        return None, None, None

    n = len(panel)
    target = np.round(panel.bars.ts / 86_400_000.0).astype(np.int64)
    src = np.round(np.asarray(flow.ts, dtype=np.float64) / 86_400_000.0).astype(np.int64)
    order = np.argsort(src)
    src_sorted = src[order]
    pos = np.searchsorted(src_sorted, target)
    ok = pos < src_sorted.size
    pos_ok = np.clip(pos, 0, max(src_sorted.size - 1, 0))
    hit = ok & (src_sorted[pos_ok] == target)

    def _scatter(values: np.ndarray) -> np.ndarray:
        out = np.full(n, np.nan)
        out[hit] = np.asarray(values)[order][pos_ok[hit]]
        return out

    return _scatter(flow.basis), _scatter(flow.basis_pct), _scatter(flow.perp_share)


def screen(conditions: list[Condition]) -> tuple[list[Condition], list[str]]:
    """Drop conditions too rare or too universal to carry information, and say which.

    Three ways a condition is useless before any outcome is looked at:

    * it fires on fewer than :data:`config.MIN_CONDITION_BARS` bars, so its interval spans most of
      the unit line whatever the answer;
    * it fires on *every* valid bar, so it has no complement to compare against;
    * it never fires at all.

    All three are dropped here rather than at report time, because a degenerate row that reaches
    the statistics still consumes a slot in the multiplicity budget and still occasionally comes
    back "significant" on three observations. Both bugs this screen caught on the first run —
    a percentile rank read as a raw basis, and a wedge condition that could never fire — presented
    exactly as such rows.
    """
    kept: list[Condition] = []
    dropped: list[str] = []
    for c in conditions:
        n_valid = int(c.valid.sum())
        n_true = c.n_true
        if n_true == 0:
            dropped.append(f"{c.key}: never fires ({n_valid} valid bars)")
        elif n_true < C.MIN_CONDITION_BARS:
            dropped.append(f"{c.key}: fires on only {n_true} bars (floor {C.MIN_CONDITION_BARS})")
        elif n_true == n_valid:
            dropped.append(f"{c.key}: fires on all {n_valid} valid bars — no complement to compare")
        elif n_valid - n_true < C.MIN_CONDITION_BARS:
            dropped.append(
                f"{c.key}: complement has only {n_valid - n_true} bars "
                f"(floor {C.MIN_CONDITION_BARS})"
            )
        else:
            kept.append(c)
    return kept, dropped


def by_family(conditions: list[Condition]) -> dict[str, list[Condition]]:
    grouped: dict[str, list[Condition]] = {}
    for c in conditions:
        grouped.setdefault(c.family, []).append(c)
    return grouped
