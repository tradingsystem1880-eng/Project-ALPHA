# Design — Isolated Qlib worker for Workstation v3

**Status:** Approved for implementation  
**Date:** 2026-07-19  
**Authority:** `CLAUDE.md`, ADR-0011, ADR-0016

## Capability gap

ALPHA has deterministic rule strategies and Kronos forecasting but lacks a fold-refitted,
cross-sectional tabular ML workflow with IC analysis and model/feature diagnostics. Qlib supplies
that bounded capability. It does not replace ALPHA's PIT store, engine, gauntlet, artifacts, or
verdicts.

## Process boundary

Qlib lives under `workers/qlib/` with its own Python project and lockfile. It is not a root uv
workspace member. No root package, `alpha_web`, or `alpha_mcp` imports Qlib or deserializes its model
pickles.

ALPHA exports a verified immutable experiment bundle as JSON/Parquet. The worker writes only
validated JSON/Parquet outputs to a job-specific exchange directory. `alpha_cli` verifies the
contract and replays predictions through the canonical engine and validation path.

## Starter experiment

- daily cross-sectional equity/ETF universe explicitly frozen by the user;
- Alpha158-style feature recipe and LightGBM CPU model;
- next-session open-to-open label consistent with a close-`t` decision/open-`t+1` fill;
- fold-local fitting and normalization with purge/embargo;
- long-only top-quintile equal-weight replay with declared costs;
- minimum 20 symbols and 756 aligned sessions;
- current-membership universes carry a permanent survivorship warning.

The workload defaults to one Qlib or Kronos heavyweight job at a time on the target M4/16 GB host.

## Contract

Input records include snapshot hash, frozen universe, feature/label recipe, train/validation/test
folds, purge/embargo, seed, canonical config hash, and worker-lock hash.

Every prediction contains:

`symbol, origin_ts, available_at, target_ts, score, fold, split, model_hash, config_hash,
worker_lock_hash, seed`.

The importer rejects duplicate keys, non-finite scores, disorder, wrong snapshot/config/lock hashes,
late availability, target overlap, and any prediction outside its declared fold. Portable diagnostics
may cross the boundary; executable/pickle model objects may not.

## Authority and labeling

Qlib Recorder/backtest outputs are diagnostic. ALPHA metrics and validation remain authoritative.
Until a counterfactual null path causes complete fold-by-fold Qlib retraining, the result is labeled
`OOS replay validated — model not recomputed under counterfactual` and cannot claim full-engine ML
robustness.

The ML tear sheet includes IC/RankIC, score distribution, quantile returns, turnover, costed and
uncosted returns, benchmark/excess return, feature importance, fold boundaries, training history,
and complete provenance.

## Offline and release acceptance

- A deterministic fake worker covers CI without Qlib or network access.
- A separate worker gate checks its own lock, types, unit tests, and reproducibility.
- Root dependency/import tests prove Qlib never enters the ALPHA runtime graph.
- Future-poison tests cover feature construction, fold-local normalization, labels, and availability.
- Crash, heartbeat, cancellation, corrupt exchange bundle, and safe re-import are tested.
- Dependency/license governance records the pinned Qlib revision, transitive impact, notices, and
  removal path before enabling the real worker.

