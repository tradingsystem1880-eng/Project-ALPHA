# Phase 2d-ii — Frictions: fees + slippage (spec §7)

> **For agentic workers:** TDD per `CLAUDE.md`. Adds realistic, conservative costs to the backtest.

**Goal:** Model the two v1 frictions (spec §7: "per-asset-class fee + a volatility-scaled slippage assumption (conservative)"; "slippage is modeled on the t+1 open"):
- **Slippage** as a side-aware **bid/ask spread on the execution (t+1 open) quote** — a market buy fills at the ask (open + slippage), a sell at the bid (open − slippage). Modeled in `feed.to_execution_feed` via a `slippage_bps` half-spread (default 0 = frictionless, backward-compatible). A fixed bps is the conservative v1 choice; vol-scaling is a later refinement.
- **Fees** as a per-notional **bps commission** via a custom nautilus `FeeModel` (`commission = notional × fee_bps/10_000`), wired through `run_backtest(fee_bps=...)`.

**Validated mechanisms (probed):** a market BUY fills at the ask when bid<ask; a `FeeModel` subclass overriding `get_commission(order, fill_qty, fill_px, instrument)` charges the commission (100@100 × 10bps = $10), deducted from the account.

**Tech Stack:** Python 3.12 · nautilus_trader 1.228 · pytest. Offline. No new deps.

**Scope:** fee + slippage only. The faithful per-session mark-to-market equity curve is 2d-iii.

---

## File Map
```
packages/alpha-backtest/src/alpha_backtest/feed.py        # MODIFY: to_execution_feed slippage_bps (bid/ask spread)
packages/alpha-backtest/src/alpha_backtest/frictions.py   # CREATE: BpsFeeModel(FeeModel)
packages/alpha-backtest/src/alpha_backtest/engine.py      # MODIFY: run_backtest(fee_bps=...) -> fee_model
tests/integration/test_frictions.py                       # CREATE: slippage prices + fee reduces equity
```

## Tasks (TDD red → green)
- [ ] `to_execution_feed(..., slippage_bps=0.0)`: quote bid = open·(1−s), ask = open·(1+s); decision bar open unchanged.
- [ ] `frictions.BpsFeeModel(fee_bps)`: commission = notional × fee_bps/10_000 in the quote currency.
- [ ] `run_backtest(..., fee_bps=0.0)`: pass `BpsFeeModel(fee_bps)` to the venue when `fee_bps > 0`.
- [ ] **Tests:** a round-trip with slippage fills the buy above / the sell below the open (entry/exit prices, reduced PnL); a round-trip with a bps fee reduces `final_equity` by the commissions. Frictionless defaults leave existing tests unchanged.
- [ ] **Gate** green.

## Done = Phase 2d-ii complete
- Backtests can charge a per-notional fee and apply side-aware slippage on the t+1 open; both default off (frictionless), so prior tests are unaffected.

**Next:** Phase 2d-iii — faithful per-session mark-to-market equity curve (so returns reflect unrealized P&L each session). Then Phase 3 — the `alpha validate` gauntlet.
