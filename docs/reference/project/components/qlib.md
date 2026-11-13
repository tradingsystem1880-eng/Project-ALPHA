---
owner: project layer
sources:
  - workers/qlib/CONTEXT.md
  - workers/qlib/README.md
  - docs/adr/0016-isolated-qlib-worker.md
  - docs/roadmap/capabilities.toml
verified: f89aa1bb78af
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
- The decision record is [ADR-0016](../../../adr/0016-isolated-qlib-worker.md).

## What is real today

See the capabilities below on [STATUS.md](../../../../STATUS.md). The worker is tested with a
stand-in on the Dell, where its install is not present.

## Where it lives

- **Workspaces:** `workers/qlib`
- **Capabilities:** `ml-lab`, `alpha158-v2`, `qlib-refit`, `qlib-in-research-cases`, `native-engine-demos`
- Code: [`workers/qlib/`](../../../../workers/qlib/README.md); the exchange and replay in
  `apps/alpha-cli/src/alpha_cli/` (`ml_*.py`, `_ml_replay.py`).
- Tests: `workers/qlib/tests/`, `tests/unit/test_qlib_isolation.py`, `tests/unit/test_ml_contract.py`.
- How to change it: [workers/qlib/CONTEXT.md](../../../../workers/qlib/CONTEXT.md).
- Plans: the `plans` of each capability above in `docs/roadmap/capabilities.toml`.
- Backlog: [full model zoo and fold retraining](../../../roadmap/backlog/qlib-model-zoo-and-fold-retraining.md).
- Decision records: [ADR-0016](../../../adr/0016-isolated-qlib-worker.md),
  [ADR-0028](../../../adr/0028-governed-market-state-and-model-candidates.md).

## Decisions and open questions

- Triage cards 10 (refit evidence, recommended SHELVE), 11 (corrected features, KEEP), A (groundwork
  for RD-Agent driving Qlib, recommended DELETE) and F (Qlib-to-Nautilus demo, recommended SHELVE)
  await the owner ([triage sheet](../../../roadmap/triage-2026-11.md)).
- Owner to confirm: are Qlib and Nautilus core engines like RD-Agent, so that their parts are
  finished rather than shelved? Cards 10, A and F were recommended before the 2026-11-14 decision.
- Owner to confirm: card A recommends deleting the groundwork for RD-Agent driving Qlib, yet that
  is item 6 of [RD-Agent's next steps](../../../roadmap/rd-agent-in-alpha.md#what-stands-between-today-and-rd-agent-researching-real-ideas).
  Keep it for that?

## Never

- Never make Qlib a dependency of the main ALPHA install, and never copy its repository into ALPHA.
- Never treat Qlib's own reports as the result; ALPHA's replay is.
- The worker rules: [Qlib worker](../../invariants/workers.md#qlib-worker) and
  [models and isolated workers](../../invariants/research-integrity.md#models-and-isolated-workers).
