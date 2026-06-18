# Phase 4i — CI hardening + docs (closes Phase 4)

> **For agentic workers:** independent hardening pass. Closes maturity-audit gaps and finalizes docs.

**Goal:** add the missing coverage gate, exercise Hypothesis, quiet benign async-teardown warnings,
and bring `CLAUDE.md` current — completing Phase 4.

## What landed

- **Coverage gate (closes the "no coverage measurement" audit gap).** `pytest-cov` added to the dev
  group; `[tool.coverage]` configures `source` (the 8 packages), `fail_under = 90`, `show_missing`,
  and `exclude_also` (TYPE_CHECKING / `__main__` / `NotImplementedError`). CI's test step now runs
  `--cov --cov-report=term-missing`. **Current coverage: 96.3%.**
- **Hypothesis property tests (closes the "Hypothesis unused" gap).**
  `tests/unit/test_paper_cost_properties.py`: `realized_slippage_bps` BUY/SELL sign-symmetry and
  zero-at-reference; `estimate_short_funding_cost` non-negativity and linearity in notional.
- **Quieted benign warnings.** `filterwarnings` ignores `PytestUnraisableExceptionWarning` — the
  "Event loop is closed" raised when nautilus live-node tasks are GC'd after a test loop closes
  (teardown noise, not a logic fault).
- **`CLAUDE.md` brought current:** DAG (7 contracts; `alpha_execution`/`alpha_paper`), module map
  (new `alpha_execution` + `alpha_paper` sections; `alpha_backtest` slimmed to feed+engine; fractional
  sizing; `order_log`), CLI surface (`alpha paper`), gate command (+coverage), "Where do I add X?",
  and the build status (Phase 4 ✅).

## Done = Phase 4 complete (4a–4i)
Crypto-first paper trading via the nautilus `SandboxExecutionClient`: a shared `alpha_execution`
layer, the `alpha_paper` subsystem, backtest↔sandbox **order-for-order parity** (equity + crypto),
slippage reconciliation, fractional sizing, risk controls (cap + kill-switch), the §13 funding
caveat, and the `alpha paper` CLI — all behind a 90% coverage gate. Gate green (ruff · format ·
lint-imports 7-kept · mypy --strict 127 files · 212 tests · coverage 96.3%).

**Next increment (post-PR):** a real-time `ccxt.pro` live data client — live paper trading proper,
beyond the historical replay dry-run.
