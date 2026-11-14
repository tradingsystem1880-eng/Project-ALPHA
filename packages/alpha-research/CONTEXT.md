---
owner: research primitives
sources:
  - packages/alpha-research/src/**
  - packages/alpha-research/pyproject.toml
verified: 330acecce016
---

# alpha-research workspace

## Purpose

Pure, deterministic research primitives: research bars and datasets, the group-atomic split of
history into D0/D1/D2/D3 phases (synthetic pilot, discovery, one-shot confirmation, final holdout),
causal event studies, power and multiplicity control, lineage-bound figures and gate packets. It
imports only `alpha_core` (import-linter contract "alpha_research depends only on core") and has no
network, persistence or authority; `alpha_cli` and `alpha_study` use it.

## Read first

| Read | Section | When |
|---|---|---|
| [research invariants](../../docs/reference/invariants/research.md) | Package boundary | always |
| [engineering rules](../../docs/reference/invariants/engineering.md) | Hash-bound source bytes | always |
| [engineering rules](../../docs/reference/invariants/engineering.md) | Quant tier | always |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Research before strategy | always |
| [research invariants](../../docs/reference/invariants/research.md) | Gate packets | changing gate packet values |
| [research invariants](../../docs/reference/invariants/research.md) | Phase allocation | changing D0/D1/D2/D3 boundaries |
| [research invariants](../../docs/reference/invariants/research.md) | — | changing event studies, confirmation, bars or figures |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Point-in-time reads | changing event studies, bars or phase boundaries |
| [command line research](../../docs/reference/invariants/cli-research.md) | Projections and dossiers | a gate packet is assembled or shown differently |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Statistical evidence | changing a statistic |
| [what this part is for](../../docs/reference/project/components/research-cases-and-approval.md) | — | why it exists; before you keep, shelve or remove it |

## How to change it

- Stop first: every `.py` byte here feeds the research implementation hash checked against
  owner-approved contracts. Even a comment edit invalidates approvals. Make no cosmetic edits;
  say in the pull request when approvals will need renewing.
- Code: `packages/alpha-research/src/alpha_research/` (for example `topology.py` and `boundary.py`
  for phase allocation, `event_study.py`, `gate_packet.py`, `confirmation.py`, `figures/`). The CLI
  assembles packets in `apps/alpha-cli/src/alpha_cli/research_gate_packet.py` and `research_readiness.py`
  (outside the implementation hash, but the dossier summary shape is hash-pinned: see cli-research).
- Tests: `tests/unit/test_research_*.py` (many also cover the CLI side), `tests/unit/test_figure_*.py`;
  bias guards `tests/bias_guards/test_research_*.py`; oracles `tests/oracles/test_metamorphic_panel.py`,
  `test_research_diagnostic.py`; integration `tests/integration/test_research_runtime.py`.
- Check: `uv run python scripts/gate.py check`; CI adds slow oracles and the mutation gate here.
- A visible figure change needs a `RENDERER_VERSION` bump (see research invariants).

## Outputs

- Tests: an oracle for every new statistic; a future-poison guard for every new read of time.
- The owning document: `docs/reference/invariants/research.md`.
