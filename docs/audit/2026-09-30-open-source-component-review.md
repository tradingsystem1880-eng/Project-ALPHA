# Open-source components for ALPHA

Reviewed 2026-09-30 against upstream documentation and current ALPHA package manifests. This is an integration assessment, not a claim that candidates are installed, benchmarked or production-accepted. The concurrent improve-agentic-benchmarks session retains ownership of its evaluator and findings.

## Decisions

| Capability | Upstream project | ALPHA decision and concrete use |
|---|---|---|
| Interactive price charts | [TradingView Lightweight Charts](https://github.com/tradingview/lightweight-charts) | Keep existing engine. Reuse panes, primitives, crosshair and incremental updates. Fix asset discovery and verified datasets before replacing rendering. Apache-2.0; retain required NOTICE and visible TradingView attribution. |
| Movable terminal workspace | [Dockview](https://github.com/dockview/dockview) | Prototype after restoring reference chrome. Evaluate tabbed/split layouts, persistence, keyboard access and inactive-panel lifecycle against existing PanelHost. Core/React packages MIT; enterprise package is separately commercial. Do not import enterprise features accidentally. |
| Chart interaction alternative | [KLineChart](https://github.com/klinecharts/KLineChart) | Compare custom indicator/drawing interactions in an isolated prototype. Avoid running two chart engines in the shipped UI. Study its indicator registration UX; ALPHA numerical calculations remain in the authoritative Python layer. |
| Provider abstraction | [OpenBB](https://github.com/OpenBB-finance/OpenBB), [provider structure](https://github.com/OpenBB-finance/OpenBB/blob/develop/openbb_platform/providers/README.md) | Study query/response models and provider-specific adapters. Adopt selected adapters only where they add needed coverage. Do not install every provider or equate an open-source adapter with a free or verified data entitlement. Current repository declares Apache-2.0. Its data platform and hosted Workspace are distinct surfaces. |
| Streaming crypto market data | [CCXT](https://github.com/ccxt/ccxt), [WebSocket documentation](https://docs.ccxt.com/docs/pro) | Extend existing CCXT boundary, using public market discovery and public streaming capabilities where supported. Pro/WebSockets are now part of the free distribution. Display live ticks separately from immutable research history; handle reconnect, stale prices and exchange rate limits. |
| Interactive large data tables | [Perspective](https://github.com/perspective-dev/perspective) | Candidate for exploratory pivots, grouping and streaming tables. Keep current TanStack tables for ordinary forms/blotters. Prototype on bounded non-authoritative data, measuring startup cost and responsiveness before adding WASM. |
| ML workflows | [Microsoft Qlib](https://github.com/microsoft/qlib) | Retain isolated worker integration. Improve dataset/experiment/result journeys and expose actual worker failures; do not duplicate the platform inside the web process. |
| Agent research workflow | [Microsoft RD-Agent](https://github.com/microsoft/RD-Agent) | Architectural reference for experiment/feedback loops. Evaluate ideas against retained Codex benchmark traces and ALPHA's blinded-data boundaries; no automatic replacement of the existing evaluator or authorization. |
| Event-driven execution | [NautilusTrader](https://github.com/nautechsystems/nautilus_trader) | Retain current pinned engine. Expose its recorded fills, events and diagnostics coherently. No replacement engine or live-capital expansion in this UI task. |
| Indicator catalogue | [TA-Lib Python](https://github.com/TA-Lib/ta-lib-python) | Candidate backend adapter for indicators missing from alpha_patterns. Test warm-up, NaNs, conventions, input types and future-cutoff behavior before adoption. Never silently replace existing formulas. |
| Hyperparameter search | [Optuna](https://github.com/optuna/optuna) | Future bounded-search candidate. Must preserve frozen trial budgets, complete ledgers, deterministic seeds and multiple-testing accounting. More trials do not automatically improve evidence. |

## Existing strengths versus actual gaps

Current frontend directly depends on React, Lightweight Charts, TanStack Table/Virtual and cmdk. Python packages already use CCXT, Polars, SciPy and a pinned NautilusTrader; Qlib has an out-of-process integration. Installing newer packages without wiring their owner journeys would not resolve the observed failures.

Live read-only investigation found 32 canonical-store symbols, of which the slash-based crypto picker displayed only three. XRP/USD is Coinbase; XRP/USDT is Binance. They are different markets. The mounted external drive's discovery metadata contains 33,534 manifests, 11,774 normalized datasets, 68 instrument strings and 51 named base assets. These counts are metadata discovery, not full artifact acceptance. Existing chart readers cannot consume these manifests. Ordinary storage/coverage reads also perform expensive whole-drive verification. Those integration defects are the immediate data priority.

Use metadata discovery for selection, then verify the exact selected manifest and raw lineage. Carry venue, market type, quote, frequency and manifest identity through chart requests. Do not silently merge spot/perpetual markets or overlapping acquisition chunks. Completed OHLCV is knowable at interval completion, not interval start.

## Adoption acceptance

For each candidate, record the exact release/commit and package-specific licence, inspect the relevant implementation and tests, then compare against ALPHA with one reproducible owner journey. Required measurements: cold/warm latency, large-data response, keyboard and resize behavior, error recovery, dependency/bundle cost, and numerical or provenance parity where applicable. Keep only components that materially improve those results.

The benchmark session's new findings are inputs to this backlog, not yet incorporated results. UI completion requires actual browser-to-CLI journeys, not just synthetic API mocks or a clean dependency install. The owner reference folder remains the visual authority: light Windows chrome, dense linked tools, legible tables and a large chart, not any upstream project's branding.
