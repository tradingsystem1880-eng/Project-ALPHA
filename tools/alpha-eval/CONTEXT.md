---
owner: agent evaluation tool
sources:
  - tools/alpha-eval/src/**
  - tools/alpha-eval/scenarios/**
  - tools/alpha-eval/pyproject.toml
verified: 00f70c232ea5
---

# alpha-eval workspace

## Purpose

A benchmark that scores AI agents on ALPHA research and engineering scenarios. It is a separate uv
project with its own lock; no root package imports it. Its scores and reports are advisory: they
never admit evidence, approve research or change the product.

## Read first

| Read | Section | When |
|---|---|---|
| [evaluation invariants](../../docs/reference/invariants/eval.md) | — | always |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Owner authority | always |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Protected and hidden tests | adding a scenario that touches tests |
| [what this part is for](../../docs/reference/project/components/delivery-and-agent-tooling.md) | — | why it exists; before you keep, shelve or remove it |

## How to change it

- Code: `tools/alpha-eval/src/alpha_eval/`; scenarios in `tools/alpha-eval/scenarios/`; tests in
  `tools/alpha-eval/tests/`. Past results under `tools/alpha-eval/results/` are records; do not edit.
- From `tools/alpha-eval`: `uv lock --check`, `uv sync --locked`, `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run mypy`, `uv run pytest -q -m "not network"`.
- Or CI's job from the repository root: `uv run python scripts/gate.py component eval`.

## Outputs

- Tests in `tools/alpha-eval/tests/`; a new dated folder under `results/` for a new run.
- The owning document: `docs/reference/invariants/eval.md`.
