# Design — Four-family Monte Carlo validation

**Status:** Implemented
**Date:** 2026-08-12
**Authority:** `CLAUDE.md`, ADR-0006, ADR-0009, ADR-0013, ADR-0014, ADR-0029

## Purpose and non-purpose

The required `monte_carlo` stage measures path and scenario risk after the randomized-price
robustness suite and before optimization. It does not test a no-edge null, prove profitability,
remove overfitting, reveal the final holdout, enable paper trading, or authorize orders.

The supplied video transcript teaches three families using trade returns: resampling with
replacement shows sequence sensitivity; regime-switching resampling retains clusters by drawing
from state-specific distributions and a transition matrix; a fitted continuous distribution tests
tails absent from the finite backtest. ALPHA preserves those questions but substitutes canonical
OOS account returns. This retains position sizing, costs, overlapping exposure, dividends, and
mark-to-market accounting. The fourth family uses Kronos-generated OHLCV and full engine replay,
never observed-signal replay.

## Families and contracts

| Family | Input | Paths | Estimation and replay | Principal caveat |
|---|---|---:|---|---|
| IID empirical | OOS account returns | 10,000 | sample with replacement to the OOS horizon | removes dependence |
| causal regime Markov | OOS account returns + prior-known market volatility | 10,000 | calm/volatile empirical emissions and a fitted 2x2 transition matrix | two-state approximation |
| Student-t | OOS account returns | 10,000 | fit log-return location, scale, and degrees of freedom; map back to simple returns | parametric misspecification |
| Kronos synthetic OHLCV | real training prefix + exact OOS calendar | 128 | one independent semantic seed per tail; rebuild strategy; fresh full-engine replay | pretraining overlap and calibration uncertainty |

The regime classifier uses trailing 63-session volatility shifted so the current return cannot
choose its own state. The calm/volatile boundary is the training-prefix median and never refits in
OOS. At least 20 OOS observations and 10 outbound transitions are required in each state.

All families report terminal-return, maximum-drawdown, longest-loss-streak, loss, and 50%-ruin
distributions. Loss and ruin probabilities carry Wilson 95% intervals. Existing ALPHA risk bands
grade each family independently.

## Commands and immutable artifacts

```text
alpha monte-carlo classical --from-run RUN_ID
alpha monte-carlo kronos --from-run RUN_ID --forecast-eval-run RUN_ID
alpha suite run PROJECT EXPERIMENT monte_carlo
alpha project review-monte-carlo PROJECT EXPERIMENT \
  --decision continue|revise|reject --actor ACTOR --reason TEXT
```

Classical v3 runs contain the observed OOS series, raw return paths, per-path metrics, regime
emissions/diagnostics, and a report. Kronos v3 runs contain observed OOS, raw and projected OHLCV,
engine account returns, per-path metrics, model/calibration diagnostics, rolling origins, and a
report. Manifests bind every artifact hash plus source validation/snapshot/cutoff, configuration,
semantic seeds, generator versions, and model provenance. Completed run directories never receive
figures or reviews. Non-CPU best-effort inference or mutable `main`/`master` model and tokenizer
revisions are explicit warnings rather than reproducibility claims.

Kronos output validation rejects non-finite or non-positive OHLC and negative volume. Raw values
remain preserved. Projection changes only high/low, and only enough to enclose open/close; every
adjustment is recorded. `Forecaster.forecast(..., step_ts=...)` receives the frozen snapshot's
future timestamps exactly.

## Gate semantics and authority

The suite launches classical and Kronos as separate steps sharing one source validation. It may do
so after a terminal failed bootstrap null so weak strategies still receive all four diagnostics.
The combined stage is:

- `pass` only when every family is clear;
- `warning` when any valid family warns and none fails;
- `fail` when any required family/evidence is invalid, missing, tampered, operationally failed, or
  non-estimable.

There is no vote. A warning remains a hard downstream pause until an exact-hash owner review says
`continue`; `revise` and `reject` do not satisfy the prerequisite. The review is CLI-only and its
actor string is audit metadata, not cryptographic identity proof. Optimization and final holdout
rebuild and verify both robustness and Monte Carlo prerequisites.

## Workstation explanation contract

The `monte_carlo` figure section contains cross-run four-panel equity fans, terminal-return
histograms, and drawdown/ruin distributions; classical runs also expose emissions and transition
diagnostics, while Kronos runs link CRPS-baseline and empirical-coverage charts. Every catalogue
entry declares the question, interpretation, uncertainty, caveat, source run, path count, and
model assumptions. Figures remain deterministic derived cache artifacts.

## Acceptance boundary

Statistical recovery and invalid-input tests, future-poison bias guards, exact-timestamp and
physical-candle tests, FakeForecaster full-engine integration, immutable contract/tamper tests,
warning-review governance, thin-surface projections, deterministic figure rendering, OpenAPI/client
freshness, frontend accessibility, packaging, and wheel smoke checks comprise the release gate.

Portfolio/Qlib candidates retain dependence-aware validation. Per-asset Kronos generation is not
presented as a joint portfolio distribution. Kronos adequacy is evaluated only from post-cutoff
proper scores and coverage; insufficient or weak skill remains a warning rather than an invented
probability claim.
