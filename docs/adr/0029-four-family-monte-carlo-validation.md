# ADR-0029: Require four-family Monte Carlo path-risk validation

**Status:** Accepted
**Date:** 2026-08-12
**Deciders:** Project ALPHA owner and AI build agents

## Context

The existing randomized-price suite asks whether a strategy beats synthetic markets with no edge.
It does not answer the different question: how sensitive are the strategy's outcomes to return
ordering, persistent volatility states, unobserved heavy tails, or plausible model-generated market
paths? Treating both questions as one vote would obscure failure modes and encourage data snooping.

The supplied teaching transcript describes three useful ideas: empirical resampling with
replacement, regime-conditioned resampling through an estimated transition matrix, and parametric
tail simulation. Its examples use raw trade returns. ALPHA instead uses the canonical OOS account
return stream so sizing, overlapping exposure, fees, dividends, and mark-to-market effects remain in
the object being simulated. Kronos adds a fourth, structurally different family by generating
OHLCV, rebuilding signals, and replaying the canonical engine.

## Decision

- Add the required single-symbol daily `monte_carlo` stage after `robustness` and before
  `optimization`. A completed robustness run may feed it even when the bootstrap null failed, but
  optimization and holdout still require both the existing robustness gate and Monte Carlo.
- Publish three classical families from the source validation's exact OOS account returns: IID
  empirical bootstrap, a two-state causal volatility Markov bootstrap, and Student-t paths fitted
  in log-return space so simulated simple account returns cannot fall below -100%.
  Defaults are 10,000 paths, the observed OOS horizon, 95% intervals, and 50% drawdown ruin.
- Define calm/volatile state from trailing 63-session market volatility known before each scored
  return. Freeze the boundary from the training prefix. Fewer than 20 OOS emissions or 10 outbound
  transitions in either state is `not_estimable` and fails the combined stage.
- Keep Kronos heavyweight and separate. Generate 128 tails from the real training prefix on the
  exact frozen future timestamps, validate and retain raw output, apply only deterministic
  high/low enclosure projection, then rebuild the unchanged strategy and replay a fresh engine for
  every path with the source costs and OOS geometry.
- Bind immutable v3 evidence to the source run/snapshot, normalized configuration, semantic seeds,
  generator versions, model/tokenizer revisions, model identity, device, and rolling-origin
  forecast-evaluation hash. Model pretraining overlap is a permanent warning. Post-cutoff CRPS and
  coverage versus random-walk and stationary-bootstrap baselines measure adequacy; weak or sparse
  skill warns rather than pretending synthetic paths are calibrated probabilities. Non-CPU
  best-effort determinism and mutable model/tokenizer branch revisions also warn.
- Grade each family independently. Never majority-vote. Missing, invalid, tampered, operationally
  failed, or non-estimable evidence fails. Risk grade D/F, non-positive median terminal return,
  weak Kronos calibration, or declared caveats warn.
- A warning pauses progression until the trusted-local CLI records one append-only
  `continue|revise|reject` owner decision over the exact evidence hashes. REST and MCP expose only
  bounded reads and cannot make this decision.
- Figures are derived cache artifacts. The Workstation groups equity fans, terminal returns,
  drawdown/ruin, regime diagnostics, and Kronos calibration under `monte_carlo`, with the observed
  OOS path and explanatory metadata.

## Consequences

Scenario/path risk is now a required development artifact, not evidence that an edge exists. Kronos
is a calibrated stochastic generator, not a market oracle. Existing stationary-bootstrap,
Student-t, and GARCH randomized-price nulls, bootstrap confidence intervals, prop-firm simulation,
and fixed stress remain separate and unchanged. The first release is deliberately limited to
canonical single-symbol daily strategies; independently generated per-asset paths are not a
coherent portfolio scenario.

The public timestamp protocol gains optional exact `step_ts`; existing forecasters remain source
compatible. Core statistics live in `alpha_validation`, engine/model composition in `alpha_cli`,
and top-of-DAG surfaces remain thin.

## Evidence anchors

- `alpha_validation.path_montecarlo`
- `alpha_cli.monte_carlo_cmds`
- `alpha_cli.control_store.ControlStore.review_monte_carlo`
- `tests/unit/test_path_montecarlo.py`
- `tests/bias_guards/test_monte_carlo_causality.py`
- `tests/integration/test_monte_carlo_cli.py`
- [Efron's bootstrap](https://doi.org/10.1214/aos/1176344552)
- [Politis and Romano's stationary bootstrap](https://doi.org/10.1080/01621459.1994.10476870)
- [Hamilton's regime-switching model](https://doi.org/10.2307/1912559)
- [White's data-snooping test](https://doi.org/10.1111/1468-0262.00152)
- [Kronos paper](https://arxiv.org/abs/2508.02739) and
  [reference implementation](https://github.com/shiyu-coder/Kronos)
