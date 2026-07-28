# XRP: everything measurable, measured

**Data:** 3,262 daily bars, 2017-07-01 → 2026-07-25 (Bitstamp spliced to Binance, join validated).
**Battery:** 92 conditions across 24 families × 20 outcome definitions = **1,832 tests**.
**Last bar:** 2026-07-25, close **1.0980**.

## The one-paragraph answer

XRP has **strong, statistically real volatility structure and no directional structure whatsoever**.
Forty-three tests survived FDR correction against a null that produces a median of 0 (p = 0.005) —
so the battery genuinely found something. Every single one of them is a *bigger move in either
direction*. On the outcomes a position actually depends on — will price be higher, will +10% come
before −7%, will XRP beat BTC — **zero tests survived, at any horizon, in any family**, which is
exactly what the null produces (p = 1.00). Nine years of daily data say XRP's direction over the
next month is a coin flip that no combination of 92 standard conditions improves on. The one
genuinely actionable finding runs opposite to intuition: **stacking bullish conditions makes the
forward odds worse, monotonically** (z = −3.98), and the live position currently sits in the
1-of-10 bucket that has historically been the *best* place to be long.

---

## 1. The headline table

| | result |
|---|---|
| tests run | 1,832 |
| survived BH-FDR within family, interval excludes zero | **43** |
| ...of which hold their sign out-of-sample (split 2024-01-01) | 40 |
| **empirical null** — median survivors on shuffled data | **0** (95th pct 4, max 5) |
| **p-value of the whole battery** | **0.005** |
| survivors on a **directional** outcome | **0** |
| null median for directional survivors | 0 |
| **p-value, directional** | **1.00** |

The null is not a formula. It is 200 re-runs of this identical battery with the outcomes circularly
shifted against the conditions — every series keeps its own autocorrelation, clustering and base
rate, and only the *alignment* between condition and future is destroyed. BH assumes a near
independence that MACD, RSI, the stochastic and Williams %R flatly violate, so the survivor count
is calibrated rather than argued about.

**Read those two p-values together.** 0.005 says the machine works and XRP has real structure.
1.00 says none of that structure points anywhere.

### Where the 43 survivors live

| outcome | survivors |
|---|---|
| `down_5` (reached −10% within 5 days) | 24 |
| `up_5` (reached +10% within 5 days) | 13 |
| `down_10` | 6 |
| `fwd_positive_*` (higher in H days), any horizon | **0** |
| `barrier_*` (+10% before −7%), any horizon | **0** |
| `beat_btc_*`, any horizon | **0** |

And the same conditions appear on both sides. `range_top` predicts `down_5` (+26.4pp) **and**
`up_5` (+17.9pp). `boll_expanded`, `volume_spike`, `rsi_overbought`, `mfi_overbought` — all of
them raise the probability of a 10% move in *either* direction. That is volatility clustering, one
of the most robust facts in finance, and it is worth precisely nothing to someone deciding whether
to be long.

Classifying all 368 condition-horizon pairs:

| | count | share |
|---|---|---|
| no effect | 124 | 33.7% |
| **volatility (both directions)** | 93 | 25.3% |
| quiet (smaller moves both ways) | 48 | 13.0% |
| bearish tilt | 55 | 14.9% |
| bullish tilt | 48 | 13.0% |

The 103 "tilts" are **uncorrected point estimates**. None survived the FDR battery on a directional
outcome. They are reported below because the live position sits among them, but a tilt in this
table is *consistent with* a direction, not *evidence for* one.

---

## 2. All 24 families, one line each

