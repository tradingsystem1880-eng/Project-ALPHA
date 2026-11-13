# Design — Isolated Qlib worker for Workstation v3

**Status:** Implemented; offline release gate passed
**Date:** 2026-07-19
**Implementation reviewed:** 2026-07-19
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
contract and synchronously replays predictions across the frozen universe through the canonical
multi-asset engine path.

## Starter experiment

- daily cross-sectional equity/ETF universe explicitly frozen by the user;
- Alpha158-style feature recipe and LightGBM CPU model;
- next-session open-to-open label consistent with a close-`t` decision/open-`t+1` fill;
- fold-local fitting and normalization with at least one full session of purge and embargo;
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

Daily panel OHLCV and predictions are available at the canonical decision close
(`session_ts + 23h`), not at session midnight. `origin_ts` names the session, `available_at` names
the close when the full daily bar can be known, and `target_ts` names the following execution/label
session. The open-to-open label also needs the aligned open after `target_ts`; therefore the
terminal aligned session is never an eligible target. Request generation and both root/worker
validators enforce a minimum one-session purge and embargo even if a caller supplies zero, so the
one-session label horizon cannot cross a train/validation or validation/test boundary.

The importer rejects duplicate keys, non-finite scores, disorder, wrong snapshot/config/lock hashes,
late availability, target overlap, and any prediction outside its declared fold. Portable diagnostics
may cross the boundary; executable/pickle model objects may not.

## Authority and labeling

Qlib Recorder/backtest outputs are diagnostic. The synchronized, costed ALPHA replay metrics and
causal execution artifacts are authoritative for that replay.
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
- Crash, independent heartbeat, true in-flight cancellation/reap, corrupt exchange bundle, and safe
  re-import are tested.
- Dependency/license governance records the pinned Qlib revision, transitive impact, notices, and
  removal path before enabling the real worker.

## Current implementation note — 2026-07-19

The root boundary is implemented in `alpha_cli.ml_input`, `alpha_cli.ml_contract`,
`alpha_cli.ml_cmds`, and `alpha_cli._ml_replay`; the synchronized target-weight execution lives in
`alpha_backtest.portfolio_replay`. The independent worker validates the same exchange contract in
`workers/qlib/src/alpha_qlib_worker/contract.py` and performs fold-local preprocessing/training in
`real.py`. Model objects and Qlib Recorder state remain worker-local and are removed with the
ephemeral training directory. The real worker builds each open-to-open label only when the target
session has a following aligned open and excludes the terminal target. Root and worker contracts
both reject sub-one-session purge/embargo gaps.

Direct Workstation ML training runs under the shared durable heavyweight journal. Its isolated
process group has a five-second stdout-independent heartbeat/cancellation lease; an audited cancel
request terminates and reaps the worker tree, records `cancelled`, releases the capacity slot, and
cannot later be overwritten by another terminal state. Heartbeat or cancellation-poll failure
fails the journal instead of allowing an unleased worker to report success.

Primary checks live in `tests/unit/test_qlib_isolation.py`, `tests/unit/test_ml_contract.py`,
`tests/unit/test_ml_boundary_guards.py`, `tests/unit/test_ml_input.py`,
`tests/unit/test_portfolio_replay_engine.py`, `tests/bias_guards/test_ml_replay_future_poison.py`,
`tests/integration/test_ml_cli.py`, `workers/qlib/tests/test_fake_worker.py`, and
`workers/qlib/tests/test_real_worker.py`. Durable ML cancellation is covered by
`tests/unit/test_web_ml.py` and `tests/integration/test_web_api_job_cancellation.py`. The isolated
locked worker and root release gates passed, with exact evidence in the audit closeout.
Counterfactual fold-by-fold retraining remains intentionally deferred.
