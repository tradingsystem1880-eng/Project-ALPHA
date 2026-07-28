# XRP triple-tap and trendline breaks — verdict

**Date:** 2026-07-28 · **Instrument:** XRP perpetual · **Question:** does the triple-tap at 1.02–1.05,
under a descending trendline and beneath three unmitigated bearish order blocks, justify a long?

## The answer

**No.** Not at this size, not at this stop, and not on this pattern.

The triple-tap carries no measurable edge. Pooled across seven series and 1,324 events, in the
configuration where the study has real statistical power, the pattern hits its target first
**33.38%** of the time against a **33.33%** breakeven, and beats its matched control by
**+0.63 percentage points with a 95% interval of [−2.13, +3.46]**. That interval contains zero. The
pattern is indistinguishable from its control.

For the trade as specified — stop 0.9900, target 2.7992, 90-day horizon — the same engine returns
**2.29% target-first against a 3.36% breakeven**, with price stopping out first **91.3%** of the
time and an expectancy of **−0.253R**.

## What was found

### Study 1 — triple-tap lows

The claim was that the third tap resolves upward. It does not.

| Horizon | median fwd return | P(up) |
|---|---|---|
| 5 d | −0.08% | 49.3% |
| 10 d | −1.67% | 44.9% |
| 20 d | −2.33% | 42.7% |
| 30 d | −0.72% | 47.4% |
| 60 d | +2.60% | 53.5% |

Forward returns after a confirmed triple tap are **negative at the median out to 30 days**, and
P(up) sits below 50% at every horizon short of 60 days. Six of seven assets show a negative 20-day
median. Directionally the pattern is mildly *bearish*, not bullish.

**Cross-asset, powered cell (3% stop, 2R, 10 days):**

| Asset | n | target-first | breakeven | 95% CI | edge vs control | 95% CI |
|---|---|---|---|---|---|---|
| XRP | 218 | 33.5% | 33.3% | [27.5, 40.0] | +1.8% | [−4.8, +8.9] |
| BTC | 282 | 33.7% | 33.3% | [27.5, 40.0] | −0.3% | [−6.2, +5.9] |
| ETH | 213 | 36.2% | 33.3% | [30.0, 42.8] | +1.4% | [−5.4, +8.7] |
| SOL | 116 | 30.2% | 33.3% | [22.6, 39.1] | +4.4% | [−4.1, +13.9] |
| LTC | 243 | 32.9% | 33.3% | [27.3, 39.1] | +0.8% | [−5.5, +7.5] |
| LINK | 32 | 34.4% | 33.3% | [20.4, 51.7] | +3.1% | [−12.8, +21.7] |
| XRP (Bitstamp) | 220 | 32.3% | 33.3% | [26.4, 38.7] | −2.6% | [−9.1, +4.4] |
| **Pooled** | **1,324** | **33.38%** | **33.33%** | **[30.89, 35.97]** | **+0.63%** | **[−2.13, +3.46]** |

Every single interval contains breakeven. No asset shows an edge, and the pooled estimate lands
0.05 percentage points above breakeven — noise.

**Walk-forward.** The confirmatory test is the out-of-sample period, and it fails: pooled in-sample
(pre-2023) 35.88%, pooled out-of-sample (2023–26) **32.45% — below breakeven**. BTC decayed
39.8%→30.7%, ETH 50.0%→32.9%, SOL 36.0%→28.6%. That decay pattern is what an in-sample artefact
looks like.

**Sweep.** 70 parameter configurations. **1** produced a raw p < 0.05 (about 3.5 were expected by
chance alone) and **0** survived Benjamini–Hochberg. Mean rate across configurations was **31.83%**,
*below* breakeven, and only **11 of 70 (16%)** cleared breakeven where ~50% would be expected under
a true no-edge null. The pattern is not merely edgeless; it is slightly worse than the payoff
requires.

The one config that looked good — tolerance 0.5%, n=37, 48.6%, p=0.038 — is exactly the result that
gets cherry-picked. Its BH q-value is 0.994.

**Fourth taps** (n=74) resolved up 52.1% at 20 days versus 42.7% for third taps. If anything the
fourth tap does *better*, which is the opposite of what "the third tap is special" predicts.

**Noise calibration.** The detector finds ~94 triple taps in a pattern-free random walk of the same
length; it found 218 in real XRP. Real markets have more structure than noise — but structure is
not prediction, and the barrier tests show the extra structure is not tradeable.

### Study 2 — trendline breaks

This reproduces the trap you already identified with order blocks. Retest **hold rates look
excellent — 70%** (95% CI [67, 72]) — and mean almost nothing: forward 20-day median after a break
is **+0.77%** with P(up) **51.7%**. On ETH and SOL the forward median is *negative* (−1.68%,
−1.01%).

Break-rule quality does separate cleanly, which is a genuine (if modest) finding:

| Rule | false break ≤3 bars | retest rate | hold rate |
|---|---|---|---|
| any close | 38% | 79% | 70% |
| ≥0.5 ATR | 19% | 65% | 69% |
| ≥1.0 ATR | **9%** | 53% | 68% |
| two closes | 22% | 68% | 70% |
| volume ≥1.5× | 23% | 63% | 67% |

Requiring a full-ATR close beyond the line cuts the false-break rate from 38% to 9%. That is worth
knowing operationally, but it does not create an edge — it only reduces how often you are wrong
about the break having happened.

Log versus linear fitting made no material difference (hold 70% vs 73%).

**Caveat, stated plainly:** 2,237 lines and 2,149 breaks over 12,918 bars means a "break" roughly
every six bars. These are nowhere near independent events, so the tight confidence intervals in this
section are optimistic. Treat the direction of these numbers, not their precision.

