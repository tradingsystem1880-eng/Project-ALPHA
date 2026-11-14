---
owner: project layer
sources:
  - workers/qlib/CONTEXT.md
  - workers/qlib/README.md
  - docs/adr/0016-isolated-qlib-worker.md
verified: 00c406280779
---

# Qlib

Qlib is Microsoft's open-source machine-learning toolkit for stock prediction. ALPHA runs the
real `pyqlib` package, at a fixed version, in its own worker program to train models that rank
stocks from past prices.

## Why it exists

ALPHA needs machine-learning models as one kind of experiment, and Qlib already provides them
with standard recipes (such as the Alpha158 price features and LightGBM). The owner: ALPHA "was
set up to install and call the real Qlib package rather than copy the whole repository"
([owner decisions](../owner-decisions.md#2026-11-14-install-and-call-real-qlib)).

## Its job in the research loop

Step 4 of the [research loop](../overview.md#the-research-loop): when an experiment is a
machine-learning model, Qlib trains it fold by fold and returns predictions. ALPHA then replays
those predictions through [Nautilus](nautilus.md) with costs; that replay, not Qlib's own report,
is the result. The intended next step is for [RD-Agent](rd-agent.md) to drive Qlib experiments.

## Intended design

- Qlib, LightGBM and their many dependencies live only in the worker's own install; nothing in
  ALPHA imports Qlib or loads its saved models.
- ALPHA sends frozen data and fold settings as plain files; the worker returns predictions stamped
  at the close of each day. Both sides check the exchange.
- Use Qlib's own recipes, providers and model zoo for breadth rather than rewriting them; any local
  copy (for example of the Alpha158 formulas) must be compared value by value before it is retired.
  Feature recipe v3 computes the features with upstream Qlib itself; it is opt-in, and making it
  the default is an owner decision ([ADR-0042](../../../adr/0042-qlib-worker-delegates-data-layer-to-upstream.md)).
- The founding decision record is [ADR-0016](../../../adr/0016-isolated-qlib-worker.md).

## What is real today

See the capabilities below on [STATUS.md](../../../../STATUS.md). The worker is tested with a
stand-in on the Dell, where its install is not present.

## Where it lives

- **Workspaces:** `workers/qlib`
- **Capabilities:** `ml-lab`, `alpha158-v2`, `alpha158-v3`, `qlib-refit`, `qlib-in-research-cases`,
  `native-engine-demos`
- Code: [`workers/qlib/`](../../../../workers/qlib/README.md); the exchange and replay in
  `apps/alpha-cli/src/alpha_cli/` (`ml_*.py`, `_ml_replay.py`).
- Tests: `workers/qlib/tests/`, `tests/unit/test_qlib_isolation.py`, `tests/unit/test_ml_contract.py`.
- How to change it: [workers/qlib/CONTEXT.md](../../../../workers/qlib/CONTEXT.md).
- Plans: the `plans` of each capability above in `docs/roadmap/capabilities.toml`.
- Backlog: [full model zoo and fold retraining](../../../roadmap/backlog/qlib-model-zoo-and-fold-retraining.md).
- Decision records: [ADR-0016](../../../adr/0016-isolated-qlib-worker.md),
  [ADR-0042](../../../adr/0042-qlib-worker-delegates-data-layer-to-upstream.md),
  [ADR-0028](../../../adr/0028-governed-market-state-and-model-candidates.md).

## Decisions and open questions

- Triage, 2026-11-14 under the owner's delegation
  ([triage sheet](../../../roadmap/triage-2026-11.md)): card 11 KEEP; cards 10, A and F SHELVE, code kept
  and labelled.
- Decided: Qlib and Nautilus are engines ALPHA installs and calls, like RD-Agent; their unfinished
  parts are kept or shelved, not deleted. Not every experiment needs Qlib
  ([log](../owner-decisions.md#2026-11-14-the-architecture-in-one-line)).
- Decided: the groundwork for RD-Agent driving Qlib is kept, shelved until it is wired in
  ([log](../owner-decisions.md#2026-11-14-agents-merge-and-decide-routine-matters)).


## Never

- Never make Qlib a dependency of the main ALPHA install, and never copy its repository into ALPHA.
- Never treat Qlib's own reports as the result; ALPHA's replay is.
- The worker rules: [Qlib worker](../../invariants/workers.md#qlib-worker) and
  [models and isolated workers](../../invariants/research-integrity.md#models-and-isolated-workers).
