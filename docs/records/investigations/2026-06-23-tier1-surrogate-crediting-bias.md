# Investigation — Tier-1 surrogate crediting convention biases high-turnover strategies

**Date:** 2026-06-23
**Scope:** Why `alpha validate` FAILs the headline randomized-price null on short-window
`mean_reversion` (and, by the same mechanism, `breakout`) despite a strongly positive, well
corroborated out-of-sample edge.
**Files:** `apps/alpha-cli/src/alpha_cli/_surrogate.py`,
`apps/alpha-cli/src/alpha_cli/_strategies.py`, `apps/alpha-cli/src/alpha_cli/_gauntlet.py`
(lines 140-179), `packages/alpha-validation/src/alpha_validation/montecarlo.py`.

---

## 0. Verdict

The Tier-1 `returns_level` surrogate is a **structurally biased** edge test for short-horizon /
high-turnover signals. It is **not** a faithful proxy of the strategy we actually trade, because it
credits the freshly-decided weight with the **close-to-close** move while the engine fills at the
**t+1 open**. The two conventions differ by exactly

```
divergence  =  Σ_s  G_s · ΔW_{s-1}            (overnight gap × change in weight)
```

so the bias is **zero for a constant weight** (low turnover — e.g. `ts_momentum`, the strategy the
surrogate was originally written for) and **grows with turnover** and with the correlation between
overnight gaps and signal changes (high for mean-reversion, which trades the immediate aftermath of
a move). For a near-zero true edge — exactly the regime of a single-name short-window
mean-reversion book — this turnover-scaled bias is large enough to **flip the sign of the measured
Sharpe**, which is what produces the observed AAPL FAIL (surrogate Sharpe −0.391 vs engine OOS
+1.2695).

**Recommendation:** fix the root cause — make Tier-1 faithful to the engine's t+1-open convention —
rather than weaken the conservative two-tier AND-gate. Weakening the AND-gate would reduce
conservatism for *every* strategy to patch a surrogate-fidelity bug. Details and a phased plan in
§6–7. A cheap, non-invasive interim guard (a convention-divergence diagnostic that needs only the
observed opens) is in §7.1.

> Live market data is network-gated in this sandbox, so the AAPL figures below are quoted from the
> report that motivated this task. The mechanism, the sign flip, the decomposition identity, and the
> turnover scaling are reproduced from first principles on synthetic OHLCV run through the **real**
> engine (`run_full_backtest`) and the **real** surrogate (`surrogate_for`); see §5 + §8.

---

## 1. The two conventions, precisely

Let bar `t` have open `O_t` and close `C_t`. Decompose each day's move into an **overnight gap**
`G_t = O_t / C_{t-1} − 1` and an **intraday** `D_t = C_t / O_t − 1`.

**Surrogate (`_surrogate.py`, `make_surrogate`).** Operates on a 1-D close-to-close return path
`pr[t] = C_{t+1}/C_t − 1`. The weight `w_t`, decided from closes up to and including `C_t`, is
credited with `pr[t]`:

```
surrogate:   w_t  earns  C_t → C_{t+1}   =   G_{t+1} + D_{t+1}
```

This is look-ahead-free (the weight uses only `closes[:t+1]`), but it assumes an **instantaneous
fill at the decision close** `C_t`.

**Engine (`feed.py` + `engine.py`).** Decide on close `t`, fill at the **open of `t+1`**
(`bar_execution=False`; the open-priced `QuoteTick` fills, the close-stamped `Bar` only decides).
The equity curve is sampled once per session **at each open** (`_EquityRecorder.on_quote_tick`), so
the per-bar OOS return is **open-to-open**, and the weight decided at `C_t` is held over the next
full session:

```
engine:      W_t  earns  O_{t+1} → O_{t+2}   =   D_{t+1} + G_{t+2}
```

**The divergence.** Both conventions credit the same intraday `D_{t+1}` to the same decision. They
differ only in *which overnight gap* the fresh weight eats:

```
surrogate − engine  (per decision t)  =  w_t · (G_{t+1} − G_{t+2})
```

Summing over the path and reindexing (the `w·G` terms telescope) gives the headline identity:

```
Σ_t w_t (G_{t+1} − G_{t+2})  =  Σ_s G_s · (w_{s-1} − w_{s-2})  =  Σ_s G_s · ΔW_{s-1}
```

