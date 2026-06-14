# 06 — Strategy Encoding, Position Sizing & ML Methodology

**Project ALPHA — personal, $0-budget, Python-first quantitative research platform.**
Author: research agent · Date: 2026-06-14

> **Scope & stance.** This document does two things at once and keeps them strictly separate:
> 1. It **encodes** the two discretionary templates from the source blueprint into precise, deterministic, look-ahead-safe state machines so they can be tested *fairly* and *reproducibly*.
> 2. It states, with citations, the **prior probability that these specific templates carry durable edge is low** (Smart-Money-Concepts / support-resistance patterns occur at the same frequency on randomized price as on real price). Encoding precisely and believing-in-advance are different acts. We encode so we can *falsify*, not so we can *confirm*.
>
> Everything below obeys the project constraints: free/open-source Python only, validation-first, look-ahead-safe.

---

## Table of contents

- [Part A — Strategy state-machine specifications](#part-a--strategy-state-machine-specifications)
  - [A.0 Shared primitive definitions](#a0-shared-primitive-definitions-make-these-canonical)
  - [A.1 Volatility-Filtered 8AM Opening Range Breakout (ORB)](#a1-volatility-filtered-8am-opening-range-breakout-orb)
  - [A.2 Rejection Block Retracement](#a2-rejection-block-retracement)
  - [A.3 Look-ahead bias: the master checklist](#a3-look-ahead-bias-the-master-checklist)
- [Part B — Position sizing & risk math](#part-b--position-sizing--risk-math)
- [Part C — ML for trading on free tools (honest edition)](#part-c--ml-for-trading-on-free-tools-honest-edition)
- [Part D — The intellectual-honesty section: a rigorous edge-discovery process](#part-d--the-intellectual-honesty-section-a-rigorous-edge-discovery-process)
- [Appendix — Free Python tool stack](#appendix--free-python-tool-stack)
- [Sources](#sources)

---

## Part A — Strategy state-machine specifications

### A.0 Shared primitive definitions (make these canonical)

Discretionary traders argue endlessly because their primitives are fuzzy. A testable system needs *one* definition per term, applied mechanically. These are the definitions Project ALPHA will use. Where the ICT/SMC community itself is consistent, we adopt their convention; where it is ambiguous, we pick the **most conservative, look-ahead-safe** choice and flag it.

**Bar / candle indexing.** A bar `i` has `open[i], high[i], low[i], close[i]` and a close timestamp `t_close[i]`. **A bar is only "known" after `t_close[i]`.** Any rule that references `high[i]`, `low[i]`, or `close[i]` may only fire on bars whose timestamp is `>= t_close[i]`. This single rule prevents most intrabar look-ahead.

**Swing pivot (fractal).** A *swing high* at bar `i` with half-width `k` (default `k=2`) requires `high[i] > high[i-j]` and `high[i] > high[i+j]` for all `j in 1..k`. A *swing low* is the mirror. This is the standard 3-candle fractal at `k=1`; we default to `k=2` (5-candle) for less noise. **Look-ahead note:** a swing high at bar `i` *cannot be confirmed until bar `i+k` has closed*. The pivot must therefore be timestamped at `t_close[i+k]`, **not** `t_close[i]`. Backtests that mark the pivot at `i` and act on it at `i+1` are using future information — a classic and very common bug. (Swing-point definition per ICT/SMC convention. [tradingstrategyguides.com](https://tradingstrategyguides.com/day-3-smc-ict-market-structure-explained-bos-choch-swing-points-2026/), [innercircletraders.net](https://innercircletraders.net/what-is-an-ict-market-structure/))

**Break of Structure (BOS).** A bullish BOS occurs when a candle **closes** (full body) above the most recent confirmed swing high; bearish BOS when a candle closes below the most recent confirmed swing low. **Critical rule, repeatedly emphasized in the ICT literature: a wick through the level is NOT a BOS — it is a liquidity sweep. Confirmation requires a body close beyond the level.** ([tradingstrategyguides.com](https://tradingstrategyguides.com/day-3-smc-ict-market-structure-explained-bos-choch-swing-points-2026/): "a wick alone does not confirm a structure break. Price must close — full candle body — beyond the previous swing point. A wick through a level is treated as a liquidity sweep, not a structural shift.") BOS = trend *continuation*; CHoCH (Change of Character) = breaking the most recent *counter-trend* swing = potential reversal. ([xs.com](https://www.xs.com/en/blog/break-of-structure/), [luxalgo.com](https://www.luxalgo.com/blog/market-structure-shifts-mss-in-ict-trading/))

**Rejection block.** A rejection block is the **wick range** of a candle that (a) **swept liquidity** — its wick extended beyond a prior swing high/low or a cluster of equal highs/lows — and (b) **closed its body back inside** the prior range, proving the extension was a sweep rather than a genuine breakout. The block zone = `[body_close, wick_extreme]` (the wick that remains after the body close). Contrast with an *order block*, which is the **body range** of the candle preceding a displacement move. The rejection block is narrower and sits closer to the swept extreme, giving a tighter stop. ([ictnotebook.com](https://ictnotebook.com/articles/rejection-block/), [howtotrade.com](https://howtotrade.com/blog/ict-rejection-block/), [smartmoneyict.com](https://smartmoneyict.com/ict-rejection-block/))

**Zone / boundary terminology for ORB.** The 08:00 range defines `OR_high`, `OR_low`, `mid = (OR_high + OR_low) / 2`. The "opposite zone boundary" relative to a *long* bias is `OR_low` (and vice versa).

**Timezone discipline.** "08:00" and "18:00" are meaningless without a timezone. Fix one exchange timezone (e.g., `America/New_York` for index futures, or the instrument's native session) in config, convert all timestamps once at load, and never mix. DST transitions must be handled by a tz-aware library (`pandas` + `zoneinfo`/`pytz`), not by hard-coded offsets.

---

### A.1 Volatility-Filtered 8AM Opening Range Breakout (ORB)

**One-line intent.** Build a range from the first post-08:00 1-minute bar, wait for a directional Break-of-Structure, demand a retrace that *taps the midpoint*, enter on the close of the confirming BOS, and kill the setup for the day if price first slices through the opposite side of the range.

#### Data required
- 1-minute OHLCV for the instrument, tz-aware.
- A **volatility filter** input (the "Volatility-Filtered" qualifier). The blueprint does not pin this down; we make it explicit and testable: compute a session-level or rolling ATR/realized-vol regime metric *using only bars that closed before 08:00* and gate the day on/off. Two defensible variants to test (pick ONE per experiment, never both post-hoc):
  - **V1 (range-relative):** require the 08:00 bar's range `OR_high − OR_low >= c · ATR_d` where `ATR_d` is yesterday's daily ATR (known at open). Trades only days with a "live" open.
  - **V2 (regime gate):** require a rolling 20-day realized volatility to sit within `[vol_low, vol_high]` so we skip dead and chaotic regimes.
  - The volatility filter is itself a **parameter** — count it in your multiple-testing budget (Part D).

#### State machine

States: `IDLE → RANGE_SET → AWAIT_BOS → AWAIT_MID_TAP → IN_TRADE → DONE_FOR_DAY`. Reset to `IDLE` at **18:00**.

| State | Entry condition | Action / transition | Look-ahead guard |
|---|---|---|---|
| `IDLE` | Clock reaches 08:00; first 1-min bar after 08:00 has **closed** | Record `OR_high=high`, `OR_low=low`, `mid`; apply vol filter. If filter passes → `RANGE_SET`, else → `DONE_FOR_DAY` | Use the bar's values only after its close timestamp |
| `RANGE_SET` | — | Begin tracking swings *after* the range bar | — |
| `AWAIT_BOS` | A 1-min candle **closes** beyond a confirmed post-range swing high (→ long bias) or swing low (→ short bias) | Set `bias`; record `bos_close_price`; → `AWAIT_MID_TAP`. **Invalidation check first:** if, before any BOS, price trades fully through the *opposite* boundary (`low < OR_low` for an incipient long-side structure, or symmetric), permanently → `DONE_FOR_DAY` | BOS = **body close**, not wick. Swing must be confirmed (`k` bars elapsed) |
| `AWAIT_MID_TAP` | After the BOS, price **retraces and taps `mid`** in the bias direction — a **wick touch counts** (`low[i] <= mid <= high[i]`) | → `AWAIT_BOS_CONFIRM` (look for the *first confirmed 1-min BOS* in the bias direction to trigger entry) | Tap detected only on closed bars; do not peek intrabar unless you have true tick data and model it explicitly |
| `AWAIT_BOS_CONFIRM` | The **first** 1-min candle that **closes** as a BOS in the bias direction after the midpoint tap | **Enter market on the close** of that candle; record entry, stop, target; → `IN_TRADE`. Max **one** trade/day | Entry price = that bar's close (fillable at next-bar open in a conservative fill model — see note) |
| `IN_TRADE` | Stop or target hit | Close position; → `DONE_FOR_DAY` | Resolve stop-before-target ambiguity conservatively (assume worst-case ordering within the bar) |
| `DONE_FOR_DAY` | — | No further action until 18:00 reset → `IDLE` | — |

**Permanent invalidation (the blueprint's hard rule).** "Invalidate permanently for the day if price runs fully through the opposite zone boundary before a midpoint tap." Encode as: while in `AWAIT_BOS`/`AWAIT_MID_TAP`, if the **bias-opposite** boundary is breached by a body close (or by trade-through, your choice — pick one and keep it) before the midpoint is tapped, jump to `DONE_FOR_DAY`. "Fully through" should be defined precisely: we recommend **body close beyond the opposite boundary** (consistent with the BOS body-close convention) to avoid being knocked out by a single wick.

**Stops / targets.** The blueprint specifies entry/invalidation but not exit geometry for ORB. To make it testable, fix a rule up front (and treat its parameters as part of the search budget): e.g., **stop** = beyond the structural low/high that produced the BOS (or `mid` ± buffer); **target** = `R`-multiple (test `R ∈ {1, 1.5, 2}`) or the opposite OR boundary. Document the chosen rule; do not optimize it after seeing results.

#### Where look-ahead bias sneaks into ORB
1. **Pivot confirmation lag.** Marking a swing at bar `i` and reacting at `i+1` leaks `k` bars of future. Always timestamp pivots at `i+k`.
2. **Wick vs. close on BOS.** Using wick penetration as "BOS" both over-signals and front-runs the true (close-based) confirmation.
3. **Intrabar midpoint tap with bar data.** With 1-min OHLC you know the bar tapped `mid` only after close; if you trigger entry *within the same bar* as the tap you are assuming intrabar sequencing you cannot observe. Either wait for the next bar or use real tick data.
4. **Same-bar entry fill.** "Enter on the close" is fine to *signal* on the closing bar, but a realistic fill is **next-bar open** (or close with slippage). Filling at the exact close of the signal bar is mild look-ahead.
5. **Stop-vs-target same-bar resolution.** If a bar's range spans both stop and target, assuming the favorable one fills first is optimistic look-ahead. Assume the stop fills first (worst case) unless you have tick data.
6. **Volatility filter computed with same-day data.** The gate must use only pre-08:00 information (prior daily ATR, prior session realized vol). Using the full day's vol to decide whether to trade that day is leakage.
7. **18:00 reset & overnight bars.** Ensure the day boundary, session gaps, and holidays don't let state or ranges bleed across days.

---

### A.2 Rejection Block Retracement

**One-line intent.** Use **daily** rejection blocks to set a macro bias, drop to **5-minute** to find the reactionary leg off the rejection zone, anchor a Fibonacci retracement to that leg, place a **limit** order in the discount half (below ~0.5), stop just past the far edge of the 5-min trigger candle, target the nearest viable 5-min swing pivot.

#### Data required
- **Daily** OHLCV (macro bias / rejection-block scan).
- **5-minute** OHLCV (execution).
- Prior-range reference for the daily sweep test (the swing high/low or equal-highs/lows that got swept).

#### State machine

States: `SCAN_DAILY → BIAS_SET → TRACK_REACTION_5M → FIB_ANCHORED → ORDER_WORKING → IN_TRADE → FLAT`.

| State | Entry condition | Action / transition | Look-ahead guard |
|---|---|---|---|
| `SCAN_DAILY` | A **completed daily candle** qualifies as a rejection block: long wick sweeps a prior swing extreme / equal highs-lows, **and body closes back inside** the prior range | Set macro `bias` (bullish if a *low* was swept and price closed back up; bearish if a *high* was swept and closed back down). Record the daily rejection zone `[body_close, wick_extreme]`; → `BIAS_SET` | Daily candle must be **fully closed**. A rejection block is only valid *after* the daily close — using it intraday on the same day is look-ahead |
| `BIAS_SET` | Next session opens | Switch to 5-min; → `TRACK_REACTION_5M` | — |
| `TRACK_REACTION_5M` | On 5-min, price reacts off the daily rejection zone, producing a directional **reactionary leg** (a move away from the zone with a defined swing start and swing end) | Identify the leg's **swing low and swing high** (confirmed 5-min pivots); → `FIB_ANCHORED` | Leg endpoints are confirmed pivots (need `k` bars after the extreme). Don't anchor to an extreme that isn't yet confirmed |
| `FIB_ANCHORED` | — | Anchor Fibonacci to the leg (`0.0` at the leg origin, `1.0` at the leg extreme, oriented so that the **discount half is the retracement zone** in the bias direction). Compute the `0.5` level and the entry band **below ~0.5** (discount). Identify the **5-min trigger candle** (the candle whose far edge defines the stop). → `ORDER_WORKING` | Fib levels derived only from confirmed leg endpoints. "Discount" = below midpoint for a long (you buy cheap); "premium" = above midpoint for a short |
| `ORDER_WORKING` | Place **limit** entry in the discount half (e.g., between `0.5` and `0.705`/`0.79` — choose & fix). **Stop** just past the **far edge of the 5-min trigger candle** (beyond its low for a long, its high for a short, + buffer). **Target** = nearest viable 5-min **swing pivot** in the trade direction | If price reaches the limit → fill → `IN_TRADE`. Cancel if structure invalidates (e.g., daily bias negated, or leg origin violated) before fill | Limit fill realism: assume filled only if a bar's range actually **trades through** the limit price. Don't assume mid-bar fills you can't see |
| `IN_TRADE` | Stop or target hit | Close; → `FLAT` | Same-bar stop/target ambiguity → assume worst case |
| `FLAT` | — | Await next daily rejection block | — |

**Precise sub-definitions for A.2:**
- **"Viable" 5-min swing pivot (target):** the nearest confirmed swing high (for a long) above entry that (a) is a true `k`-fractal and (b) leaves a reward:risk ≥ a preset floor (e.g., ≥ 1.0R, ideally ≥ 1.5R). If none qualifies, **no trade** — do not invent a target.
- **"Reactionary leg":** the first impulsive 5-min move originating at/inside the daily rejection zone, measured from the local pivot inside the zone to the first confirmed counter-pivot. Define a minimum leg size (e.g., ≥ 1× 5-min ATR) so noise legs are excluded.
- **"Far edge of the trigger candle":** the extreme (low for long / high for short) of the specific 5-min candle designated as the entry trigger; the stop sits a small ATR-fraction beyond it.

#### Where look-ahead bias sneaks into Rejection Block Retracement
1. **Same-day daily rejection block.** The single biggest trap. A daily candle is only a rejection block *after the daily close*. Acting on "today's developing daily candle" intraday means you used the close before it happened. Bias may only be applied to **subsequent** sessions.
2. **Unconfirmed 5-min leg extremes.** Anchoring the Fib to a swing that isn't yet a confirmed pivot front-runs `k` bars.
3. **Fib drawn with hindsight.** If you wait to see where price reversed and *then* anchor the leg so the entry lands perfectly, you've curve-fit the anchor. The leg must be defined by a deterministic rule evaluated in real time.
4. **Limit-fill optimism.** Assuming a limit fills when price merely *approaches* it, or filling at a better-than-limit price, is look-ahead. Require an actual trade-through.
5. **Target chosen after the fact.** The "nearest viable swing pivot" must be the nearest one *existing at order time*, not the most profitable one visible later.
6. **Survivorship / selection in the daily scan.** Scanning history for "good" rejection blocks and only counting the ones that worked is the confirmation-bias failure mode the blueprint itself warns about (Part D).

---

### A.3 Look-ahead bias: the master checklist

Apply to **both** strategies and to any future strategy:

- [ ] Every signal references only bars with `t_close <= now`.
- [ ] Swing pivots timestamped at confirmation (`i+k`), never at the extreme (`i`).
- [ ] BOS / sweep logic uses **body close**, not wick, where the definition requires it.
- [ ] Higher-timeframe context (daily) applied only to **strictly later** lower-timeframe bars (no same-period leakage).
- [ ] Entry fills modeled at next-bar open or with explicit slippage, not at the signal bar's close.
- [ ] Limit orders fill only on genuine trade-through.
- [ ] Same-bar stop/target conflicts resolved worst-case (stop first) absent tick data.
- [ ] Volatility/regime filters computed only from past information.
- [ ] Indicators with warm-up (ATR, rolling vol) drop or quarantine warm-up rows.
- [ ] Any parameter chosen by looking at results is counted in the multiple-testing budget (Part D).
- [ ] Costs (commission + spread + slippage) applied to **every** trade before judging edge.

---

## Part B — Position sizing & risk math

> Formulas below are presented with the verdict first, then the math, then a Python sketch. All are implementable with `numpy`/`pandas` only (free).

### B.1 ATR-based volatility targeting (vetting the blueprint's formula)

**The blueprint's idea — hold constant *dollar* risk by sizing inversely to ATR — is correct and standard.** The canonical formula is:

```
PositionSize (units) = DollarRiskPerTrade / (StopDistance_in_price * PointValue)
```

where, for an ATR-based stop, `StopDistance_in_price = m * ATR` (m = ATR multiplier, e.g., 1.5–2.0):

```
PositionSize = (Equity * risk_fraction) / (m * ATR * PointValue)
```

This is exactly the formula in the practitioner literature: *Position Size = Dollar Risk / (ATR × Multiplier)* and *Position Size = Dollar Risk per Trade / (ATR Multiplier × ATR × Point Value)*. Example: \$100k account, 1% risk = \$1,000; ATR(14)=\$3, multiplier 2 → stop distance \$6 → 166 shares. As volatility rises the unit count falls, holding dollar risk constant. ([pro.stockalarm.io](https://pro.stockalarm.io/blog/average-true-range-atr-guide), [quantifiedstrategies.com](https://www.quantifiedstrategies.com/volatility-based-position-sizing/), [quantstrategy.io](https://quantstrategy.io/blog/using-atr-to-adjust-position-size-volatility-based-risk/))

**Verdict on the specific blueprint formula (rolling 20-period ATR + a "volatility scaling coefficient").**
- ✅ **Rolling 20-period ATR** is a fine, conventional volatility proxy (use Wilder's ATR or a simple rolling mean of True Range; be consistent). 14 and 20 are both common; the choice is a (counted) parameter.
- ✅ The "**volatility scaling coefficient**" *is* the ATR multiplier `m` when it defines stop distance, and/or a global risk knob. Both are legitimate.
- ⚠️ **Caveats that must be encoded:**
  1. **ATR must be lagged** — use `ATR` computed on bars up to and including the entry bar's close (or the prior close), never the bar you're entering on if that bar isn't closed. (Look-ahead.)
  2. **Stop distance and ATR must use the same price units** (points), and `PointValue` (dollar value per point per unit/contract) must be correct for the instrument. Mixing these is the most common real-world sizing bug.
  3. **Round to tradeable lot size** *after* computing the raw size, and re-check that rounded risk ≤ budget.
  4. **Cap leverage / notional** independently — ATR sizing can demand huge size in ultra-low-vol regimes. Always impose a max notional and max units.
  5. **The stop you size against must equal the stop you actually use.** If the strategy's structural stop (e.g., "far edge of the 5-min trigger candle" in A.2) differs from `m*ATR`, size against the **actual** stop distance, not ATR. ATR sizing is for strategies whose stop *is* ATR-defined; for structural stops, use `StopDistance = |entry − stop_price|` directly in the same formula.

```python
import numpy as np, pandas as pd

def wilder_atr(df: pd.DataFrame, n: int = 20) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()  # Wilder smoothing

def position_size(equity, risk_fraction, stop_distance_price, point_value, lot=1):
    """stop_distance_price = m*ATR (ATR-stops) OR |entry-stop| (structural stops)."""
    if stop_distance_price <= 0:
        return 0
    dollar_risk = equity * risk_fraction
    raw = dollar_risk / (stop_distance_price * point_value)
    units = np.floor(raw / lot) * lot
    return int(max(units, 0))
```

### B.2 Volatility scaling (portfolio level)

Target a constant *portfolio* volatility by scaling exposure:

```
scaling_factor = target_vol / realized_vol            # leverage on the strategy/asset
weight(t) = sigma_target / sigma_realized(t)
```

i.e., lever up in calm regimes, de-lever in turbulent ones. This raises Sharpe for risk assets and balanced/risk-parity portfolios, at the cost of pro-cyclical de-leveraging into crashes. ([Man Group](https://www.man.com/insights/the-impact-of-volatility-targeting), [QuantPedia](https://quantpedia.com/an-introduction-to-volatility-targeting/)) **Caveats:** estimate `sigma_realized` from *past* returns only (e.g., trailing 20–60d, or an EWMA); annualize consistently (`sigma_annual = sigma_daily * sqrt(252)`); cap the scaling factor (a max leverage); and beware feedback — many funds de-lever simultaneously, which the ECB notes can amplify sell-offs. ([ECB](https://www.ecb.europa.eu/press/financial-stability-publications/fsr/focus/2020/html/ecb.fsrbox202005_02~f6616db9be.en.html))

### B.3 Kelly & fractional Kelly

**Discrete (binary bet) Kelly:**
```
f* = (b*p - q) / b = p - q/b          with q = 1 - p, b = win/loss payoff ratio
```
([ryanoconnellfinance.com](https://ryanoconnellfinance.com/kelly-criterion/), [coriva.eu.org](https://coriva.eu.org/en/kelly-criterion-position-sizing/))

**Continuous / Gaussian-returns Kelly (the relevant one for trading a return stream):**
```
f* = (mu - r) / sigma^2
```
the excess-return-to-variance ratio; for a strategy, `f* ≈ mean(return) / var(return)` per period, which equals leverage. ([epchan.blogspot.com — "Kelly formula revisited"](http://epchan.blogspot.com/2009/02/kelly-formula-revisited.html))

**Use fractional Kelly. This is not optional for a solo researcher.** Full Kelly assumes you *know* `p`, `b`, `mu`, `sigma`; you don't — you estimated them from a finite, possibly overfit sample, so true Kelly is unknown and full Kelly massively over-bets. Half-Kelly retains ~75% of the growth with roughly half the drawdown; most practitioners use **half- or quarter-Kelly**, and Chan treats the Kelly leverage as an **upper limit**, not a target. ([epchan.blogspot.com — "How much leverage should you use?"](http://epchan.blogspot.com/2006/10/how-much-leverage-should-you-use.html), [coriva.eu.org](https://coriva.eu.org/en/kelly-criterion-position-sizing/))

```python
def kelly_binary(p, b):           # b = avg_win/avg_loss
    return p - (1 - p) / b

def kelly_continuous(returns, rf=0.0):
    mu, var = returns.mean() - rf, returns.var(ddof=1)
    return 0.0 if var == 0 else mu / var          # this IS leverage

def fractional_kelly(f_star, fraction=0.5, cap=1.0):
    return float(np.clip(f_star * fraction, -cap, cap))
```

> **Honesty flag:** Kelly inputs estimated on in-sample data are biased high (the same overfitting Part D describes), so Kelly computed on a backtest is itself optimistic. Recompute on out-of-sample / walk-forward returns and still divide by 2–4.

### B.4 Simple risk parity / inverse-volatility weighting

**Inverse-volatility (naïve risk parity):**
```
w_i = (1/sigma_i) / sum_j (1/sigma_j)
```
Equalizes each asset's *standalone* volatility contribution. **True risk parity** equalizes each asset's *marginal contribution to portfolio risk*, which accounts for correlations and generally needs a small optimizer. ([researchaffiliates.com](https://www.researchaffiliates.com/publications/articles/1014-harnessing-volatility-targeting), [kundan-reads.readthedocs.io](https://kundan-reads.readthedocs.io/en/latest/finance/risk_management/volatility_target/))

```python
def inverse_vol_weights(returns: pd.DataFrame, lookback=60):
    vol = returns.tail(lookback).std(ddof=1)            # past data only
    inv = 1.0 / vol.replace(0, np.nan)
    w = inv / inv.sum()
    return w.fillna(0.0)

def risk_parity_weights(returns: pd.DataFrame, lookback=120, iters=500, lr=0.1):
    """Equal risk contribution via simple projected gradient (numpy-only)."""
    cov = returns.tail(lookback).cov().values
    n = cov.shape[0]; w = np.ones(n) / n
    for _ in range(iters):
        port_var = w @ cov @ w
        mrc = cov @ w                       # marginal risk contribution
        rc = w * mrc                        # risk contribution
        grad = rc - port_var / n            # drive toward equal RC
        w = np.clip(w - lr * grad, 0, None)
        s = w.sum(); w = w / s if s > 0 else np.ones(n) / n
    return w
```
For a single-instrument intraday strategy, B.4 mainly matters once you run **multiple** uncorrelated strategies and want to allocate capital across them — which is the right way to grow this project.

---

## Part C — ML for trading on free tools (honest edition)

### C.1 The honest headline

For a solo researcher on free tools, **ML is usually the *wrong* first tool** and frequently a *negative-value* one, because the dominant failure mode in retail quant is **overfitting/data-leakage**, and ML expands the surface area for both by orders of magnitude. López de Prado's "10 Reasons Most Machine Learning Funds Fail" is explicitly about how *professionals with far more data and infrastructure* still fail at this. ([GARP / López de Prado PDF](https://www.garp.org/hubfs/Whitepapers/a1Z1W0000054x6lUAA.pdf)) ML *can* add value — but only inside the rigorous validation scaffolding of Part D, and usually as a **filter on a rules-based signal (meta-labeling)** rather than as the primary signal generator.

### C.2 Feature engineering (free)

Build features that are (a) computable from past data only and (b) ideally *stationary*:
- **Returns & log-returns**, rolling mean/std, rolling skew/kurtosis. Tools: `pandas`.
- **Technical features:** RSI, MACD, Bollinger %B, ATR, ADX via **`pandas-ta`** (pure Python, free) or **TA-Lib** (free, C-accelerated). ([blog.dataengineerthings.org](https://blog.dataengineerthings.org/python-for-algorithmic-trading-the-complete-beginners-guide-559e7256adfc))
- **Structure-derived features for *our* strategies:** distance to `mid`/OR boundaries, time-since-BOS, sweep depth, fib level of current price, daily-bias flag. These turn the discretionary primitives into numeric features.
- **Fractional differentiation (López de Prado):** make price series stationary *while preserving memory* (ordinary first-differencing destroys memory; raw prices are non-stationary). This is a genuinely useful, finance-specific feature transform.

> **Leakage rule for features:** every rolling/EWMA feature must use only data up to `t`. Fit scalers/imputers **inside** each CV fold's training set, never on the whole series.

### C.3 Labeling — the triple-barrier method (López de Prado)

Instead of "return over the next N bars," set **three barriers** per event: an **upper** (profit-take), a **lower** (stop), and a **vertical** (time limit). The label is determined by **which barrier is hit first** (+1 / −1 / 0). Barriers are **volatility-scaled per observation** (e.g., width = `k * sigma_t`), so quiet and wild periods are labeled comparably — the key advantage over fixed-horizon labeling. ([Advances in Financial Machine Learning, 2018](https://gildan-bonus-content.s3.amazonaws.com/GIL2476_AdvancesFinancial/GIL2476_AdvancesFinancial_BonusPDF.pdf); [mlfinpy docs](https://mlfinpy.readthedocs.io/en/latest/Labelling.html); [hudsonthames.org](https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/)) This labeling is **the natural target for our two strategies** because each already has a profit target and a stop — triple-barrier labels are essentially "did this setup hit target before stop within the holding window."

**Meta-labeling:** keep your *rules-based* model as the primary side-decision (long/short), then train a *secondary* ML classifier to predict **whether to take or skip** each primary signal (sizing 0/1). This improves precision/F1 and is far safer than letting ML pick direction from scratch. ([hudsonthames.org](https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/))

### C.4 The BIG data-leakage pitfalls (memorize these)

1. **Train/test temporal contamination.** Standard k-fold CV shuffles time and trains on the future — *forbidden* in finance. ([Wikipedia: Purged CV](https://en.wikipedia.org/wiki/Purged_cross-validation); [abouttrading.substack.com](https://abouttrading.substack.com/p/my-key-takeways-from-maros-lopez))
2. **Overlapping labels.** Triple-barrier (and any multi-bar horizon) makes labels overlap in time, so adjacent train/test samples share information → leakage even without shuffling. Fix with **purging** (drop train samples whose label window overlaps the test set) and **embargo** (drop a buffer of train samples immediately after the test set). ([Advances in FML]; [Wikipedia](https://en.wikipedia.org/wiki/Purged_cross-validation))
3. **Non-unique / autocorrelated samples** inflate effective sample size → over-optimistic significance. Use sample-uniqueness weights (López de Prado).
4. **Feature leakage:** fitting scalers/encoders/feature-selection on the full dataset; using future-anchored indicators; target leakage from a feature that encodes the label.
5. **Survivorship & point-in-time data** (delisted tickers removed; restated fundamentals). For intraday futures/FX this is smaller, but corporate actions and contract rolls still bite.
6. **Multiple testing / selection bias:** trying many models/features/params and reporting the best (Part D). This is *the* killer.

### C.5 Walk-forward / purged evaluation (the only acceptable way)

- **Walk-forward (anchored or rolling):** train on `[t0, t1]`, test on `[t1, t2]`, roll forward; concatenate out-of-sample results. Mimics live deployment.
- **Purged K-Fold CV with embargo:** k-fold but purge train samples overlapping each test fold and embargo a post-test buffer. ([Wikipedia](https://en.wikipedia.org/wiki/Purged_cross-validation))
- **Combinatorial Purged CV (CPCV):** generate many train/test path combinations to get a *distribution* of out-of-sample performance and estimate the **Probability of Backtest Overfitting (PBO)**. ([towardsai.net](https://towardsai.net/p/l/the-combinatorial-purged-cross-validation-method); [Bailey et al.](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf))
- `sklearn`'s `TimeSeriesSplit` is a free starting point but does **not** purge/embargo — implement purging yourself or port the López de Prado routines.

### C.6 Libraries — status & verdict (free only)

| Library | What it's for | Status / license | Verdict for Project ALPHA |
|---|---|---|---|
| **scikit-learn** | Core ML, pipelines, `TimeSeriesSplit`, metrics | Free, BSD, active | ✅ Backbone. Use `Pipeline` so transforms fit inside folds. |
| **LightGBM** | Gradient-boosted trees (tabular) | Free, MIT, active | ✅ Best default model for tabular financial features; fast, handles non-linearities, gives feature importance. |
| **XGBoost** | Gradient-boosted trees | Free, Apache-2.0, active | ✅ Alternative to LightGBM; either is fine. |
| **Microsoft Qlib** | Full AI quant pipeline: data, model zoo, backtest, Alpha158/360 factors, workflows | **Free, MIT, active** (Microsoft Research) | ✅ Worth studying/adopting for its data layer + walk-forward infra; heavier learning curve; equity-centric but adaptable. ([github.com/microsoft/qlib](https://github.com/microsoft/qlib)) |
| **mlfinlab** (Hudson & Thames) | López de Prado implementations (triple-barrier, purged CV, fractional diff, meta-labeling) | ⚠️ **Now closed-source / proprietary license** — no longer freely usable. ([github issue #496](https://github.com/hudson-and-thames/mlfinlab/issues/496), [LICENSE](https://github.com/hudson-and-thames/mlfinlab/blob/master/LICENSE.txt)) | ❌ Do **not** depend on it (violates the $0/open-source constraint). |
| **mlfinpy** | Open-source re-implementation of López de Prado tooling | Free (open-source), early/active | ✅ Free substitute for the mlfinlab feature set — vet correctness. ([pypi.org/project/mlfinpy](https://pypi.org/project/mlfinpy/), [docs](https://mlfinpy.readthedocs.io/en/latest/Labelling.html)) |
| **pandas-ta / TA-Lib** | Technical indicators / features | Free | ✅ Feature engineering. |
| **vectorbt** (open-core) | Vectorized backtesting at scale | Apache-2.0 + Commons Clause (free for our use; some features paid in PRO) | ✅ Fast parameter sweeps — but speed *enables* multiple-testing sin; pair with Part D discipline. ([github.com/polakowo/vectorbt](https://github.com/polakowo/vectorbt)) |
| **backtesting.py / Backtrader** | Event-driven backtesting | Free | ✅ More realistic fills/event semantics; good for final validation of the two strategies. |

> **mlfinlab status, stated plainly:** the project still exists and is maintained, but its license is **proprietary/closed-source**, not OSI-approved open source. For a strict $0/open-source mandate, treat it as off-limits and use **mlfinpy** or hand-rolled implementations instead. ([Hudson & Thames LICENSE](https://github.com/hudson-and-thames/mlfinlab/blob/master/LICENSE.txt))

### C.7 When classic rules-based beats ML for a solo researcher

Prefer **rules-based** when (most of the time for this project):
- **Few trades / short history** → not enough independent samples for ML to generalize; Chan: there are usually "not enough historical trades to achieve statistical significance," and optimized params "suffer from data snooping bias." ([epchan.blogspot.com](http://epchan.blogspot.com/2017/11/optimizing-trading-strategies-without.html))
- You want **interpretability and a falsifiable economic hypothesis** (Part D). A 3-rule strategy is auditable; a 200-feature GBM is not.
- You have **limited compute/time** and a high risk of silent leakage.
- Chan's antidote is explicit: **"simple and linear strategies"** resist overfitting and data-snooping better than complex ones. ([epchan.blogspot.com](http://epchan.blogspot.com/2017/11/optimizing-trading-strategies-without.html))

Reach for **ML** when: you have many features whose *interaction* matters, enough independent events to support purged CV, and you deploy it as a **meta-label filter** on an already-sensible rules signal — never as an unconstrained alpha-search over thousands of configs. ML's honest role here is **risk filtering and sizing**, not magical signal discovery.

---

## Part D — The intellectual-honesty section: a rigorous edge-discovery process

### D.1 Start from the null: these patterns probably have no edge

The source blueprint's own admission is the correct prior. Smart-Money-Concepts / support-resistance constructs are **(a) subjective** — two skilled traders mark different order blocks on the same chart — and **(b) appear with the same frequency on randomized/synthetic price as on real price**, which means "it worked" is largely **survivorship + confirmation bias**: indicators that paint hundreds of zones will always have *some* zone near any reversal, and humans remember the hits and forget the misses. ([dailypriceaction.com](https://dailypriceaction.com/blog/smart-money-concepts/), [mindmathmoney.com](https://www.mindmathmoney.com/articles/smart-money-concepts-the-ultimate-guide-to-trading-like-institutional-investors-in-2025)) **Therefore the burden of proof is on the strategy to beat a properly randomized null, not on us to disprove it.**

This is consistent with the broader literature: Bailey, Borwein, López de Prado & Zhu show that "high simulated performance is easily achievable after backtesting a relatively small number of alternative strategy configurations… the higher the number of configurations tried, the greater the probability that the backtest is overfit," and that under realistic conditions overfitting produces **negative** expected out-of-sample returns, not merely zero. ([*Pseudo-Mathematics and Financial Charlatanism*, Notices of the AMS, 2014](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2308659); [phys.org summary](https://phys.org/news/2014-04-pseudo-mathematics-financial-charlatanism.html))

### D.2 The pipeline (each gate can KILL the strategy)

```
Economic hypothesis
   ↓  (must be falsifiable & have a mechanism)
In-sample design on a held-out development window
   ↓  (fix rules & params; LOG every variant tried)
Out-of-sample / walk-forward (purged + embargoed) validation
   ↓  (survives unseen data with costs?)
Multiple-testing correction  →  Deflated Sharpe / PBO
   ↓  (edge survives the number of trials?)
Monte Carlo robustness  (randomized null, trade shuffling, bootstrap, param perturbation)
   ↓  (edge ≠ luck / ≠ random charts?)
Paper / forward trading  (real-time, real frictions, real psychology)
   ↓  (live OOS confirms backtest?)
ONLY THEN: real money, small, with kill-switches
```

**1. Hypothesis first.** Write the economic rationale *before* coding: *why* would an 08:00 range or a daily liquidity sweep create exploitable order flow? "It looks like it works on the chart" is not a hypothesis. A hypothesis you can't state mechanistically you can't trust when it later "works."

**2. In-sample design (development set).** Reserve the most recent chunk of data and **do not look at it.** Design and tune only on the development window. **Keep a literal log of every configuration you try** (params, filters, variants) — this count is the input to Step 4. Chan: prefer simple/linear formulations; minimize free parameters. ([epchan.blogspot.com](http://epchan.blogspot.com/2017/11/optimizing-trading-strategies-without.html))

**3. Out-of-sample / walk-forward, with costs.** Evaluate on never-seen data via anchored/rolling **walk-forward** and **purged K-Fold + embargo** (Part C.5). Apply realistic commission + spread + slippage to **every** trade. A strategy that's only profitable gross is not a strategy. ([Wikipedia: Purged CV](https://en.wikipedia.org/wiki/Purged_cross-validation))

**4. Correct for multiple testing — the step retail skips.**
   - **Deflated Sharpe Ratio (DSR):** deflates the observed Sharpe for (i) the **number of independent trials** `N`, (ii) the **variance of the trial Sharpes**, and (iii) **non-normality** (skew/kurtosis) and sample length. The benchmark uses the *expected maximum* Sharpe under the null of no skill:
     `SR0 = sqrt(Var[SR_n]) * [ (1−γ)·Z⁻¹(1 − 1/N) + γ·Z⁻¹(1 − 1/(N·e)) ]`, with γ = Euler–Mascheroni ≈ 0.5772. DSR is the probability the true Sharpe exceeds this null-max. ([Bailey & López de Prado, *The Deflated Sharpe Ratio*](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf); [Wikipedia](https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio))
   - **Probability of Backtest Overfitting (PBO):** via **combinatorially-symmetric cross-validation (CSCV)** — the probability that the config you'd pick as best *in-sample* ranks **below median out-of-sample**. High PBO ⇒ your selection process is overfitting, regardless of the headline Sharpe. ([Bailey, Borwein, López de Prado & Zhu, *The Probability of Backtest Overfitting*](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf); [CSCV overview](https://towardsai.net/p/l/the-combinatorial-purged-cross-validation-method))
   - Practical: a great-looking Sharpe found after 500 configs is usually noise. Report `N`, the DSR, and the PBO alongside any Sharpe — *or the result is not credible.*

**5. Monte Carlo robustness (multiple angles):**
   - **Randomized-price null (directly addresses the blueprint's admission):** run the *exact* strategy on many **synthetic/shuffled** price series that preserve the instrument's statistical properties (e.g., block-bootstrap of returns, or a fitted GARCH/AR simulation — Chan's recommended approach since "prices are more abundant than trades"). If the strategy earns as much on random charts as on the real one, **it has no edge** — exactly the SMC failure mode. ([epchan.blogspot.com — optimizing without overfitting](http://epchan.blogspot.com/2017/11/optimizing-trading-strategies-without.html))
   - **Trade-order / returns bootstrap:** resample the sequence of trade P&Ls to get confidence intervals on Sharpe, CAGR, and **max drawdown** (point estimates lie).
   - **Parameter perturbation:** nudge every parameter ±10–20%. A real edge degrades *gracefully* across a *plateau*; an overfit one collapses off a knife-edge peak.
   - **Regime / sub-period splits:** does it survive different years, volatility regimes, and instruments?

**6. Paper / forward trading.** Run **live, real-time, paper** for a meaningful window. This catches look-ahead bugs the backtest hid, real fills/latency/slippage, data-feed quirks, and — crucially — **your own discretionary deviations** (these templates are discretionary in origin; forward testing reveals whether the *mechanized* version matches what you imagined).

**7. Real money — last, small, reversible.** Only after all gates pass: deploy small, with hard risk limits, position caps, and a kill-switch tied to a max-drawdown / live-vs-backtest divergence threshold. Size with **fractional** Kelly on **out-of-sample** statistics (Part B.3).

### D.3 Why most retail backtests are overfit — the citations

- **Bailey, Borwein, López de Prado, Zhu (2014), *Pseudo-Mathematics and Financial Charlatanism*, Notices of the AMS.** Few configurations are enough to manufacture a great backtest; the more you try, the worse the overfitting; overfit strategies have *negative* expected OOS returns. Because researchers rarely disclose how many configs they tried, investors can't gauge overfitting. ([SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2308659), [phys.org](https://phys.org/news/2014-04-pseudo-mathematics-financial-charlatanism.html))
- **López de Prado (2018), *Advances in Financial Machine Learning*.** Triple-barrier labeling, meta-labeling, fractional differentiation, **purged k-fold CV + embargo**, sample uniqueness, and the discipline of treating backtesting as a *research tool, not a discovery tool*. ([book bonus PDF](https://gildan-bonus-content.s3.amazonaws.com/GIL2476_AdvancesFinancial/GIL2476_AdvancesFinancial_BonusPDF.pdf), [key-takeaways summary](https://abouttrading.substack.com/p/my-key-takeways-from-maros-lopez))
- **López de Prado, *The 10 Reasons Most Machine Learning Funds Fail* (GARP).** Even professionals fail — chiefly via leakage, multiple testing, mis-specified backtests, and ignoring the structure of financial data. ([GARP PDF](https://www.garp.org/hubfs/Whitepapers/a1Z1W0000054x6lUAA.pdf))
- **Bailey & López de Prado, *The Deflated Sharpe Ratio*** and **Bailey et al., *The Probability of Backtest Overfitting*** — the two quantitative tools that turn "trust me" into a number. ([DSR](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf), [PBO](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf))
- **Ernest Chan, *Algorithmic Trading: Winning Strategies and Their Rationale* (2013)** and his QuantCon talks/blog. Data-snooping bias from too many parameters; not enough trades for significance; **prefer simple/linear strategies**; optimize **time-series-model** parameters (GARCH/AR) and simulate paths rather than over-fitting trade-level params; treat Kelly leverage as an upper bound. ([epchan.blogspot.com](http://epchan.blogspot.com/2017/11/optimizing-trading-strategies-without.html), [Backtesting and its Pitfalls PDF](https://epchan.com/img/links/Backtesting-and-its-Pitfalls.pdf))
- **On the specific templates:** SMC's subjectivity and the "random charts look the same" problem mean these two strategies should be treated as **hypotheses with a low prior**, validated against a randomized-price null before any further investment. ([dailypriceaction.com](https://dailypriceaction.com/blog/smart-money-concepts/), [mindmathmoney.com](https://www.mindmathmoney.com/articles/smart-money-concepts-the-ultimate-guide-to-trading-like-institutional-investors-in-2025))

### D.4 Bottom line for Project ALPHA
1. **Encode both strategies exactly as specified in Part A** so they can be tested fairly — done.
2. **Assume they have no edge until they survive Part D**, especially the randomized-price null and DSR/PBO with an honest trial count.
3. **Keep them rules-based first.** Only add ML as a **meta-label filter** with purged CV once a rules-based version shows out-of-sample promise.
4. **Report `N` (trials), Deflated Sharpe, PBO, and net-of-cost OOS results** for every claim. No exceptions. This is the difference between research and self-deception.

---

## Appendix — Free Python tool stack

| Need | Free library | Note |
|---|---|---|
| Data wrangling | `pandas`, `numpy` | tz-aware timestamps mandatory |
| Indicators / features | `pandas-ta`, `TA-Lib` | features from past data only |
| ML models | `scikit-learn`, `lightgbm`, `xgboost` | use `Pipeline`; fit transforms in-fold |
| López de Prado tooling | **`mlfinpy`** (open) / hand-rolled | avoid closed-source `mlfinlab` |
| Full quant pipeline | **Microsoft `qlib`** (MIT) | data layer + walk-forward infra |
| Fast backtests / sweeps | `vectorbt` (open-core) | speed enables overfitting — pair with Part D |
| Realistic event backtests | `backtesting.py`, `Backtrader` | better fills for final validation |
| Stats / Monte Carlo | `scipy`, `statsmodels`, `arch` (GARCH) | bootstrap, DSR, PBO, synthetic paths |

---

## Sources

**López de Prado / overfitting / validation (primary)**
- Bailey, Borwein, López de Prado, Zhu — *Pseudo-Mathematics and Financial Charlatanism* (Notices of the AMS, 2014): https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2308659 · summary https://phys.org/news/2014-04-pseudo-mathematics-financial-charlatanism.html
- Bailey & López de Prado — *The Deflated Sharpe Ratio*: https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf · https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio
- Bailey, Borwein, López de Prado, Zhu — *The Probability of Backtest Overfitting*: https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
- López de Prado — *The 10 Reasons Most Machine Learning Funds Fail* (GARP): https://www.garp.org/hubfs/Whitepapers/a1Z1W0000054x6lUAA.pdf
- *Advances in Financial Machine Learning* (bonus PDF): https://gildan-bonus-content.s3.amazonaws.com/GIL2476_AdvancesFinancial/GIL2476_AdvancesFinancial_BonusPDF.pdf · key takeaways https://abouttrading.substack.com/p/my-key-takeways-from-maros-lopez
- Purged cross-validation: https://en.wikipedia.org/wiki/Purged_cross-validation · CSCV/CPCV https://towardsai.net/p/l/the-combinatorial-purged-cross-validation-method

**Triple-barrier / meta-labeling**
- mlfinpy labelling docs: https://mlfinpy.readthedocs.io/en/latest/Labelling.html
- Hudson & Thames — meta-labeling & triple-barrier: https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/

**Ernest Chan**
- Optimizing trading strategies without overfitting: http://epchan.blogspot.com/2017/11/optimizing-trading-strategies-without.html
- Kelly formula revisited: http://epchan.blogspot.com/2009/02/kelly-formula-revisited.html · How much leverage: http://epchan.blogspot.com/2006/10/how-much-leverage-should-you-use.html
- Backtesting and its Pitfalls (PDF): https://epchan.com/img/links/Backtesting-and-its-Pitfalls.pdf

**Strategy primitives (ICT/SMC) — for precise encoding, not endorsement**
- BOS / swing points / CHoCH: https://tradingstrategyguides.com/day-3-smc-ict-market-structure-explained-bos-choch-swing-points-2026/ · https://www.xs.com/en/blog/break-of-structure/ · https://www.luxalgo.com/blog/market-structure-shifts-mss-in-ict-trading/ · https://innercircletraders.net/what-is-an-ict-market-structure/
- Rejection block vs order block: https://ictnotebook.com/articles/rejection-block/ · https://howtotrade.com/blog/ict-rejection-block/ · https://smartmoneyict.com/ict-rejection-block/
- SMC subjectivity / "random charts" critique: https://dailypriceaction.com/blog/smart-money-concepts/ · https://www.mindmathmoney.com/articles/smart-money-concepts-the-ultimate-guide-to-trading-like-institutional-investors-in-2025

**Position sizing & risk**
- ATR position sizing: https://pro.stockalarm.io/blog/average-true-range-atr-guide · https://www.quantifiedstrategies.com/volatility-based-position-sizing/ · https://quantstrategy.io/blog/using-atr-to-adjust-position-size-volatility-based-risk/
- Kelly criterion: https://ryanoconnellfinance.com/kelly-criterion/ · https://coriva.eu.org/en/kelly-criterion-position-sizing/
- Volatility targeting: https://www.man.com/insights/the-impact-of-volatility-targeting · https://quantpedia.com/an-introduction-to-volatility-targeting/ · https://www.ecb.europa.eu/press/financial-stability-publications/fsr/focus/2020/html/ecb.fsrbox202005_02~f6616db9be.en.html
- Risk parity / inverse vol: https://www.researchaffiliates.com/publications/articles/1014-harnessing-volatility-targeting · https://kundan-reads.readthedocs.io/en/latest/finance/risk_management/volatility_target/

**Free Python tooling**
- Microsoft Qlib: https://github.com/microsoft/qlib
- mlfinlab license (closed-source): https://github.com/hudson-and-thames/mlfinlab/blob/master/LICENSE.txt · https://github.com/hudson-and-thames/mlfinlab/issues/496
- mlfinpy: https://pypi.org/project/mlfinpy/
- vectorbt: https://github.com/polakowo/vectorbt
- Python algo-trading / feature engineering overview: https://blog.dataengineerthings.org/python-for-algorithmic-trading-the-complete-beginners-guide-559e7256adfc
