---
owner: domain core
sources:
  - packages/alpha-core/src/**
  - packages/alpha-core/pyproject.toml
verified: 1ac86fc02443
---

# alpha-core workspace

## Purpose

The bottom layer: frozen domain values (`Bar`, traces, outcomes), the typed error family, the
structural protocols, corporate-action types, the shared fee rate and the typed settings
(`AlphaSettings`, `ALPHA_*` environment variables). It imports nothing internal (import-linter
contract "alpha_core imports nothing internal") and every other package imports it, so a change
here reaches the whole repository.

## Read first

| Read | Section | When |
|---|---|---|
| [core invariants](../../docs/reference/invariants/core.md) | — | always |
| [engineering rules](../../docs/reference/invariants/engineering.md) | Import layers | always |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Invalid data fails loud | always |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Corporate actions: two clocks | changing corporate-action types |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Deterministic seeds and identity | changing settings or seeds |
| [engineering rules](../../docs/reference/invariants/engineering.md) | Hash-bound source bytes | any source edit (run ids fingerprint core bytes) |
| [what this part is for](../../docs/reference/project/components/command-line.md) | — | why it exists; before you keep, shelve or remove it |

## How to change it

- Code: `packages/alpha-core/src/alpha_core/` (`types.py`, `errors.py`, `protocols.py`, `config.py`,
  `corporate.py`, `costs.py`). The package has no tests of its own; they live in the root suite.
- Tests: `tests/unit/test_core_types.py`, `tests/unit/test_bar_invariants.py`,
  `tests/unit/test_corporate_actions.py`, `tests/unit/test_universe_store.py`,
  `tests/bias_guards/test_universe_survivorship.py`.
- Check: `uv run python scripts/gate.py check`. Because almost every test imports core, a change
  here maps to a large selection; run `uv run python scripts/gate.py check --all` for the fast tier.
- A new setting must never enter a run id or manifest if it is machine-local (see core invariants).

## Outputs

- A unit test for every new value rule or error, and a bias guard if a protocol's read semantics change.
- The owning document: `docs/reference/invariants/core.md`; update it and its `verified` commit
  when a rule changes.
