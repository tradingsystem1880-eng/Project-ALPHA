# Project ALPHA — Build Conventions

Personal, $0/free, Python quant research platform. Spec: `docs/superpowers/specs/2026-06-14-project-alpha-v1-design.md`. Research: `research/00-SYNTHESIS.md`.

## Architecture (enforced by import-linter — never violate)
Dependency DAG: `alpha_core` ← `alpha_data` ← `alpha_backtest`; `alpha_strategies`, `alpha_validation` ← `alpha_core`; `alpha_cli` ← everything. `alpha_core` imports nothing internal.

## Golden rules
- **TDD.** Failing test → minimal code → green → commit. Small commits.
- **No look-ahead, ever.** Strategies read data only via the point-in-time accessor (`as_of`). Every data/strategy unit gets a `@pytest.mark.bias_guard` future-poison test.
- **Execution convention:** decide on close of bar `t`, fill at open of `t+1`.
- **No empty `except`.** Log with context or re-raise. Fail loud on data gaps / NaN / disorder.
- **Polars** is the default dataframe; pandas only at library edges.
- Strong typing everywhere; `mypy --strict` is a CI gate.

## Commands
- Install: `uv sync`
- Test: `uv run pytest -q` · bias guards only: `uv run pytest -m bias_guard -q`
- Lint/format/types/arch: `uv run ruff check . && uv run ruff format --check . && uv run mypy packages apps tests && uv run lint-imports`
- CLI: `uv run alpha info`
