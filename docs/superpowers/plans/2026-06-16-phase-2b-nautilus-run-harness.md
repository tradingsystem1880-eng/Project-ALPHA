# Phase 2b — nautilus Run Harness + the t+1-Open Execution Convention

> **For agentic workers:** TDD per `CLAUDE.md`. This plan encodes a *spike finding*: nautilus's default bar execution fills market orders at the bar **close**, not the open of `t+1` the spec requires. The harness below makes nautilus honor "decide on close of `t`, fill at open of `t+1`."

**Goal:** A minimal `BacktestEngine` run harness that feeds `PointInTimeSource`-derived bars through nautilus and honors the spec's execution convention (§7, §13), proven by a fill-price bias guard.

**Spike finding (validated empirically):** With `bar_execution=True` a market order decided in `on_bar(t)` fills at bar `t`'s **close**; a latency model only shifts it to the next bar's close; market orders cannot rest before a price exists ("no market" rejection). The convention requires submitting the order when the `t+1` **open** price is the *current* market.

**Validated mechanism (the harness encodes this):**
1. Venue config **`bar_execution=False`** — bars drive strategy *decisions* only, never fills; fills come from quotes.
2. Per session, feed **two events**: an open-priced `QuoteTick` stamped at the session **open** (price = `bar.open`, deep size so the market order fills fully — slippage is modeled separately later), and the **decision `Bar`** (full OHLC) stamped at the session **close** (open + a fixed `<24h` offset, preserving `close(t) < open(t+1)`).
3. Strategy pattern: compute the target in `on_bar` (close of `t`); **submit the market order in `on_quote_tick`** (open of `t+1`). Fills at the open of `t+1`.

**Tech Stack:** Python 3.12 · nautilus_trader 1.228 (`bar_execution=False`) · pytest. Offline (no network). DAG: `alpha_backtest` → `alpha_core` + `alpha_data` (+ nautilus).

**Scope:** instrument helper (equity), the execution-feed builder, the run harness + a minimal `BacktestResult`, and the execution-convention bias guard. The TS-momentum strategy, fee/slippage `FillModel`, mixed-asset (crypto/FX) instruments, and the rich result schema (equity curve/trades) are later increments.

---

## File Map
```
packages/alpha-backtest/src/alpha_backtest/feed.py         # ADD: to_execution_feed (open quotes + close-stamped decision bars)
packages/alpha-backtest/src/alpha_backtest/instruments.py  # CREATE: equity_instrument (v1: wraps nautilus test provider)
packages/alpha-backtest/src/alpha_backtest/engine.py       # CREATE: BacktestResult + run_backtest (bar_execution=False)
tests/integration/test_nautilus_engine.py                  # CREATE: do-nothing run + t+1-open fill bias guard
```

## Tasks
- [ ] **feed.to_execution_feed(bars, bar_type, …)** → sorted `[QuoteTick(open)@session-open, Bar(OHLC)@session-close, …]`.
- [ ] **instruments.equity_instrument(symbol, venue="SIM")** → an `Equity` (v1 wraps `TestInstrumentProvider`; explicit per-asset-class defs are a later increment).
- [ ] **engine.run_backtest(instrument, data, strategy, …)** → builds the engine with **`bar_execution=False`**, NETTING/CASH venue, runs, returns `BacktestResult(orders, fills)`, disposes.
- [ ] **Test 1 (do-nothing):** a strategy that only counts bars → all bars seen, 0 orders, 0 fills.
- [ ] **Test 2 (bias guard — the headline):** a strategy that decides on the first bar's close and executes on the next open → **fill price == the open of `t+1`** (not bar `t`'s close), at the `t+1` timestamp. `@pytest.mark.bias_guard` (this is the causality/shift guarantee).
- [ ] **Gate:** ruff/format/mypy/lint-imports/pytest all green.

## Done = Phase 2b complete
- A run harness feeds PIT-safe bars through nautilus and a market order decided on the close of `t` provably fills at the **open of `t+1`** — the spec's execution convention, enforced and bias-guarded.

**Next:** Phase 2c — the TS-momentum strategy (decide-on-close / execute-on-open base) + vol-target sizing; then the fee/slippage `FillModel` and the standard result schema (equity curve + trade log).
