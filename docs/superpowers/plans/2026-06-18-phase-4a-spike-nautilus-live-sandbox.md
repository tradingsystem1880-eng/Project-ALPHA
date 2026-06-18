# Phase 4a — SPIKE: nautilus 1.228 live/sandbox API (ADR)

> **For agentic workers:** read-only verification spike. No production code, no DAG changes. The
> deliverable is this ADR pinning the confirmed API so 4b+ build on facts, not assumptions
> (`CLAUDE.md` discipline; mirrors the Phase-2 nautilus spike).

**Goal:** confirm the exact `nautilus_trader==1.228.0` live/sandbox surface needed for crypto-first
paper trading, and lock the three open decisions (data path, instrument construction, sizing).

## Confirmed API (probed against the installed 1.228.0)

- **Sandbox execution** — `nautilus_trader.adapters.sandbox`:
  - `execution.SandboxExecutionClient`, `config.SandboxExecutionClientConfig`,
    `factory.SandboxLiveExecClientFactory`.
  - `SandboxExecutionClientConfig` fields: `instrument_provider, routing, venue, starting_balances,
    base_currency, oms_type, account_type, default_leverage, leverages, book_type, frozen_account,
    **bar_execution**, trade_execution, reject_stop_orders, support_gtd_orders, ...`.
  - **Key parity lever:** `bar_execution` exists on the sandbox config → set **`bar_execution=False`**
    so only quotes fill, exactly as the backtest venue does. The sandbox runs an internal
    `SimulatedExchange`/matching engine fed by live data — broker-independent, no real orders, $0.
- **Live node** — `nautilus_trader.live.node`: `TradingNode`, `TradingNodeConfig`,
  `TradingNodeBuilder`; register clients via `add_data_client_factory(name, Factory)` /
  `add_exec_client_factory(name, SandboxLiveExecClientFactory)`, then `node.build()` / `node.run()`.
  - `TradingNodeConfig` fields include `data_clients, exec_clients, risk_engine, cache, message_bus,
    logging, load_state, save_state, timeout_reconciliation, strategies, ...` — covers state
    persistence (`load_state`/`save_state`), audit (`logging`), and risk (`risk_engine`).
  - `nautilus_trader.live.config` provides `LiveDataClientConfig`, `LiveExecClientConfig`,
    `LiveRiskEngineConfig`, `RiskEngineConfig`, `Environment`, `InstrumentProviderConfig`.
- **Crypto instrument** — `TestInstrumentProvider.btcusdt_binance()` returns a ready `CurrencyPair`
  `BTCUSDT.BINANCE`: `price_precision=2`, **`size_precision=6`**, `size_increment=0.000001`. (Also
  `ethusdt_binance`, `adausdt_binance`, `xrpusdt_linear_bybit`, perps/futures helpers.) Equity by
  contrast is `size_precision=0` (integer lots).
- **Strategy base** — `nautilus_trader.trading.strategy.Strategy` unchanged; `TimeSeriesMomentum`
  needs no engine-specific edits to run under a `TradingNode`.

## Decisions locked

1. **Data path (4d):** start with a **thin live data client behind a seam** + `FixtureLiveDataClient`
   for offline/CI; the first *real* feed targets public crypto data (key-free). Native adapter
   (Binance/Bybit) vs `ccxt.pro` is finalized in 4d against this seam — the sandbox needs only a live
   **data** feed, not an exec venue, so this choice is isolated and swappable.
2. **Instrument construction (4b):** `crypto_instrument(symbol, venue=...)` wraps
   `TestInstrumentProvider.btcusdt_binance()` for the BTC/USDT first increment, mirroring how
   `equity_instrument` wraps `TestInstrumentProvider.equity`. Explicit hand-built `CurrencyPair`s for
   other pairs are a later increment behind the same seam.
3. **Sizing:** `size_precision=6` **confirms fractional sizing is genuinely needed** for crypto. The
   first green increment keeps the existing integer-lot path (coarse but functional at high notional);
   true fractional sizing is isolated to **4f** and mirrored in backtest to preserve parity.

## Parity conclusion

`SandboxExecutionClientConfig.bar_execution=False` + subscribe(daily bar → decide, quote → execute)
reproduces the backtest's "decide on close-t / fill at open-t+1" causal chain with real wall-clock
events. The same `TimeSeriesMomentum` class runs unchanged. The one risk — a stale pre-decision quote
arriving first — is handled at the data-client seam (4d), keeping the strategy byte-identical.

## Done = Phase 4a complete

API surface pinned; the three open decisions resolved; no code/DAG changes.

**Next:** Phase 4b — extract the `alpha-execution` layer (instruments + frictions + results), add
`crypto_instrument`, and wire the new import-linter contracts.
