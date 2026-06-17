# Phase 2d-i — Standard Result Schema (trade log + equity curve)

> **For agentic workers:** TDD per `CLAUDE.md`. Turns `run_backtest`'s output from bare counts into
> the validatable result the Phase-3 gauntlet consumes (spec §11 success criterion).

**Goal:** Extract a typed result schema from the nautilus engine — the **closed-trade log** and the **account-equity curve** — so a backtest produces "a trade log + equity curve" (spec §11), the input the validation gauntlet needs.

**Design:** A new `alpha_backtest.results` module holds frozen dataclasses `Trade` and `BacktestResult`. `run_backtest` extracts them from the engine before disposal:
- **trades** ← `engine.cache.positions_closed()` (typed `Position` objects: `entry`, `peak_qty`, `avg_px_open/close`, `realized_pnl.as_double()`, `realized_return`, `ts_opened/closed`).
- **equity_curve** ← `engine.trader.generate_account_report(venue)` `total` column over time, as `(datetime, equity)`.
- `starting_equity` / `final_equity` convenience properties.

**Known limitation (documented; refined in 2d-ii):** for a CASH account the equity curve tracks realized cash (an open position is not marked to market); a MARGIN account marks-to-market. Frictions (fees/slippage `FillModel`) and a faithful per-session MtM curve come in 2d-ii.

**Tech Stack:** Python 3.12 · nautilus_trader 1.228 · pytest. Offline. No new deps.

**Scope:** the result schema + extraction only. No fees/slippage yet (kept out so PnL assertions stay exact).

---

## File Map
```
packages/alpha-backtest/src/alpha_backtest/results.py   # CREATE: Trade + BacktestResult
packages/alpha-backtest/src/alpha_backtest/engine.py    # MODIFY: extract trades + equity curve
tests/integration/test_backtest_result.py               # CREATE: round-trip -> 1 closed trade, PnL, equity
```

## Tasks (TDD red → green)
- [ ] `results.Trade` + `results.BacktestResult` (counts, trades, equity_curve, starting/final equity).
- [ ] `engine.run_backtest` populates trades + equity_curve from the cache/report.
- [ ] **Test:** a round-trip (buy then sell) yields one closed `Trade` (entry/exit px, qty, `realized_pnl`, `realized_return`) and an equity curve whose `final_equity` reflects the realized PnL.
- [ ] **Gate** green (existing do-nothing / momentum tests still pass — they read counts / strategy state).

## Done = Phase 2d-i complete
- A backtest emits a typed trade log + equity curve — the spec's success-criterion output and the gauntlet's input.

**Next:** Phase 2d-ii — fee/slippage `FillModel` (per-asset-class fee + vol-scaled slippage on the t+1 open) + a faithful per-session mark-to-market equity curve. Then Phase 3 — the `alpha validate` gauntlet.
