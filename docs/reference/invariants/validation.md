---
owner: validation statistics
sources:
  - packages/alpha-validation/src/**
  - apps/alpha-cli/src/alpha_cli/_gauntlet.py
  - tests/oracles/**
  - tests/unit/test_gauntlet*.py
  - tests/bias_guards/test_walkforward_no_leak.py
  - tests/bias_guards/test_montecarlo_null_calibration.py
  - tests/integration/test_gauntlet_degenerate.py
verified: aa600e57932d
---

# Validation statistics invariants

What must hold in `alpha_validation` (`packages/alpha-validation/src/alpha_validation/`): engine-agnostic
statistical primitives, the gauntlet gate semantics they feed, and the oracles that make them
wrong-detectable. Composition of the gauntlet run itself (`apps/alpha-cli/src/alpha_cli/_gauntlet.py`) is
covered with the CLI; the gate meanings are here.

## Package boundary

- Quant tier: changes here carry the obligations in [engineering § Quant tier](engineering.md#quant-tier).
- Import only `alpha_core` (numpy/scipy allowed) — import-linter contract `alpha_validation depends only on core`.
  Never import the engine, a strategy, an optimiser or a model; callers pass a `score`/`strategy_fn` callable.
- pandas and QuantStats-Lumi appear only in `tearsheet.py` — [engineering § Polars by default](engineering.md#polars-by-default).
- Fail loud on degenerate input with `DataError` — [research integrity § Invalid data fails loud](research-integrity.md#invalid-data-fails-loud).
  The documented exceptions return a typed "undefined" instead (below); never return NaN as a silent answer.
- Primitives take `seed: int | None`; `None` draws fresh entropy and is for interactive use only. Every
  composer passes a semantic, settings-derived seed, except the D0/D1 research protocols, whose seeds are
  frozen in code — [research integrity § Deterministic seeds and identity](research-integrity.md#deterministic-seeds-and-identity).

## Gauntlet gates

Gate outcomes are built by `build_outcomes` in `tearsheet.py` (called from `_gauntlet.py`) as
`alpha_core.ValidationOutcome`s. Overall `passed` is the AND of every gate.
[ADR-0006](../../adr/0006-two-tier-null-model.md).

- `walk_forward_oos` (gate 2): passes on a finite OOS Sharpe. Folds come from the session calendar; scored OOS
  evidence comes from one fresh-portfolio execution after causal priming, and rule parameters are not refit.
  Metrics, equity, decisions, orders, fills, trades, indicators and annotations are all scoped from that same
  execution (`alpha_cli/_runner.py`), so the numbers and the chart describe one state.
- `randomized_price_null` (gate 3, headline): the observed OOS Sharpe must reach the `threshold` percentile in
  every tier — Tier 1 `returns_level` (engine-free surrogate on resampled returns; `--null-model` picks
  bootstrap, student_t or garch; scored on the walk-forward OOS window), Tier 2 `full_engine` (real engine on
  block-bootstrapped, level-continuous synthetic OHLCV paths) and Tier 3 `bar_permutation` (real engine on
  bar-permuted OOS windows).
- The only rescue: a Tier-1 FAIL becomes advisory (`flagged_low_fidelity`, reported, not vetoing) when Tier 2
  passed and the measured close-fill vs next-open-fill `convention_divergence` exceeds `tier1_divergence_tol`
  (default 0.25). The flag is computed only for Tier 1 (`_tier1_summary`); a Tier-2 or Tier-3 FAIL is never
  rescued. Reason: the close-fill surrogate structurally over-credits high-turnover strategies
  ([investigation](../../records/investigations/2026-06-23-tier1-surrogate-crediting-bias.md)).
  Tests: `tests/unit/test_gauntlet_tier1.py`.
- `bootstrap_ci` (gate 4): passes when the Sharpe BCa lower bound is above 0; the interval is always reported.
- `deflated_sharpe`: PSR/DSR of the OOS stream; a single run has `n_trials = 1`, so DSR equals PSR. Passes
  when DSR is at least `dsr_threshold`.
- `cpcv_oos`: passes when the mean OOS Sharpe across CPCV folds of the OOS stream is above 0.
- A flat or zero-variance OOS short-circuits every gate to a clean FAIL, never an undefined-Sharpe crash
  (`tests/integration/test_gauntlet_degenerate.py`). A zero-variance bootstrap resample scores 0.0 through the one
  statistic `_gauntlet.safe_sharpe_statistic`; the portfolio and cross-sectional runs import it rather than copy it.
- Multi-trial statistics (DSR deflated by trial-Sharpe variance, PBO, Reality Check, SPA) judge a parameter
  sweep and belong to `alpha optim` (`_optim.py`), never the single-run gauntlet.

## Null models and permutation tests

- Null p-values use Davison and Hinkley's `(1 + c) / (1 + N)` with `c` = null draws at least as good — never 0.
  `percentile` is the fraction of null draws strictly below the observed value; a tier passes when it is at
  least `threshold`. One implementation: `montecarlo._rank_null`, shared by `mcpt`.
- `randomized_price_null` fails loud on `n_paths < 1`, a threshold outside (0, 1), fewer than two returns,
  non-finite returns, or a non-finite statistic on any path.
- The null must not certify structureless noise. Enforced distributionally over many noise series by
  `tests/bias_guards/test_montecarlo_null_calibration.py`, not by one chosen seed.
- `permute_bars` shuffles overnight log gaps and intrabar log shapes as two independent multisets after
  `start_index`; the prefix through `start_index` is copied unchanged and the final close is preserved.
  Several markets get the same two orders. A start index leaving nothing to permute fails loud.
- Tier 3 permutes every scored OOS bar (`start_index` = first test bar − 1), unlike upstream, which keeps the
  first OOS bar fixed.
- In-sample MCPT (re-optimise per permutation) is a selection-bias test only, never out-of-sample evidence.
- Ports from neurotrader888 cite `docs/governance/2026-09-12-neurotrader888-provenance.md`.

## Splits and resampling

General rule: [research integrity § Point-in-time reads](research-integrity.md#point-in-time-reads).

- `walk_forward_splits` is strictly causal: every train index precedes every test index, with `embargo`
  samples left empty before each test window. Equal-size folds; a short tail is dropped; a configuration with
  no fitting fold raises. Enforced by `tests/bias_guards/test_walkforward_no_leak.py`.
- CPCV tests every `C(N, k)` group combination and embargoes the training samples right after each test block.
  This one-sided buffer is the operative purge only because ALPHA's labels are daily and horizon-1.
- Splitters are index-only and engine-agnostic. Oracles: `tests/oracles/test_metamorphic_splits.py`.
- `block_bootstrap_ci` uses the Politis–Romano stationary bootstrap with BCa correction (leave-one-out
  jackknife acceleration, a documented approximation on dependent data). It fails loud when the BCa adjustment
  is unstable instead of returning an infinite percentile.

## Multi-trial selection statistics

- PSR and DSR work in per-observation Sharpe units; pass `trial_sharpes` in the same units. DSR deflates
  against the expected maximum Sharpe of `N` trials using the cross-trial variance.
- PBO via CSCV runs on a `(T × S)` performance matrix and is deterministic (no RNG).
- Reality Check and SPA judge the best of `S` strategies with stationary-bootstrap means.

## Path risk and scenarios

[ADR-0029](../../adr/0029-four-family-monte-carlo-validation.md).

- Path-risk Monte Carlo (`path_montecarlo.py`) simulates the observed OOS account-return process. It does not
  test a no-edge null and never establishes edge — reports say so.
- Families are graded independently; never majority-vote. Missing, invalid or non-estimable evidence fails.
  Purposes and reading of each family: the [four-family Monte Carlo guide](../../operations/monte-carlo/README.md).
- `iid_empirical` resamples OOS account returns independently, which removes serial dependence.
  `regime_switching` is a causal two-state (calm/volatile) empirical Markov bootstrap, not an HMM;
  independent per-asset paths say nothing about joint portfolio dependence.
- `student_t` fits log account returns and maps back with `expm1`; a finite simulated mean wealth does not
  show a finite population expected wealth (checklist EX14). It is distinct from the `student_t` null option.
- `kronos_synthetic` replays the unchanged strategy on generated tails; tests with `FakeForecaster` do not
  qualify real weights, calibration or pretraining overlap.
- Scenario and stress outputs (`scenario.py`) and the prop-firm simulation (`propfirm.py`) describe risk under
  what-if changes; they are not evidence of edge.

## Reports and verdicts

- `report_to_manifest` is byte-stable for identical runs: sorted keys, non-finite floats become `null`.
- `grade_verdict` is an A–F headline summary, not a gate. Thresholds are module constants; NaN inputs score F
  on that dimension. The Workstation mirrors the bands in `apps/alpha-web/frontend/src/explain/bands.ts`
  (drift-guarded) — change both together.
- The verdict's robustness count treats null tiers strictly (`_gauntlet.py` `_verdict_summary`): a demoted
  Tier-1 FAIL still lowers the grade even though the gate passes.
- `native_tearsheet.py` is the authority for report metrics and series; the browser renders them and never
  recomputes financial statistics.
- An undefined trade-runs statistic is `None` with a reason (`runs_test_undefined`, `no_closed_trades`), never NaN.
  In `runs_test`, zeros count in `n` and break a run without being positive or negative.
- `metrics.profit_factor` (gross profit over gross loss, `None` with no loss) is the one implementation: the
  native tear sheet uses it and MCPT `score` callables should too; never add a second one.
- Forecast-skill baselines (random-walk drift, stationary bootstrap) use the same context window as the forecast;
  calibration and blending are fold-local and frozen before OOS
  ([ADR-0028](../../adr/0028-governed-market-state-and-model-candidates.md)).

## Oracles and tolerances

- Every public statistical primitive must be wrong-detectable: a metamorphic relation, a known-truth
  calibration or a differential oracle in `tests/oracles/` (markers `oracle`, `slow_oracle`), with a
  primary-source citation in the docstring.
- Never compare floats with `==` in tests. Use the named tolerances in `tests/oracles/_reference/tolerances.py`;
  stochastic rates use the Bernoulli band (`bernoulli_band`, two-sided alpha 1e-4), not a hand-picked margin.
- Shared statistics are pinned across packages: `trade_dependence.runs_test` equals `alpha_patterns.runs.runs_z`
  (`tests/oracles/test_differential_runs_test.py`); DSR matches the Bailey–López de Prado reference
  (`tests/oracles/test_differential_bailey_ldp.py`).
- Known-truth calibrations (`slow_oracle`) use fixed seeds with analytic answers
  (`tests/oracles/test_calibration_known_truth.py`, `tests/oracles/test_calibration_mcpt.py`).
