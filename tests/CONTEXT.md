---
owner: root test suite
sources:
  - tests/_tiers.py
  - tests/conftest.py
  - tests/bias_guards/test_future_poison_pattern.py
  - tests/oracles/_reference/**
verified: 1ac86fc02443
---

# tests workspace

## Purpose

The root test suite for every package and app: unit, integration, bias guards (look-ahead
detectors), oracles (statistical correctness checks), fixtures and staged acceptance tests. The
isolated workers and `tools/alpha-eval` keep their own suites. Tests must never read the hidden
`tests/holdout/` path, and guards and oracles must never be weakened to make a change pass.

## Read first

| Read | Section | When |
|---|---|---|
| [testing invariants](../docs/reference/invariants/testing.md) | Test layers | always |
| [testing invariants](../docs/reference/invariants/testing.md) | Markers and tiers | always |
| [research integrity](../docs/reference/invariants/research-integrity.md) | Protected and hidden tests | always |
| [testing invariants](../docs/reference/invariants/testing.md) | Bias guards | adding or changing a bias guard |
| [testing invariants](../docs/reference/invariants/testing.md) | Oracles | adding or changing an oracle |
| [testing invariants](../docs/reference/invariants/testing.md) | Owned test processes | a test spawns processes that may outlive it |
| [research integrity](../docs/reference/invariants/research-integrity.md) | Statistical evidence | writing tolerances for statistics |

## How to change it

- Layout: `tests/unit/` (pure units; `tests/unit/study/` for alpha-study), `tests/integration/`
  (CLI and engine), `tests/bias_guards/`, `tests/oracles/` (tolerances in `_reference/`),
  `tests/fixtures/` (goldens), `tests/holdout_seed/` (staged acceptance proposals).
- A new file's name decides its tier: `tests/_tiers.py` moves files with listed prefixes out of
  the fast local tier. Never add the `platform` marker by hand.
- Run one file: `uv run pytest -q tests/unit/test_x.py`; the fast check:
  `uv run python scripts/gate.py check`; the fast tier: `uv run python scripts/gate.py check --all`;
  bias guards: `uv run pytest -q -m bias_guard`.
- Protected (reviewed pull request only): `tests/bias_guards/`, `tests/oracles/`,
  `tests/unit/test_claude_harness_*.py`, `tests/_tiers.py`, `tests/holdout_seed/`.

## Outputs

- The test itself, in the layer its subject belongs to, named after the module it tests (test
  selection maps tests by the names they import).
- The owning document: `docs/reference/invariants/testing.md`.