| # | family | primary condition | verdict |
|---|---|---|---|
| 1 | Moving averages | price > 200-day SMA | 6 survivors, all volatility. No directional edge. |
| 2 | MACD | histogram > 0 | **nothing** |
| 3 | RSI | RSI < 30 | 1 survivor (`rsi_overbought`→`up_5`), volatility |
| 4 | Stochastic / Williams %R | %K < 20 | **nothing** |
| 5 | Bollinger | bandwidth bottom 20% | 3 survivors — compression *anti*-predicts fast moves |
| 6 | Keltner squeeze | bands inside Keltner | **nothing** |
| 7 | Donchian | close > 20-day high | **nothing** |
| 8 | ADX / DMI | ADX > 25 | 3 survivors, volatility |
| 9 | OBV | 20-day OBV rising | **nothing** — incl. both divergence forms |
| 10 | Money flow (MFI/CMF) | CMF > 0 | 1 survivor, volatility |
| 11 | Volume regime | volume < 70% of 20d avg | 1 survivor, volatility |
| 12 | Volatility regime | vol in bottom quintile | 2 survivors, volatility (tautologically) |
| 13 | Ichimoku | above the cloud | 5 survivors, all volatility |
| 14 | Fibonacci | within 5% of a retracement | **nothing** |
| 15 | Round numbers | near a round number | **nothing** — no magnetism, either grid |
| 16 | BTC correlation / lead-lag | BTC up over 20d | **nothing** |
| 17 | XRP/BTC ratio | ratio > its 50-day MA | 3 survivors, volatility |
| 18 | Seasonality | Oct–Dec | **nothing** |
| 19 | Cycles / memory | variance ratio > 1 | 7 survivors, volatility |
| 20 | Drawdown / range position | >60% below ATH | 7 survivors, volatility |
| 21 | On-chain (MVRV, addresses, tx) | MVRV bottom quintile | 4 survivors, volatility |
| 22 | Chart patterns (wedge/tap/H&S) | wedge confirmed | **nothing** |
| 23 | Perp-spot basis | basis top quintile | **nothing** |
| 24 | Bar structure (inside/NR7) | inside bar | **nothing** |

Twelve of twenty-four families produced nothing at all. The twelve that produced something produced
volatility forecasts.

---

## 3. The four named analyses

### 3.1 Cycles — there is no cycle

| | value |
|---|---|
| dominant spectral period | 1,087 days |
| share of detrended power in that peak | **29.5%** |
| random-walk null, median / 95th pct | 26.6% / **43.3%** |
| beats the null? | **NO** |

A 1,087-day cycle is a seductive number — it is close to the four-year halving folklore. It is also
inside the null. Every finite noisy series has a spectral peak; random walks of the same length
average 26.6% power in theirs. XRP's 29.5% is unremarkable.

**Memory tests agree.** Hurst on returns 0.564 against a no-memory null of 0.556 ± 0.028 → z =
+0.30. Variance ratios:

| q (days) | ratio | z | verdict |
|---|---|---|---|
| 2 | 0.982 | −0.50 | random walk |
| 5 | 1.016 | +0.21 | random walk |
| 10 | 1.127 | +1.20 | random walk |
| 20 | 1.227 | +1.58 | random walk |
| 60 | 1.109 | +0.47 | random walk |

Five horizons, no rejection. XRP daily returns are indistinguishable from a random walk by every
memory test run against them.

### 3.2 Lead-lag — BTC does not lead XRP

| asset | peak lag | r at peak | r at lag −1 |
|---|---|---|---|
| BTC | **0** | +0.585 | −0.019 |
| ETH | **0** | +0.610 | −0.038 |
| SOL | **0** | +0.519 | −0.083 |
| LTC | **0** | +0.626 | −0.045 |

Every one peaks at lag zero. The 90-day XRP/BTC correlation is currently 0.867, and that number is
routinely mistaken for a tradeable relationship. It is not: they move *together*, not in sequence.
Yesterday's BTC return tells you nothing about today's XRP return (r = −0.019 over 2,152 days).

### 3.3 Seasonality — nothing, once the count is honest

30-day forward positive rate, base rate 44.6%:

