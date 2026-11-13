---
owner: study projections
sources:
  - packages/alpha-study/src/**
  - packages/alpha-study/pyproject.toml
verified: 0377681b
---

# alpha-study workspace

## Purpose

An additive research-plane seam: strict immutable feature, event and factor contracts, one closed
operator registry, and derived finding and workspace projections that reference existing
research records exactly. It may import `alpha_core`, `alpha_data`, `alpha_patterns` and
`alpha_research` (import-linter contract "alpha_study composes only research-plane primitives").
It owns no persistence, commands, approvals, evidence or trading authority.
[ADR-0035](../../docs/adr/0035-generic-study-composition-and-external-capability-adapters.md)

## Read first

| Read | Section | When |
|---|---|---|
| [study invariants](../../docs/reference/invariants/study.md) | — | always |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Owner authority | always |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Point-in-time reads | always |
| [research invariants](../../docs/reference/invariants/research.md) | Phase allocation | the change touches D0 or D1 references |
| [command line research](../../docs/reference/invariants/cli-research.md) | Projections and dossiers | the change surfaces through `alpha research` |

## How to change it

- Code: `packages/alpha-study/src/alpha_study/`.
- Tests: `tests/unit/study/` (its own folder), `tests/unit/test_study_*.py`; bias guards
  `tests/bias_guards/test_study_double_bottom_future_poison.py`,
  `tests/bias_guards/test_verified_semantic_read_future_poison.py`.
- Check: `uv run python scripts/gate.py check`; `uv run lint-imports` keeps the seam one-way.

## Outputs

- Tests: a round-trip determinism test for every new contract and a future-poison guard for any
  projection that reads time.
- The owning document: `docs/reference/invariants/study.md`.
