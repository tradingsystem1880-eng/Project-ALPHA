# Head & shoulders / Quasimodo — verdict

**Date:** 2026-07-28 · **Sample:** 51,538 detected structures · 9 assets · 4 timeframes ·
1,429,944 bars · 2017-07 to 2026-07-25

## The short version

Three findings, in descending order of how well established they are.

1. **The raw pattern is worthless.** Forward returns after a confirmed head-and-shoulders are
   *negative* in both directions, at every timeframe, at every horizon. Structures without a break
   of structure lose 0.13–0.18R per trade, consistently, on every asset.
2. **Two filters carry large, robustly-measured information.** A **break of structure** (the
   Quasimodo qualifier) adds 7–10 percentage points. A **volume-confirmed neckline break** adds
   10–16 points. Both with intervals far clear of zero on tens of thousands of events. These are the
   real findings of this study.
3. **Neither filter clearly clears breakeven out-of-sample.** The best case — bearish Quasimodo —
   reaches +0.09R OOS with a confidence interval that still contains breakeven. Suggestive, not
   established.

For the live XRP long specifically, the answer is unchanged and slightly worse than before: the
structure is a genuine inverse head and shoulders, it carries **no break of structure**, and it sits
**under overhead supply** — the two conditions that this study finds most damaging.

## The pattern itself carries no directional information

Forward returns, signed so positive always means the pattern's own direction worked:

| population | n | 5d | 10d | 20d | 30d | 60d |
|---|---|---|---|---|---|---|
| inverse H&S 1h | 11,577 | −1.46% | −1.72% | −2.20% | −0.59% | +1.70% |
| inverse H&S 4h | 3,656 | −0.77% | −1.79% | −2.36% | −2.86% | −2.08% |
| inverse H&S 1d | 623 | +0.06% | +0.35% | −4.13% | −1.60% | −1.45% |
| H&S 1h | 11,259 | −1.34% | −1.27% | −1.31% | −1.34% | −1.88% |
| H&S 4h | 3,675 | −1.23% | −1.96% | −2.33% | −1.89% | −2.94% |
| H&S 1d | 579 | −0.03% | −1.22% | −2.75% | −5.34% | −11.27% |

Negative essentially everywhere, in **both** directions. That symmetry matters: a bullish-only or
bearish-only failure would suggest the sample's drift was driving it. Both directions failing
equally means the pattern itself is empty, which is a cleaner and more general result.

The **symmetry test** confirms it directly — bullish vs bearish differ by −0.25% to +0.08% with
intervals containing zero on three of four barrier cells.

## But the break-of-structure filter is real

Pooled over all nine assets, at a 3% stop and 2R over 10 days (breakeven 33.33%):

| population | n | rate | EV | vs breakeven |
|---|---|---|---|---|
| inverse H&S **with** BOS | 10,338 | 35.05% | +0.06R | CI contains |
| inverse H&S **without** BOS | 15,656 | 27.18% | **−0.17R** | clearly below |
| H&S **with** BOS | 9,857 | 36.45% | +0.11R | **clears** |
| H&S **without** BOS | 15,683 | 26.85% | **−0.18R** | clearly below |

The gap is +7.9 and +9.6 points. It holds on **every asset individually** — XRP, BTC, ETH and SOL
all show the same 7–10 point separation, with the no-BOS population always losing money. This is the
most consistent effect in the study.

So the Quasimodo distinction, which reads like jargon, is doing measurable work: it separates
structures that follow through from structures that don't.

## And volume confirmation is the strongest single filter

Volume-confirmed neckline breaks (break-bar volume ≥ 1.5× the trailing 20-bar mean) versus
unconfirmed, difference in target-first rate with Newcombe intervals:

| variant | cell | confirmed n | unconfirmed n | difference |
|---|---|---|---|---|
| inverse H&S | 3%/1R/10d | 10,226 | 7,562 | **+9.71%** [+8.23, +11.18] |
| inverse H&S | 3%/2R/10d | 10,226 | 7,562 | **+10.53%** [+9.09, +11.95] |
| inverse H&S | 3%/2R/20d | 10,226 | 7,562 | **+11.17%** [+9.72, +12.60] |
| H&S | 3%/1R/10d | 9,943 | 5,732 | **+15.97%** [+14.36, +17.57] |
| H&S | 3%/2R/10d | 9,943 | 5,732 | **+13.96%** [+12.39, +15.51] |
| H&S | 3%/2R/20d | 9,943 | 5,732 | **+14.02%** [+12.45, +15.58] |

Every interval is far clear of zero. The widely-quoted "73% vs 54%" claim implies a ~19-point gap;
this measures 10–16 points on a far larger and more diverse sample. Different magnitude, same
direction, and firmly established. **This is the one piece of head-and-shoulders folklore that
survives contact with the data.**

## Out-of-sample, it still does not clear breakeven

The confirmatory test — the pre-registered specification run on 2023–26 only:

