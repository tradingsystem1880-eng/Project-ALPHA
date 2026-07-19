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
JSON/Parquet. `alpha_cli` validates the exchange bundle and replays signals through the canonical
engine and gauntlet. No ALPHA process imports Qlib or deserializes model pickles.

Qlib reports are advisory. Replay-only counterfactual evidence is permanently labeled until the ML
model is fully recomputed on each counterfactual path.

## Options considered

- Root dependency: rejected due to dependency, pandas-edge, and authority conflicts.
- Reimplement the full ML stack locally: rejected because Qlib supplies the named missing capability.
- Isolated worker: chosen for containment, reproducibility, and a clean removal path.

## Consequences

- Easier: optional installation, lock isolation, offline fake-worker CI, canonical ALPHA validation.
- Harder: exchange-contract validation and separate worker maintenance.
- Revisit: only after the dependency/license gate, deterministic worker acceptance, and a specific
  counterfactual retraining design.

