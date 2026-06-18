# Phase 4e — Strategy parity + reconciliation (HEADLINE)

> **For agentic workers:** the payoff phase — prove paper == backtest. TDD per `CLAUDE.md`.

**Goal:** the *same* `TimeSeriesMomentum` class, fed the *same* bars, emits the *same* order sequence
through the sandbox as through the backtest engine; and realized sandbox-fill slippage reconciles with
the modeled `slippage_bps`.

## What landed

- **`alpha_execution/orders.py`** — `order_signature(order) -> (side_name, quantity)`: the
  engine-neutral order identity. Exported.
- **`alpha_execution/results.py`** — `RunResult` gains `order_log: list[tuple[str, float]]`
  (backward-compatible; `orders: int` stays).
- **`alpha_backtest/engine.py`** — `run_backtest` records `order_log` from ts-ordered
  `engine.cache.orders()` before dispose.
- **`alpha_paper/reconcile.py`** (pure) — `realized_slippage_bps(side, fill_px, ref_px)` (sign-aware:
  a buy above / sell below the reference is a positive cost) and `reconcile(fills, modeled_bps)` →
  `Reconciliation` records with `delta_bps`. Exported.
- **`alpha_paper/node.py`** — `run_node_for` gains `dispose=False` so a test can read the node cache
  after stopping (dispose clears it).

## Tests
- **`tests/bias_guards/test_paper_parity.py` (HEADLINE):** the SAME `to_execution_feed` drives the
  backtest and, via the fixture replay, the sandbox; assert `node.cache` order signatures ==
  `RunResult.order_log`, non-empty. Proven on the **equity** instrument (integer lots); the crypto
  fractional path is 4f.
- **`tests/integration/test_paper_reconcile.py`:** a sandbox run's filled-order `avg_px` vs the
  recovered session open yields realized slippage matching the modeled bps within tick rounding.
- **`tests/unit/test_paper_reconcile.py`:** the pure reconciliation math.

## Two real findings baked in
1. **Async fill timing.** In an instantaneous fixture replay, an order's async fill hasn't settled
   before the next event, so `net_units` is stale and the next order's delta diverges. Real (daily)
   live data spaces events far apart so fills settle first; the fixture reproduces this via a
   `feed_interval`. Parity holds once events are paced.
2. **One live node per process aborts without a held log guard.** A `TradingNode`'s `LogGuard` drops
   on dispose and tears down the global Rust logger; the next live node then aborts (SIGABRT). Fixed
   in `tests/conftest.py` with a session-scoped fixture that initializes logging once (bypassed) and
   holds the guard — so any number of live nodes coexist (also silences the banner spam). Unblocks
   4f/4h. (Backtests already use `bypass_logging=True`, so only live nodes hit this.)

Plus the 4d caveat still stands: the sandbox hard-codes `MakerTakerFeeModel`, so commission parity is
out of scope; slippage reconciliation is what 4e validates.

## Done = Phase 4e complete
Order-for-order parity proven; slippage reconciled. Gate green (ruff · format · lint-imports 7-kept ·
mypy --strict 119 files · 198 tests).

**Next:** Phase 4f — fractional sizing (honor `instrument.size_precision`) so the crypto path trades,
mirrored in the backtest, with a crypto parity check.