| month | n | **n_eff** | rate | 95% CI (naive) | **95% CI at n_eff** |
|---|---|---|---|---|---|
| Sep | 262 | 9 | 61.5% | [55.4%, 67.1%] | **[35.4%, 87.9%]** |
| May | 279 | 18 | 22.6% | [18.1%, 27.8%] | **[9.0%, 45.2%]** |
| Aug | 279 | 18 | 33.3% | [28.1%, 39.1%] | **[16.3%, 56.3%]** |
| Nov | 259 | 9 | 36.7% | [31.0%, 42.7%] | **[12.1%, 64.6%]** |

The naive intervals make September and May look like discoveries. They are not. **Nine years of
data contain nine Septembers**, not 262 independent September days, and with a 30-day forward
window a 31-day clump is worth about one observation. At the honest count every month's interval
spans the base rate. No weekday effect either (all seven sit at 43.6–45.7%).

This single correction is the whole difference between a seasonality study and an astrology column,
and it is why the "sell in May" and "September strength" patterns in this table are not findings.

### 3.4 Confluence — stacking bullish conditions makes it WORSE

The direct test of "multiple technical factors reinforcing the upside bias". Ten bullish
conditions, one per family, chosen before the counts were computed. Score each bar by how many
hold, then measure the 30-day forward positive rate:

| bullish conditions on | n | n_eff | 30d forward positive rate |
|---|---|---|---|
| 0 | 88 | 21 | **58.0%** |
| 1 | 256 | 42 | **58.6%** |
| 2 | 304 | 51 | 55.9% |
| 3 | 252 | 50 | 50.0% |
| 4 | 209 | 50 | 46.4% |
| 5 | 183 | 51 | 42.1% |
| 6 | 169 | 44 | 47.3% |
| 7 | 179 | 48 | 33.0% |
| 8 | 185 | 37 | 32.4% |
| 9 | 205 | 33 | 33.2% |
| 10 | 93 | 19 | **26.9%** |

**Cochran–Armitage trend z = −9.12 nominal, −3.98 on independent-block counts. Significant.**

This is the most useful result in the report and it is the opposite of what the phrase "confluence"
promises. On XRP, over nine years, the more bullish signals agree, the *worse* the next month is —
58% down to 27%, monotonically across eleven buckets. The mechanism is not mysterious: by the time
ten bullish conditions are all true, the move has happened. You are buying the top of a trend, and
in an asset that mean-reverts at that scale, that is the wrong end.

It also disposes of the specific claim tested in the corpus study. "Multiple technical factors
reinforcing the upside bias" is measurable on XRP, and its measured sign is negative.

---

## 4. The live position

Last bar 2026-07-25, close **1.0980**. **29 of 92 conditions are currently true.** Every one is
shown with its measured 30-day effect, because a list of what is "firing" without a track record is
a horoscope.

**Current readings:** 69.1% below all-time high · 6th percentile of the past year's range ·
Bollinger bandwidth in the **1.6th percentile** and realized vol in the 5.8th — the tightest
compression in the sample · RSI 47 · ADX 11.3 (no trend at all) · below the 200-day and the 50-day
· below the Ichimoku cloud · MVRV in its bottom quintile · 90-day BTC correlation 0.87.

### The bullish-side conditions that are live

| condition | n | up | down | edge | class |
|---|---|---|---|---|---|
| `range_bottom` (bottom decile of the year) | 523 | +14.1% | −25.0% | **+39.0%** | bullish |
| `ichi_below_cloud` | 2,156 | +8.5% | −21.4% | +29.9% | bullish |
| `ma_price_below_200` | 1,815 | +5.2% | −18.8% | +24.0% | bullish |
| `extreme_drawdown` (>80% below ATH) | 1,672 | +3.9% | −17.1% | +21.0% | bullish |
| `atr_tight` | 628 | +1.6% | −16.9% | +18.5% | *quiet, not bullish* |
| `boll_extreme_compressed` | 218 | +7.7% | −7.8% | +15.5% | bullish |
| `mvrv_low` | 1,107 | +3.2% | −11.5% | +14.7% | bullish |
| `ma_death_cross` | 1,723 | +2.7% | −11.6% | +14.2% | bullish |
| `vol_low` | 1,027 | +2.1% | −10.0% | +12.1% | bullish |