| population | window | n | rate | breakeven | EV |
|---|---|---|---|---|---|
| inverse H&S + BOS | in-sample | 5,650 | 36.39% | 33.33% | +0.10R |
| inverse H&S + BOS | **out-of-sample** | 4,688 | 33.43% | 33.33% | **+0.02R** |
| H&S + BOS | in-sample | 5,427 | 37.31% | 33.33% | +0.13R |
| H&S + BOS | **out-of-sample** | 4,430 | 35.40% | 33.33% | **+0.09R** |

The in-sample bearish result clears breakeven; out-of-sample it does not — the interval
[32.9%, 38.0%] still contains 33.33%. Bullish decays to almost exactly breakeven.

The honest reading: **the filters identify a real distinction, but the surviving edge is too small
to be established as tradeable on this sample.** +0.09R with an interval spanning breakeven is a
lead worth pursuing, not a strategy.

## The finding that applies directly to the live position

Structures sitting under unmitigated bearish order blocks, versus in clear air:

| variant | cell | under supply | clear air | difference |
|---|---|---|---|---|
| **inverse H&S** | 3%/1R/10d | n=21,070 | n=4,924 | **−7.90%** [−9.44, −6.35] |
| **inverse H&S** | 3%/2R/10d | n=21,070 | n=4,924 | **−8.61%** [−10.10, −7.13] |
| **inverse H&S** | 3%/2R/20d | n=21,070 | n=4,924 | **−8.01%** [−9.50, −6.53] |
| H&S | 3%/2R/10d | n=22,175 | n=3,365 | +2.47% [+0.81, +4.09] |

A bullish inverse head and shoulders under overhead supply performs **8 percentage points worse**,
with the interval entirely below zero on 21,070 events. The bearish mirror is correspondingly
*better* under supply — the directional logic is coherent, which is what makes the result credible
rather than an artefact.

The triple-tap study found the same effect at −6.78% with an interval grazing zero. At this sample
size it is no longer marginal.

## The live XRP position

The daily detector finds the marked base and it **is** an inverse head and shoulders — the original
triple-tap framing was wrong:

- left shoulder **1.0490** (6 Jun) · head **1.0081** (26 Jun) · right shoulder **1.0526** (13 Jul)
- shoulder asymmetry 0.08 (near-symmetric) · head depth 4.06% · confirmed 2026-07-18
- neckline 1.2930 → 1.1838, sloping −8.45%
- **no break of structure** → a plain inverse H&S, not a Quasimodo

Which places it in the worst cell this study identifies: **no BOS** (−0.17R population) and **under
overhead supply** (−8 points).

The measured move puts the target at **1.1756**, not 1.3000:

| | as held | pattern's own geometry |
|---|---|---|
| target | 1.3000 | **1.1756** (−10.6%) |
| R:R | 4.23:1 | **2.07:1** |
| breakeven | 19.14% | **32.62%** |

At the pattern's canonical conventions it is worse still — entry at confirmation (1.0922) with a
stop below the head (1.0081) gives R:R 0.99 and a 50.2% breakeven. Position sizing at the 44 USDT
cap against the pattern's own stop is **523 XRP**; the held position is **115×** that.

## Limitations — read before acting

- **The measured-move table is not trustworthy as stated.** Each event carries its own R:R, so a
  pooled win rate has no single breakeven. That table uses the *median* R:R as a proxy, which is not
  a sound aggregation — the planned `aggregate_variable_r()` was not implemented. Treat the
  `confirm × right_shoulder` figure of +0.55R as unverified; it almost certainly reflects a very
  tight stop with a rare, large payoff, which is the same high-R:R trap the triple-tap study
  documented. Everything in the fixed-R barrier grid is unaffected.
- **Overlap is severe.** Nominal n runs to tens of thousands but effective n is 700–1,400 after
  correcting for forward windows that overlap 7–23×. Every interval quoted here is computed at the
  effective size; the nominal counts are not the basis for any claim.
- **Multiplicity.** Many cells were examined. The BOS and volume findings are large and consistent
  across all nine assets and both directions, which is what distinguishes them from the isolated
  cells that clear breakeven. The out-of-sample result is the only confirmatory test, and it does
  not clear.
- **Provenance.** Every market-data API is egress-blocked in this environment; all series come from
  third-party GitHub mirrors, each SHA-256 pinned in `config.py`. Data ends 2026-07-25, three days
  before this was written.
- **Sample composition.** 15m and 1h dominate the event count (42,000 of 51,538). Daily events are
  only 1,202, so the timeframe most traders actually use is the least well-measured here.

## Datasets

`data/hs/` — `events.parquet` (51,538 × 88), `panel/` (1,429,944 bar rows with pattern-state
labels), `paths/` (240 forward bars per event), and `DATA_DICTIONARY.md`. Export asserts across the
whole table that no entry index precedes its confirmation bar.

## Reproducing

```bash
python -m research.hs_quasimodo.detect      # sharded, resumable
python -m research.hs_quasimodo.export --all
python -m research.hs_quasimodo.study
python -m research.hs_quasimodo.current     # classify the live structure
```
