---
owner: literature worker
sources:
  - workers/literature/src/**
  - workers/literature/pyproject.toml
  - workers/literature/uv.lock
verified: 1724a5befe5d
---

# Literature worker workspace

## Purpose

An isolated process that discovers, fetches and extracts research literature for research cases
and returns bounded, validated claims. It is a separate uv project with its own lock; no root
package imports it. The CLI starts it with a minimal environment, no inherited credentials and
resource limits; its output is advisory evidence, never research authority.
[ADR-0024](../../docs/adr/0024-literature-acquisition-worker-and-claim-model.md)

## Read first

| Read | Section | When |
|---|---|---|
| [worker invariants](../../docs/reference/invariants/workers.md) | Shared rules | always |
| [worker invariants](../../docs/reference/invariants/workers.md) | Literature worker | always |
| [command line research](../../docs/reference/invariants/cli-research.md) | Process boundaries | changing how the CLI starts the worker |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Owner authority | changing what a claim can be used for |

## How to change it

- Code: `workers/literature/src/literature_worker/`; tests: `workers/literature/tests/`
  (add a new unit test there, named `test_<module>.py`). The launch boundary is tested from the
  root in `tests/integration/test_research_cli.py`.
- From `workers/literature`: `uv lock --check`, `uv sync --locked`, `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run mypy`, `uv run pytest -q -m "not network"`.
- Or CI's job from the repository root: `uv run python scripts/gate.py component literature`.
- Tests that touch the network carry the `network` marker and never run in CI.

## Outputs

- Tests in `workers/literature/tests/`.
- The owning document: `docs/reference/invariants/workers.md` § Literature worker.