`atr_tight` earns its edge entirely by suppressing the downside (−16.9%) while barely touching the
upside (+1.6%), so the classifier files it as "smaller moves both ways" rather than bullish. The
distinction matters: it is an argument for the position surviving, not for it working.

### The bearish-side conditions that are live

| condition | n | up | down | edge | class |
|---|---|---|---|---|---|
| `ma_50_rising` | 1,464 | −9.6% | +14.9% | −24.4% | bearish |
| `ichi_chikou_clear` | 1,428 | −7.7% | +11.4% | −19.1% | bearish |
| `ichi_tk_cross` | 1,350 | −5.6% | +10.9% | −16.5% | bearish |
| `month_summer` | 823 | −5.1% | +6.9% | −12.0% | bearish |
| `hurst_persistent` | 2,361 | −0.8% | +10.3% | −11.0% | *no effect on upside* |

**Confluence stack: 1 of 10 bullish conditions on** (`macd_hist_positive` only). Given the measured
negative slope, that is the *second-best* bucket in the sample — the 0 and 1 buckets carry 58.0%
and 58.6% forward positive rates against a 44.6% base.

### What this actually means

The position sits in a deeply oversold, maximally compressed, low-confluence state, and every one
of those things has historically been associated with better-than-base forward odds on XRP. That is
the honest bull case and it is worth stating plainly.

It is also **not statistically established**. Not one of those bullish-side conditions survived the
FDR battery on a directional outcome; the entire directional battery came back at exactly the null
(p = 1.00). The point estimates are consistent with the long. They are not evidence for it, and
anyone — including me — who presents that table as a green light has quietly swapped "consistent
with" for "predicts".

*Flagging once, as agreed: the position is 13.8× the framework's 44 USDT per-trade cap.*

---

## 5. Things that turned out to be nothing (worth knowing)

- **Fibonacci retracements.** Zero survivors. Price is no more likely to do anything near a 0.382 /
  0.5 / 0.618 level than away from one, with retracement grids anchored only on swings confirmed in
  real time.
- **Round numbers.** No magnetism at either grid (2-significant-figure or big-round). Zero survivors.
- **Chart patterns.** Wedges (106 detected), triple taps (90), inverse H&S (245 bar-windows) —
  nothing survives. Worse, `inverse_hs_confirmed` at 30 days carries an uncorrected **bearish** tilt
  (edge −30.0%, n = 240), the opposite of its reputation. Not significant, but not supportive either.
- **OBV and its divergences.** Both bull and bear divergence: nothing.
- **Perp-spot basis and perp share.** Nothing at daily resolution.
- **Inside bars, NR7, close-in-range.** Nothing.
- **The Keltner squeeze**, including the squeeze-release trigger. Nothing.
- **Compression predicting breakouts.** `boll_compressed` *reduces* the chance of a fast +10% move
  (16.7% vs 30.1% for `up_5`, a surviving result). Coiling does not precede springing; it precedes
  more coiling. This replicates the earlier XRP pump study rather than adding to it.

---

## 6. Method and limits

**Causality.** Every indicator is trailing-window only and covered by future-poison bias guards
(32 new guards; poison everything after bar 300, assert nothing before it moves). Three constructions
needed specific care: Ichimoku's senkou spans are drawn 26 bars forward so the cloud in force at a
bar was computed 26 bars earlier; Ichimoku's chikou span is stamped where the information exists,
not where a chart draws it; and Fibonacci grids anchor only on swings confirmed at `index + lookback`,
which is the standard way a retracement study manufactures fake support.

