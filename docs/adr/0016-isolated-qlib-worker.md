# ADR-0016: Isolate Qlib behind immutable JSON/Parquet exchange contracts

**Status:** Accepted
**Date:** 2026-07-19
**Deciders:** Owner-approved Workstation v3 plan and AI build agents

## Context

Qlib fills a real cross-sectional ML workflow gap, but its broad pandas/model dependency graph and
optional NumPy constraints do not belong in ALPHA's root Python 3.12/NumPy 2.4 environment. Its
backtest and experiment recorder also must not become a second source of research truth.

## Decision

Qlib runs as a separately locked worker outside the root uv workspace. ALPHA exports verified
immutable snapshot/fold/config bundles; the worker returns timestamped OOS prediction and diagnostic
JSON/Parquet. Daily observations and predictions are available only at the canonical close
(`session_ts + 23h`). `alpha_cli` validates the exchange bundle and performs a synchronized,
costed, multi-asset replay across the frozen universe through ALPHA's canonical engine. No ALPHA
process imports Qlib or deserializes model pickles.

Qlib reports are advisory; the ALPHA engine's metrics and causal artifacts are authoritative for
the replay it performs. The replay is not a full counterfactual gauntlet. Counterfactual evidence is
permanently labeled until the ML model is fully recomputed fold-by-fold on each path.

## Implementation anchors

- `apps/alpha-cli/src/alpha_cli/ml_input.py` and `ml_contract.py` build and validate the immutable,
  close-stamped exchange.
- `workers/qlib/src/alpha_qlib_worker/contract.py` independently validates the same boundary;
  `real.py` owns fold-local preprocessing and Qlib/LightGBM training.
- `packages/alpha-backtest/src/alpha_backtest/portfolio_replay.py:run_weight_replay` and
  `apps/alpha-cli/src/alpha_cli/_ml_replay.py:run_ml_replay` own canonical synchronized execution,
  reconciliation, metrics, and v3 artifacts.
- Regression evidence: `tests/unit/test_qlib_isolation.py`, `tests/unit/test_ml_contract.py`,
  `tests/unit/test_ml_boundary_guards.py`, `tests/unit/test_portfolio_replay_engine.py`,
  `tests/bias_guards/test_ml_replay_future_poison.py`, `tests/integration/test_ml_cli.py`, and
  `workers/qlib/tests/test_fake_worker.py`.

## Options considered

- Root dependency: rejected due to dependency, pandas-edge, and authority conflicts.
- Reimplement the full ML stack locally: rejected because Qlib supplies the named missing capability.
- Isolated worker: chosen for containment, reproducibility, and a clean removal path.

## Consequences

- Easier: optional installation, lock isolation, offline fake-worker CI, canonical ALPHA validation.
- Harder: exchange-contract validation and separate worker maintenance.
- Revisit: only after the dependency/license gate, deterministic worker acceptance, and a specific
  counterfactual retraining design.