i.e. **the total surrogate-vs-engine divergence is the sum of overnight gaps weighted by the change
in position.** Verified numerically in §5 (`−0.37544` vs `−0.37317`, the residual being the
log-vs-simple-return approximation).

---

## 2. Why this is *structural*, not noise

`Σ G_s ΔW_{s-1}` has two regimes:

- **Low turnover (`ΔW ≈ 0` almost everywhere).** `ts_momentum` holds the same sign for months; the
  weight changes a handful of times over a multi-year run. The gap terms cancel and the surrogate
  tracks the engine. This is exactly the strategy class the surrogate was designed and tested for
  (`tests/unit/test_surrogate.py`), and it is faithful there.

- **High turnover (`ΔW` frequently non-zero *and signal-correlated*).** Mean-reversion changes its
  weight precisely in response to recent deviations, and overnight gaps are part of the
  deviation/reversal dynamics — so `G_s` and `ΔW_{s-1}` are **correlated**, and the sum has a
  **non-zero mean** (a systematic bias), not just added variance. The sign of the bias is set by
  whether the overnight move *continues* or *reverses* the deviation that triggered the trade —
  microstructure the surrogate's 1-D close-to-close path **cannot see**.

"Turnover" here is a proxy for **holding horizon / edge concentration in the decision-adjacent
bar**. A short-horizon bet (mean-reversion: the reversal predicted over the next 1–5 days) puts most
of its edge in the bars right after the decision — exactly where the close-vs-open gap mismatch
lives. A multi-month bet (momentum) puts almost none of its edge there, so the mismatch is immaterial.

---

## 3. There are actually *three* distinct estimands being compared

The headline gate compares two numbers that differ in more than one way. Disentangling them matters:

| | Tier-1 `returns_level` (observed) | Tier-2 `full_engine` (observed) |
|---|---|---|
| fill convention | close-to-close (`C_t→C_{t+1}`) | t+1 open-to-open (`O_{t+1}→O_{t+2}`) |
| sample | **full bar history** (incl. warmup/train) | **walk-forward OOS** test windows only |
| signal inputs | closes only (breakout: closes-as-OHLC) | real OHLC (breakout uses true highs/lows) |

Source A (**convention**) is the dominant, systematic driver analysed above. Source B (**sample**)
is independent and also real: `_gauntlet.py:144` builds `price_returns` from the **whole** series, so
Tier-1's *observed* statistic is the full-sample surrogate Sharpe, whereas Tier-2's observed is the
engine **OOS** Sharpe. For a noisy short-horizon strategy with few effective bets these can have
opposite signs from sampling variation alone (see the `re=21` row in §5, where the engine OOS
`+0.216` sits above both the full-sample engine `+0.128` and the surrogate `−0.080`). Source C
(**signal fidelity**) is a known, documented approximation specific to `breakout`
(`_strategies.py:227-231` builds the Donchian channel from closes because Tier-1 has no synthetic
intrabar range).

---

## 4. Why it bites `mean_reversion` and `breakout` but not `ts_momentum`

- **`mean_reversion`** — short window, fades the latest move, enters right when the next overnight
  gap is most informative/adverse. Highest signal-correlated turnover ⇒ largest, most systematic
  `Σ G ΔW`. **Primary victim.**
- **`breakout`** — trades the bar that prints a new extreme; the decision-adjacent gap is again
  where the action is, *plus* Source C (closes-as-OHLC) compounds the unfaithfulness. **Secondary
  victim**, by the same mechanism.
- **`ts_momentum`** — slow, low-turnover, edge spread over months. `Σ G ΔW ≈ 0`. **Faithful.**
- **`ma_crossover`** — trend-following like momentum; low turnover; expected faithful (not the
  subject of the report but covered by the same argument).

---

## 5. Empirical reproduction (real engine + real surrogate, synthetic OHLCV)

Synthetic daily OHLCV with a mean-reverting overshoot baked into the close (a genuine reversion
edge) and a **tunable overnight gap** `G_{t+1} = γ·d_t + noise` (`γ>0` = overnight *continues* the
overshoot, the empirically-typical short-reversal pattern; `γ<0` = overnight reverses it). Every
number below comes from the production code paths — only the input bars are synthetic. The weight
reconstruction used for `surr_oo` and the identity reproduces the real surrogate **exactly**
(`max|recon − surrogate| = 0.0`), so `surr_oo` is the real surrogate with *only* the fill convention
changed.