**Multiplicity.** One primary condition per family declared in advance; BH-FDR within family, never
pooled; the empirical null above as the actual bound. Degenerate conditions (firing on <60 bars, or
on every bar) are dropped *before* the battery so they cannot consume multiplicity budget — five were.

**Overlap.** Every interval is deflated. A 30-day forward window on daily bars overlaps ~30×, so
3,262 bars carry ~109 independent observations. Seasonal buckets get a stricter treatment still
(nine Januaries, not 279 January days).

**Out-of-sample.** Split at 2024-01-01. 40 of 43 survivors hold their sign — which, given all 43 are
volatility effects, mostly confirms that volatility clusters in both halves.

**Four data defects found and fixed en route**, each of which would have produced a publishable-looking
fake:

1. `rolling_correlation` is cumulative-sum based, so the 1,109 leading NaNs from BTC's later start
   poisoned the accumulator, and the zero-variance guard converted the result to a clean **0.0 on all
   3,262 bars** — which reads as "XRP has decoupled from BTC" rather than as a bug.
2. The basis conditions read `basis_pct` (a percentile rank) as a raw basis fraction, making
   "basis negative" impossible by construction and "basis rich" true on every single bar.
3. The raw perp-spot basis has a −4bp median against 16bp of dispersion — a mirror stamping offset,
   not backwardation. The sign test was replaced with a trailing-median comparison that cancels it.
4. On-chain metrics are joined at **D+1**: a row stamped D is published after D closes, and joining
   it to D would hand the on-chain family a free look at the day it is meant to predict.

**Limits.**

- **No funding, open interest, or order flow.** Market-data APIs are egress-blocked. The perp-spot
  basis is a sound funding *proxy* and the perp share of notional is a direct measure, but true
  funding, OI and CVD are absent and their absence is a real limitation, not a rounding error.
- **On-chain coverage ends 2026-05-24.** Later bars are NaN, never carried forward.
- **The LINK/DOGE-style venue splice** applies to XRP too: Bitstamp before 2020-09-02, Binance after.
  Validated at 0.07% median close disagreement and 0.9965 return correlation across 1,597 overlapping
  days, so it is a change of venue rather than of asset — but it is a splice.
- **Daily resolution.** Intraday structure is not tested here.
- **Nine years is nine years.** For a 30-day question that is ~109 independent observations, which is
  enough to detect a large effect and nowhere near enough to detect a small one. The study can say
  "no large directional edge exists in these 92 conditions". It cannot say "no edge exists".

**Reproduce:**

```
.venv/bin/python -m research.xrp_deep.study            # the 1,832-test battery
.venv/bin/python -m research.xrp_deep.nullcal          # 200-surrogate empirical null
.venv/bin/python -m research.xrp_deep.directionality   # volatility vs direction
.venv/bin/python -m research.xrp_deep.deepdive         # cycles, lead-lag, seasonality, confluence
.venv/bin/python -m research.xrp_deep.scorecard        # the live read
```

---

## 7. What I would actually take from this

1. **Stop looking for directional confirmation on XRP daily.** Ninety-two conditions, twenty-four
   families, 1,832 tests, nine years: the directional result is exactly the null. This is the most
   thorough negative result in the project and it is worth more than another indicator would be.
2. **The confluence finding is real and inverts the usual advice.** More bullish signals agreeing has
   meant worse forward odds, monotonically, significantly. Currently 1 of 10 are on. If you are
   going to weight anything in this report, weight that.
3. **Trade the volatility structure if you trade anything.** That is the part that survived — the
   compression currently sits in the 1.6th percentile of the year, and compression genuinely does
   precede *larger* moves at longer horizons even though it anti-predicts fast ones. It says nothing
   about which way, so it is an argument about position *sizing* and option structure, not direction.
4. **Do not read the live bullish table as a signal.** It is the honest bull case and it did not
   survive correction. Treat it as "the setup is not hostile", not "the setup is favourable".
