# Phase 4d — Sandbox TradingNode + FixtureLiveDataClient

> **For agentic workers:** TDD per `CLAUDE.md`. First phase touching real nautilus live/async wiring.
> Developed iteratively against the installed `nautilus_trader==1.228.0` (not from assumptions).

**Goal:** assemble a live `TradingNode` wired to the `SandboxExecutionClient`, fed by a pluggable
live-data-client seam, and prove offline + deterministically that a do-nothing strategy sees every
replayed bar/quote through the full live path and produces zero orders.

## What landed

- **`alpha_paper/node.py`**:
  - `build_paper_node(spec, instrument, *, data_client_name, data_client_factory,
    data_client_config, ...)` → composes a `TradingNodeConfig` with a `SandboxExecutionClient`
    (`SandboxLiveExecClientFactory`) on the **instrument's own venue**, NETTING OMS,
    `bar_execution=False` (only quotes fill → the backtest's t+1 convention), balances/base-currency
    in the instrument's quote currency, and the injected data client. Adds the instrument to the
    node cache. The caller adds the strategy via `node.trader`.
  - `run_node_for(node, duration_seconds)` → bounded async drive (`run_async` → sleep →
    `stop_async` → `dispose`) for tests and bounded sessions. Live open-ended sessions use the
    node's own blocking `run()`.
  - `alpha-paper` gains a `nautilus-trader>=1.228` dependency.
- **`tests/fixtures/paper_fixtures.py`** (offline replay infra, reused by 4e):
  `FixtureLiveDataClient` + `FixtureLiveDataClientFactory` + `FixtureDataClientConfig` (events passed
  via a process-local registry keyed by a config string), `make_quote`/`make_bar`/`daily_bar_type`
  builders (precision via `instrument.make_price`/`make_qty`), and a `CountingStrategy` (do-nothing).
- **`tests/integration/test_paper_sandbox.py`**: 4 quotes + 4 bars replayed → strategy sees all 4
  bars + 4 quotes; `cache.orders()` is empty.

## Spike learnings baked in (the live node is finicky; these are the gotchas)
1. **Engines must run `graceful_shutdown_on_exception=True`.** The nautilus default is an immediate
   `os._exit(1)` (data/exec/risk engines) on an unhandled queue exception — a *silent* crash whose
   logged cause never flushes from the async logger. Graceful mode surfaces the real error.
2. **Async data clients require `async def _subscribe_*`** — the engine awaits them; a plain `def`
   returns `None` → `TypeError("a coroutine was expected, got None")`.
3. **Build market data via `instrument.make_price`/`make_qty`** — a precision mismatch with the
   instrument makes nautilus reject the tick/bar.
4. **The sandbox venue must equal the instrument's venue** (it loads instruments from cache by venue
   and subscribes to `data.*.{venue}.*`). The instrument goes into the cache before connect.
5. `LoggingConfig.bypass_logging=True` is illegal in a LIVE context — use a quiet `log_level`.

## Parity caveat (recorded, not silently ignored)
`SandboxExecutionClient` **hard-codes `MakerTakerFeeModel`** — it does not accept the backtest's
`BpsFeeModel`. So paper commissions follow the instrument's maker/taker fees rather than the modeled
bps. This is a known model gap to **quantify in reconciliation (4e)** and revisit in 4g.

## Done = Phase 4d complete
Gate green (ruff · format · lint-imports 7-kept · mypy --strict 113 files · 191 tests). The live
sandbox node runs offline and deterministically.

**Next:** Phase 4e — run the real `TimeSeriesMomentum` unchanged through the sandbox replay; the
headline bias-guard parity test (same bars → same orders as the backtest) + reconciliation.
