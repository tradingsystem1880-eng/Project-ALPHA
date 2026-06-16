# Phase 2c-ii — `TimeSeriesMomentum` nautilus Strategy (first end-to-end backtest)

> **For agentic workers:** TDD per `CLAUDE.md`. Wires the pure 2c-i functions into a nautilus
> `Strategy` on the decide-on-close / execute-on-open base (Phase 2b), run via `run_backtest`.

**Goal:** Connect everything built so far — PIT firewall → `to_execution_feed` → `run_backtest` → strategy — into the first runnable backtest. `TimeSeriesMomentum` computes the signal + vol-target size on the close of `t` and executes at the open of `t+1`.

**Strategy loop:**
- `on_start`: subscribe to the decision bars + the execution quotes.
- `on_bar` (close of `t`): append the close; every `rebalance_every` bars (monthly ≈ 21), once there is enough history, compute `ts_momentum_signal` + `vol_target_size` (using `realized_volatility` over `vol_window`) and store the **target units**.
- `on_quote_tick` (open of `t+1`): if a target is pending, submit a market order for `target − current` units (rounded to whole lots); fills at the open.
- `on_order_filled`: track realized `net_units` / `fills` (self-contained position state).

**Pre-registered v1 params (fixed):** `lookback=252`, `skip=21`, `vol_window=63`, `target_vol=0.15`, `max_leverage=1.0`, `rebalance_every=21`. Tests use small windows for short fixtures.

**Tech Stack:** Python 3.12 · nautilus_trader 1.228 (`alpha_strategies` now depends on nautilus) · pytest. Offline. DAG: `alpha_strategies` → `alpha_core` (+ nautilus); the backtest harness lives in `alpha_backtest` and is used by tests.

**Scope:** the strategy + an integration backtest proving direction (long in uptrend, short in downtrend) and that orders fill. The fee/slippage `FillModel` and the standard result schema (equity curve + trade log) are Phase 2d.

---

## File Map
```
packages/alpha-strategies/pyproject.toml                    # MODIFY: add nautilus-trader
packages/alpha-strategies/src/alpha_strategies/ts_momentum.py  # CREATE: TimeSeriesMomentum(Strategy)
tests/integration/test_ts_momentum_backtest.py              # CREATE: uptrend->long, downtrend->short
```

## Tasks (TDD red → green)
- [ ] **TimeSeriesMomentum** wiring signal+sizing on the decide-on-close / execute-on-open base.
- [ ] **Integration test:** an uptrend fixture → the strategy goes long (`net_units > 0`, `fills > 0`); a downtrend → short (`net_units < 0`). Run through `run_backtest`.
- [ ] **Gate** green.

## Done = Phase 2c-ii complete
- The full v1 loop runs end-to-end: PIT-safe bars feed nautilus, `TimeSeriesMomentum` decides on the close and fills at the next open, taking signal-consistent positions.

**Next:** Phase 2d — fee/slippage `FillModel` + the standard result schema (equity curve + trade log), turning `BacktestResult` into a validatable output; then the `alpha validate` gauntlet (Phase 3).