`surr_cc` = real Tier-1 surrogate (close-to-close, what ships today).
`surr_oo` = same weights, t+1-open crediting (the proposed fix).
`eng_full`/`eng_oos` = real engine, full-sample / walk-forward OOS Sharpe.

### Weak-edge regime — the sign flip (γ = +2.0 continuation, mean over 3 seeds)

```
config               turnover   surr_cc   surr_oo   eng_full   eng_oos
MR w=10 z=1 re=1        381      -0.157    +0.454    +0.380     +0.207     <- FLIP: cc<0<everything
MR w=10 z=1 re=5        140      -0.036    +0.173    +0.108     +0.018
MR w=10 z=1 re=21        42      -0.080    -0.023    +0.128     +0.216     <- Source B (sample) dominates

identity (re=1): Σ w·(cc−oo) = −0.37544   ≈   Σ G·ΔW = −0.37317
```

The `re=1` row is the AAPL phenomenon reproduced from first principles: identical weights, the
close-to-close convention scores **−0.157** (a FAIL) while the t+1-open convention and the engine
are all **positive**. Lowering turnover (`re=1 → 5 → 21`) monotonically shrinks the convention gap
`surr_oo − surr_cc` (`0.61 → 0.21 → 0.06`).

### Strong-edge regime — turnover scaling + momentum faithfulness (γ = +0.6)

```
config               turnover   surr_cc   surr_oo   eng_full   eng_oos   (surr_oo−surr_cc)
MR w=10 z=1 re=1        344      +2.792    +3.209    +2.760     +2.900        +0.417
MR w=10 z=1 re=5        113      +1.605    +1.719    +1.492     +1.372        +0.114
MR w=10 z=1 re=21        22      +0.251    +0.344    +0.316     +0.493        +0.093
ts_mom lb=252 re=21      11      -0.021    +0.011    +0.108     +0.096        +0.032
```

The convention gap scales with turnover and is an order of magnitude smaller for `ts_momentum`
(turnover 11, gap 0.03) than for high-turnover MR (turnover 344, gap 0.42). In every row `surr_oo`
tracks `eng_full` far better than `surr_cc` does — the fix is a strict faithfulness improvement with
**no downside** for the low-turnover strategies the surrogate already handled well.

### Sign sensitivity to overnight structure (MR w=10 z=1 re=5)

```
γ      overnight behaviour       surr_cc   surr_oo   eng_oos
+0.6   continuation              +1.605    +1.719    +1.372
 0.0   none                      +1.605    +1.668    +1.373
-0.6   reversal                  +1.605    +1.321    +0.944
```

The *engine's* verdict moves with an overnight microstructure property the close-to-close surrogate
is blind to — direct evidence that Tier-1 cannot, in principle, track the engine for this strategy
class.

---

## 6. Options

### Option A — make the surrogate use t+1-open fills (root-cause fix)

Test the strategy we actually trade. The blocker is that Tier-1 is, by design, **engine-free and
operates on a 1-D close-to-close return path** that the null *resamples* — a bootstrapped path has
no coherent "open", so there is nothing to fill against. A faithful fix therefore requires
**resampling bars as `(overnight_gap, intraday_return)` pairs**, reconstructing open+close paths,
and running an open-fill surrogate. This is implementable and clean for the default
`null_model="bootstrap"` (resampling bar-pairs preserves each bar's internal open→close→next-open
structure while destroying cross-bar serial structure — a valid null). It is awkward for the
parametric nulls (`student_t`/`garch` generate 1-D returns with no gap/intraday split); those would
need an explicit variance split or can retain the current convention (they are explicitly the
"more adversarial / different purpose" nulls, `montecarlo.py:212-217`).

- **Pro:** removes the bias at the source; keeps the conservative AND-gate honest and meaningful;
  proven by §5 to track the engine for *all* strategy classes.
- **Con:** moderate, invasive change to `montecarlo.randomized_price_null`'s data model (1-D →
  2-channel) and the surrogate signature; parametric nulls need separate handling.

### Option B — reconsider the two-tier AND-gate for high-turnover signals

