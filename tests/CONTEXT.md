---
owner: root test suite
sources:
  - tests/_tiers.py
  - tests/conftest.py
  - tests/bias_guards/test_future_poison_pattern.py
  - tests/oracles/_reference/**
verified: 70f15b4e80c4
---

# tests workspace

## Purpose

The root test suite for every package and app: unit, integration, bias guards (look-ahead
detectors), oracles (statistical correctness checks), fixtures and visible acceptance tests. The
isolated workers and `tools/alpha-eval` keep their own suites. Tests must never read the guarded
`tests/holdout/` path, and guards and oracles must never be weakened to make a change pass.

## Read first

| Read | Section | When |
|---|---|---|
| [testing invariants](../docs/reference/invariants/testing.md) | Test layers | always |
| [testing invariants](../docs/reference/invariants/testing.md) | Markers and tiers | always |
| [research integrity](../docs/reference/invariants/research-integrity.md) | Protected and hidden tests | always |
| [testing invariants](../docs/reference/invariants/testing.md) | Bias guards | adding or changing a bias guard |
| [testing invariants](../docs/reference/invariants/testing.md) | Oracles | adding or changing an oracle |
| [checks](../docs/reference/checks.md) | — | adding a marker or moving tests between CI tiers |
| [testing invariants](../docs/reference/invariants/testing.md) | Owned test processes | a test spawns processes that may outlive it |
| [research integrity](../docs/reference/invariants/research-integrity.md) | Statistical evidence | writing tolerances for statistics |
| [what this part is for](../docs/reference/project/components/delivery-and-agent-tooling.md) | — | why it exists; before you keep, shelve or remove it |

## How to change it

- Layout: `tests/unit/` (pure units; `tests/unit/study/` for alpha-study), `tests/integration/`
  (CLI and engine), `tests/bias_guards/`, `tests/oracles/` (tolerances in `_reference/`),
  `tests/fixtures/` (goldens), `tests/acceptance/` (17 visible acceptance tests, always run), `tests/smoke/` (end-to-end
  workflows through the installed programs; marker `smoke`, not in the fast tier; crypto downloads go through
  the offline recorded provider `tests/smoke/_recorded_provider.py`, a loopback TLS proxy).
- A new file's name decides its tier: `tests/_tiers.py` moves files with listed prefixes out of
  the fast local tier. Never add the `platform` marker by hand.
- Run one file: `uv run pytest -q tests/unit/test_x.py`; the fast check:
  `uv run python scripts/gate.py check`; the fast tier: `uv run python scripts/gate.py check --all`;
  bias guards: `uv run pytest -q -m bias_guard`; smoke:
  `uv run python scripts/run_owned_test.py --timeout 900 -- uv run pytest -q -m smoke -n 0`.
- Protected (reviewed pull request only): `tests/bias_guards/`, `tests/oracles/`,
  `tests/unit/test_claude_harness_*.py`, `tests/_tiers.py`, `tests/acceptance/`.

## Outputs

- The test itself, in the layer its subject belongs to, named after the module it tests (test
  selection maps tests by the names they import).
- The owning document: `docs/reference/invariants/testing.md`.