### Study 3 — confluence (your actual situation)

A triple tap sitting **under an unmitigated bearish order block** versus one in clear air:

| Asset | under bear OB | clear air |
|---|---|---|
| XRP | 27.7% (n=119) | 40.4% (n=99) |
| BTC | 33.5% (n=227) | 34.5% (n=55) |
| ETH | 32.8% (n=177) | 52.8% (n=36) |
| SOL | 29.6% (n=54) | 30.6% (n=62) |
| **Pooled** | **31.72%** (n=577) | **38.49%** (n=252) |

Difference **−6.78%**, 95% CI **[−13.93, +0.21]**. The interval just touches zero, so this is *not*
established at the 5% level — but the point estimate is negative on every asset, and on XRP the gap
is 12.7 points. The honest statement: **a triple tap under a bearish order block is not better than
one in clear air, and is probably worse.** Your setup is the "under" case.

## Why the trade fails even if the pattern worked

Three independent lines converge:

1. **A driftless random walk never clears breakeven at any plausible XRP volatility.** Simulating
   the 90-day barrier race: at 4%/5%/6% daily vol, P(target-first) is 0.35%/1.14%/2.13% and EV is
   −0.78R/−0.58R/−0.32R. Even at an extreme 7% daily it reaches only 2.86% — still under the 3.36%
   breakeven. **The structure is EV-negative under a no-edge null across the entire realistic vol
   range.**
2. **The measured rate is below breakeven anyway** — 2.29% against 3.36%, with 91.3% stopping out
   first. Your own prior work put the 90-day noise-hit at 91.0%; two independent datasets here
   reproduce it at 91.3% (Binance perp) and 91.4% (Bitstamp spot). That cross-check is the strongest
   validation in this report, and it validates the *bad* number.
3. **No stop placement escapes the squeeze.** Tighten and you are noise-stopped 91% of the time.
   Widen to the p75 sweep extension (16.87% below the tapped level → 0.8479) and R:R collapses to
   8.6:1, pushing breakeven to **10.40%** — far above any rate observed anywhere in this study.

## Two corrections to the numbers you are carrying

**Your confidence interval used the normal approximation you told me to avoid.** For 9 successes in
181 trials the normal interval is [1.81%, 8.14%] ≈ your quoted [1.8%, 8.0%]. The correct **Wilson
interval is [2.64%, 9.18%]**. The conclusion is unchanged — the lower bound is still under
breakeven — but the interval is shifted up and wider.

**Your effective sample size is ~39, not 181.** A 90-day horizon on 4H bars is a 540-bar forward
window, while 181 events across 20,866 bars sit ~115 bars apart: an overlap factor of **4.7×**. Two
independent derivations agree (events ÷ overlap, and independent 90-day blocks in the record). At
n_eff = 39 the Wilson interval widens to **[1.42%, 16.89%]**. This is precisely the failure you said
you had been burned by — one episode counted many times — and it is present in the numbers you are
acting on. In this study's own live-trade cell the same effect appears: n = 218 nominal, **n_eff =
24**, overlap 9.1×.

## Sizing, if you take it anyway

Your 44 USDT cap implies **724 XRP (~$760 notional)** at the current stop. The live position is
10,000 XRP — **13.8×** the cap. Flagged once, as agreed; the sizing decision is yours.

For reference, at wider stops: p50 sweep (0.9357) → 382 XRP; p75 sweep (0.8479) → 217 XRP; p90
sweep (0.7268) → 136 XRP. Every one of those raises breakeven above any rate this study measured.

## Limitations — read these before acting

- **Data provenance.** Every market-data API is egress-blocked in this environment (51 hosts probed;
  all exchanges and vendors returned `connect_rejected`). All series come from **third-party GitHub
  mirrors**, not from the exchanges. Each is SHA-256 pinned in `data.py`. The XRP series was
  validated against your chart before use: June 2026 low 1.0081, July 2026 low 1.0212, and a
  1.0847–1.0945 range on 2026-07-25 matching the order block you cited independently.
- **The last three days are missing.** Data ends 2026-07-25 21:15 UTC; the session date is
  2026-07-28. Your most recent bars are not in sample.
- **Your prior figures are unverified.** n=181, 784 order blocks, n=1,313 sweeps, the 60-cell grid —
  none of that code or data is in this repo. Carried as context, marked unverified throughout. The
  one figure independently reproduced here is the 91% 90-day stop rate.
- **The trendline section's n is inflated** by non-independent breaks, as noted above.
- **SOL and LINK have short histories** (2020-09 and 2024-03 respectively); LINK's n=32 makes its
  interval nearly uninformative.
- **Intrabar ambiguity resolves pessimistically.** When one bar spans both barriers, the labeler
  assigns the stop. Reported target-first rates are lower bounds; `optimistic=True` brackets the
  other extreme.

## Reproducing

```bash
uv sync --package alpha-validation && uv pip install -e packages/alpha-patterns --no-deps
.venv/bin/python -m pytest tests/unit/test_proportion.py tests/unit/test_barrier.py \
    tests/unit/test_pattern_detectors.py tests/bias_guards/test_pattern_no_lookahead.py -q
```

Charts: `research/xrp_triple_tap/out/{01_setup,02_evidence,03_gallery}.png`.

Detector correctness is established before any statistic: patterns are injected at known bar indices
and must be recovered exactly (15 cases), and a future-poison bias guard corrupts every bar after
*t* and requires detections on `[0, t)` to be unchanged.