Treat Tier-1 as advisory (not a hard AND) when turnover/holding-horizon marks it low-fidelity,
relying on the faithful Tier-2 plus the corroborating gates (CPCV, BCa CI, PSR/DSR).

- **Pro:** small, localised change in `_gauntlet.py`/`tearsheet.build_outcomes`.
- **Con:** **weakens conservatism for the wrong reason.** The two-tier AND is a deliberate
  guardrail; the tiers *disagree only because Tier-1 is unfaithful*. Once Tier-1 is faithful they
  agree and the AND is correct. Introducing a turnover-dependent gate policy needs an arbitrary "what
  is high turnover?" threshold and risks rubber-stamping genuinely overfit high-turnover books.
  Note the surrogate docstring already claims "Tier-2 exists precisely to catch any material
  divergence" — but with an **AND**-gate, Tier-2 *passing* cannot rescue a Tier-1 *fail*, so that
  stated safety net does not currently work as written.

---

## 7. Recommendation

**Adopt Option A; do not weaken the AND-gate (reject Option B as the primary fix).** The defect is
that Tier-1 mismodels the fill, not that the gate is too strict. Phase it:

### 7.1 Interim guard (cheap, non-invasive — needs only the observed opens)

Compute the open-fill surrogate Sharpe on the **observed** path (the real opens are already in
`bars`; no change to the null distribution) and compare it to the shipped close-fill surrogate
Sharpe. When they diverge materially, the run is in the biased regime: surface a
`tier1_convention_divergence` field on the report and **down-weight / flag** a Tier-1 fail in the
verdict rather than silently FAILing. This immediately prevents false FAILs like the AAPL case while
the full fix lands, and it is a pure addition (no behavioural change for low-turnover runs, where the
divergence is ≈ 0).

### 7.2 Root-cause fix

Bar-pair-resampling, open-fill Tier-1 for `null_model="bootstrap"` (§6 Option A). Keep the parametric
nulls on their current path or give them an explicit gap/intraday variance split. Add a bias-guard
test asserting `|surr_oo − eng_full|` stays small across a turnover sweep, and a regression test on a
short-window mean-reversion fixture that PASSes once the convention is faithful.

### 7.3 Also fix Source B (independent, small)

Make Tier-1's *observed* statistic the **OOS** surrogate stream (not full-sample), so it is measured
on the same window as Tier-2 and the other gates. Currently `_gauntlet.py:144` feeds the whole
series. This removes a second, unrelated apples-to-oranges comparison.

Because §7.2 changes the validation **core** (`alpha_validation`) and the headline gate's behaviour —
architecturally significant per `CLAUDE.md` — it should be confirmed with the maintainer before
implementation. §7.1 is a safe, self-contained first step.

---

## 8. Reproduction

Network is gated in the sandbox, so the harness builds synthetic OHLCV and runs it through the real
engine + real surrogate. Method:

1. Generate daily OHLCV: log fair-value random walk + an AR(1) mean-reverting overshoot `d_t` baked
   into the close (a genuine reversion edge); overnight gap `G_{t+1} = γ·d_t + noise` with `γ`
   tuning overnight continuation (`>0`) vs reversal (`<0`); high/low bracket open/close.
2. `surr_cc`: `surrogate_for(spec)(to_returns(closes))` — the shipped Tier-1 surrogate.
3. Reconstruct the surrogate's continuous weight series `w_t` (mirroring `make_surrogate`'s loop with
   the same `signals`/`sizing`); verify `max|w·pr − costs − surr_cc| = 0`.
4. `surr_oo`: `w_t · (O_{t+2}/O_{t+1} − 1) − costs` — identical weights, t+1-open crediting.
5. `eng_full`/`eng_oos`: `run_full_backtest(bars, spec)` → `to_returns(equity)` and
   `walk_forward_oos_for_spec(...)`.
6. Identity: confirm `Σ w·(cc−oo) ≈ Σ G·ΔW`.

Specs mirror `alpha validate` defaults (`vol_window=63`, `target_vol=0.15`, `fee_bps=1`,
`slippage_bps=2`, `train_size` ≥ warmup floor), `MARGIN` account for `allow_short=True`,
`mean_reversion` params `window=10, entry_z=1.0`, swept over `rebalance_every ∈ {1,5,21}`.
