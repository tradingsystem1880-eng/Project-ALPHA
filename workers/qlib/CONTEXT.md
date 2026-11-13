---
owner: qlib worker
sources:
  - workers/qlib/src/**
  - workers/qlib/pyproject.toml
  - workers/qlib/uv.lock
verified: 0377681b
---

# Qlib worker workspace

## Purpose

An isolated process that runs the real `pyqlib` package for daily cross-sectional model training
and returns close-stamped out-of-sample predictions. It is a separate uv project with its own lock;
no root package imports it, and it imports no ALPHA package. It exchanges only validated JSON and
Parquet with `alpha_cli`, and its results are advisory: ALPHA's own replay is the authority.
[ADR-0016](../../docs/adr/0016-isolated-qlib-worker.md)

## Read first

| Read | Section | When |
|---|---|---|
| [worker invariants](../../docs/reference/invariants/workers.md) | Shared rules | always |
| [worker invariants](../../docs/reference/invariants/workers.md) | Qlib worker | always |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Models and isolated workers | always |
| [command line machine learning](../../docs/reference/invariants/cli-ml.md) | Exchange contract | changing what the worker reads or writes |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Point-in-time reads | changing features or fold boundaries |

## How to change it

- Code: `workers/qlib/src/alpha_qlib_worker/`; tests: `workers/qlib/tests/`. Root tests that cover
  the boundary: `tests/unit/test_qlib_isolation.py`, `tests/unit/test_ml_*.py`.
- The worker has its own environment. From `workers/qlib`: `uv lock --check`, `uv sync --locked`,
  `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`,
  `uv run pytest -q -m "not network"`.
- Or run CI's job from the repository root: `uv run python scripts/gate.py component qlib`.
- A change to the exchange schema also needs the root check (`uv run python scripts/gate.py check`)
  for the CLI side.

## Outputs

- Tests in `workers/qlib/tests/`; a root future-leakage test when exchange validation changes.
- The owning document: `docs/reference/invariants/workers.md` § Qlib worker.
