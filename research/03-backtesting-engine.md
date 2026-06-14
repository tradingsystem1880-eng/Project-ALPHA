# Project ALPHA — Backtesting Engine Selection

**Document:** 03 — Backtesting / Execution Engine
**Date:** 2026-06-14
**Scope:** Single-user, $0-budget, Python-first, institutional-grade, event-driven + look-ahead-safe backtesting → heavy-tailed validation → **paper trading**, with backtest↔paper **parity** (same strategy code).

---

## TL;DR — The Verdict

| Decision | Answer |
|---|---|
| **Primary engine (event-driven, paper-parity core)** | **`nautilus_trader`** — decisively. Rust-core, deterministic event-driven, *literally the same strategy class* runs in backtest, paper, and live. Truly free (LGPL-3.0). |
| **Add a fast vectorized tool for research?** | **Yes — `vectorbt` (open-source core, Apache-2.0+Commons-Clause, free).** Use it for idea triage and broad parameter sweeps ONLY. Promote survivors to Nautilus for honest validation + paper. |
| **Build a custom engine?** | **No.** A correct event-driven engine with realistic fills/margin + live adapters is a multi-year effort. Adopt Nautilus. Build only thin strategy/indicator/analytics code on top. |
| **Best look-ahead safety by construction** | **`nautilus_trader`** — a single deterministic event/message bus drives backtest *and* live; a strategy physically cannot read a bar/tick before its event timestamp is dispatched. |
| **Cleanest backtest→paper path (Alpaca/IBKR)** | **IBKR: `nautilus_trader` today** (production-grade native adapter). **Alpaca: in progress** (RFC #3374). For an Alpaca-first *paper* start with zero friction, a thin `alpaca-py` paper bridge is acceptable as a stopgap — see §7. |

> **Why not LEAN?** QuantConnect LEAN is excellent and genuinely open-source for *backtesting*, but **local live/paper trading via `lean-cli` requires a paid QuantConnect organization tier (~$20–$80/mo)**. That violates the hard $0 constraint for the paper-trading goal. Keep LEAN as a strong "Plan B," not the core. (See §4.)

---

## 1. Evaluation Criteria

Each framework is scored on the dimensions that matter for an institutional-grade personal quant stack:

1. **Architecture** — event-driven (correct, realistic) vs vectorized (fast, approximate).
2. **Look-ahead-bias protection** — by construction vs by discipline.
3. **Friction fidelity** — slippage, fees/commissions, margin, short borrow, partial fills, queue position.
4. **Multi-asset & multi-timeframe** — equities/futures/FX/options/crypto; mixed bar sizes & tick/quote/order-book.
5. **Live/paper adapters** — Alpaca, IBKR, crypto (ccxt/native).
6. **Performance & language** — speed and core implementation language.
7. **Maintenance & community (2025–2026)** — stars, release cadence, is it alive?
8. **Learning curve.**
9. **AI-agent-assisted development fit** — clear/typed APIs, docs, stable surface (this matters: ALPHA is built with an AI coding agent).

---

## 2. Master Comparison Table

| Framework | Model | Look-ahead safety | Friction fidelity | Multi-asset / multi-TF | Live/paper adapters | Speed / lang | Maint. 2025–26 | Stars | Learning curve | AI-agent fit | Free? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **nautilus_trader** | **Event-driven** | **By construction** (deterministic event bus, same in BT & live) | **High**: configurable `FillModel` (prob_slippage, prob_fill_on_limit), L2/L3 order-book fills, queue position, margin models, fees; borrow modelable | **Excellent**: FX, futures, equities (IBKR), crypto, options (greeks added 2026); tick/quote/trade/bar/order-book, multi-venue | **IBKR (prod), Binance, Bybit, OKX, Coinbase, Kraken, dYdX, Hyperliquid, BitMEX, Deribit, Betfair**; **Alpaca = RFC/WIP (#3374)** | **Very high** — **Rust** core + Cython, Python API | **Very active** (v1.228.0, Jun 2026; multiple releases/mo) | **~23.5k** | **Steep** | **Good** (typed configs, huge docs/snippet corpus, stable patterns) | **Yes (LGPL-3.0)** |
| **vectorbt (OSS core)** | **Vectorized** | **By discipline** (off-by-one / `shift` errors easy; you must enforce) | **Low–med**: vector fee/slippage %, fixed/% commission; **can't faithfully model stops/limits, partial fills, intrabar, borrow** | **Good for portfolios of bars**; multi-asset arrays, multi-TF via resample | **None native** (research-only) | **Very high** — NumPy/Numba | **Active-ish** (OSS core slower than PRO; PRO gets the work) | **~5k** | Medium | **Excellent** (array API, massive snippet corpus) | **Yes (Apache-2.0 + Commons Clause)** — **PRO is PAID** (~$20+/mo, invite-only) |
| **QuantConnect LEAN (local CLI)** | **Event-driven** | **By construction** | **High**: institutional fills/fees/margin/shortable-borrow data models | **Excellent**: equities/options/futures/FX/crypto, multi-resolution | **IBKR, Alpaca, 20+ brokers** — **but local live needs PAID QC tier** | High — **C#** core, Python algos | **Very active** | **~12k** (Lean) | Steep | Good (but C# core; data plumbing is the friction) | **Backtest: yes. Local live/paper: NO (paid tier)** |
| **zipline-reloaded** | Event-driven (daily-centric) | By construction (pipeline is point-in-time) | Med: commission/slippage models; weak intraday, no native borrow | **US-equities / daily-bar centric**; intraday awkward | **None native** (backtest/research only) | Med — Python/Cython | **Maintained** (v3.1.x, 2025; Py3.12) | **~1.7k** | Medium | OK (older API, data-bundle friction) | **Yes (Apache-2.0)** |
| **backtesting.py** | Vectorized/loop hybrid | By discipline | Low: % commission, simple slippage; no margin/borrow | **Single-asset only**; no portfolio/multi-asset | **None** | High — Python/NumPy | Light updates (2025) | **~7.1k** | **Low (easiest)** | Excellent (tiny clean API) | **Yes (AGPL-3.0)** |
| **bt** | Allocation/rebalance (periodic) | By discipline | Low: focuses on weights, not microstructure | Multi-asset **portfolio allocation**; not tick/intraday | **None** | Med — Python (on ffn) | **Maintained** (v1.1.2, Apr 2025; Py3.13) | **~2.7k** | Low | Good | **Yes (MIT)** |
| **backtrader** | Event-driven | By construction | Med: commission/slippage/margin; live adapters existed | Multi-asset, multi-TF | IBKR/Oanda (legacy, fragile) | Med — pure Python (slow) | **ABANDONED** — last commit/release **2023-04-19** | **~17k** | Medium | Risky (no upstream fixes) | **Yes (GPL-3.0)** |
| **Qlib (Microsoft)** | ML/alpha research + simple backtest | N/A (point-in-time data infra) | Low (simple exec sim; RL order-exec module) | Equities-factor centric; ML-first | **None** | High — Python/Cython | **Active** (RD-Agent integ.) | **~22k** | Steep | Good for ML, wrong tool for execution | **Yes (MIT)** |

> Star counts are approximate as of mid-2026 (GitHub/web), rounded; treat as relative magnitude.

---

## 3. PRIMARY RECOMMENDATION — `nautilus_trader`

**`nautilus_trader` is the core of Project ALPHA.** It is the only free framework that hits every hard requirement simultaneously:

### 3.1 Why it wins

- **Event-driven by design, and the *same* engine runs live.** The docs are explicit: "identical strategy implementations between research and live deployment … the same execution semantics and deterministic time model operate in both research and live systems." Strategies move from backtest → paper → live **without code changes**. This is *parity by construction*, not by convention — the #1 requirement of ALPHA.
  - Source: https://github.com/nautechsystems/nautilus_trader and https://nautilustrader.io/docs/latest/concepts/backtesting/

- **Look-ahead bias is structurally prevented.** A single deterministic message/event bus dispatches data events strictly in timestamp order; a `Strategy` only ever receives an `on_bar`/`on_quote_tick`/`on_trade_tick`/`on_data` callback when that event's time is reached. There is no DataFrame the strategy can "peek" forward into. Nanosecond event clock. This is the cleanest look-ahead protection of any option here (tied with LEAN, but Nautilus is free for live).

- **Institutional friction modeling.** Configurable `FillModel`:
  ```python
  fill_model=FillModelConfig(
      prob_fill_on_limit=0.2,   # chance a limit fills when price only touches
      prob_slippage=0.5,        # chance of 1-tick adverse slippage (L1 data)
      random_seed=42,           # reproducible
  )
  ```
  - **L2/L3 order-book data → fills walk real book levels** (size-aware, depth impact, per-level liquidity consumption via `liquidity_consumption=True`).
  - **Queue position tracking** (`queue_position=True`) for realistic limit-order fills.
  - **Margin vs cash accounts**, `MarginModelConfig(model_type="standard")` for broker-style margin.
  - **Fees/commissions** per instrument; **short selling** supported; **borrow/financing fees are modelable** (note: not always on by default — you configure them; budget time for this on short strategies).
  - Source: https://nautilustrader.io/docs/latest/concepts/backtesting/ ; https://github.com/nautechsystems/nautilus_trader/issues/2194

- **Multi-asset, multi-venue, multi-timeframe.** FX, futures, equities (via IBKR), crypto, and options (option chains + greeks landed in Rust & Python in 2026). Backtest multiple venues/instruments/strategies simultaneously across tick/quote/trade/bar/order-book data.

- **Performance / language.** Rust core (with Cython bindings) and a Python API. Among the fastest event-driven engines in existence; handles tick/LOB backtests that would crawl in pure-Python backtrader.

- **Alive and thriving.** ~23.5k GitHub stars; **v1.228.0 Beta released 2026-06-08**, with multiple releases per month through 2026. This is the single most actively developed open-source trading engine.
  - Sources: https://github.com/nautechsystems/nautilus_trader ; https://github.com/nautechsystems/nautilus_trader/releases ; https://pypi.org/project/nautilus_trader/

- **License: LGPL-3.0** — free for personal use. (LGPL is copyleft; for a *personal, non-distributed* research platform this is a non-issue. Only matters if you later redistribute a modified core.)

### 3.2 Honest downsides

- **Steep learning curve.** Confirmed across reviews: paradigm shift to event-driven/order-lifecycle programming, build/install complexity, and high-fidelity data requirements for tick/LOB backtests. Expect a real ramp-up. (Source: review aggregation, https://dev.to/kpcofgs/nautilustrader-the-open-source-trading-platform-5dji)
  - **Mitigation:** This is *exactly* where AI-agent-assisted development pays off. Nautilus has a large, well-structured docs + example corpus (thousands of indexed snippets via Context7), typed config objects, and stable, repeated patterns (`BacktestEngine` → `add_venue` → `add_instrument` → `add_data` → `add_strategy` → `run`). The agent can scaffold strategies and configs reliably.

- **Alpaca adapter is not yet first-class** (RFC #3374, in progress — native HTTP/WS, no SDK dependency planned). **IBKR is production-grade today.** See §7 for the parity path.

- **"Beta" version label.** Despite "Beta" in the version string, it is used in production by individuals and small teams; the label reflects API-evolution caution, not instability.

### 3.3 AI-agent development fit (important for ALPHA)

Strong. Typed `*Config` dataclasses with JSON-schema generation, a consistent imperative setup flow, exhaustive API reference, and a massive snippet corpus the coding agent can ground on (Context7 `/nautechsystems/nautilus_trader`, ~7.7k snippets; site mirror ~3.5k). The biggest agent risk is the breadth of the API — pin a Nautilus version and keep the docs in context.

---

## 4. Why NOT LEAN as the core (the close runner-up)

QuantConnect **LEAN** is institutional-grade, event-driven, look-ahead-safe by construction, and has the best built-in friction models (including shortable-quantity/borrow data) and the broadest broker list (IBKR, Alpaca, 20+).

**The disqualifier for ALPHA's $0 paper-trading goal:**
- **Local live/paper trading via `lean-cli` requires membership in a *paid* QuantConnect organization tier (~$20–$80/mo).** The free plan only gives limited cloud hourly/daily history. Local backtesting with **your own data** is free, but the moment you want **paper trading**, you hit the paywall.
  - Sources: https://www.quantconnect.com/forum/discussion/16036/ ; https://www.quantconnect.com/pricing/ ; https://www.quantconnect.com/docs/v2/lean-cli/live-trading/brokerages/alpaca

**Secondary friction:** C#-core (Python algos run, but debugging/extending the engine means C#), and local data plumbing is manual (you `lean data download` or supply your own; bulk QC data is paid and must be re-pulled daily).

**Verdict:** Keep LEAN as a documented **Plan B**. If you ever outgrow Nautilus's equities/Alpaca story and are willing to pay ~$20/mo, LEAN is the natural escalation. For now it conflicts with the hard constraint.

---

## 5. The vectorized research layer — `vectorbt` (open-source core)

### 5.1 Recommendation: YES, add it — for research only

Use **`vectorbt`** (the **open-source** `polakowo/vectorbt`, Apache-2.0 + Commons-Clause, **free**) as a **fast idea-triage / parameter-sweep** layer. It runs **thousands of parameter combinations** in seconds via NumPy + Numba — something an event-driven engine cannot match for breadth.

- Source: https://github.com/polakowo/vectorbt ; https://vectorbt.dev/

### 5.2 Critical caveats (why it is NOT the validation engine)

- **Look-ahead bias is on YOU.** Vectorized signal logic makes off-by-one / `df.shift(-1)` errors trivial to introduce and easy to miss; a single misaligned index silently inflates returns. (Source: https://www.interactivebrokers.com/campus/ibkr-quant-news/a-practical-breakdown-of-vector-based-vs-event-based-backtesting/)
- **It cannot faithfully model microstructure:** assumes fills at next bar open/close, ignores intrabar path, bid-ask, partial fills; **stop/limit/trailing logic and borrow costs are not honestly simulable.**
- **vectorbt PRO is PAID** (~$20+/mo, invite-only, proprietary). PRO has the better look-ahead handling and active dev — but it costs money, so it is **out of scope** under the $0 rule. Use only the OSS core.

### 5.3 Alternatives considered for the research layer (and rejected)

- **`backtesting.py`** (7.1k, AGPL-3.0): cleanest API, but **single-asset only** — no portfolio sweeps. Fine for a quick single-name sanity check; too limited as the main research tool.
- **`bt`** (2.7k, MIT, maintained 2025): great for **weight/allocation** strategies and periodic rebalancing research, weak on microstructure. Optional add-on if you do asset-allocation work.
- **`Qlib`** (Microsoft, ~22k, MIT): superb **ML alpha-factor research** and point-in-time data infra, with an RL order-execution module — but it is **not an execution/parity engine**. Adopt later *only if* you go heavy on ML signal generation; it would feed signals into Nautilus, not replace it.

---

## 6. HYBRID WORKFLOW (concrete)

A two-engine pipeline: **vectorbt for breadth, Nautilus for truth + paper.**

```
┌──────────────────────────────────────────────────────────────────────┐
│ STAGE 0 — DATA (shared, point-in-time, single source of truth)        │
│   Parquet/columnar store; corporate-action-adjusted; UTC timestamps.  │
│   Same data feeds BOTH engines to keep comparisons honest.            │
└──────────────────────────────────────────────────────────────────────┘
                 │                                   │
                 ▼                                   ▼
┌───────────────────────────────┐   ┌──────────────────────────────────┐
│ STAGE 1 — RESEARCH / TRIAGE    │   │ STAGE 2 — VALIDATION (the gate)   │
│ Tool: vectorbt (OSS)           │   │ Tool: nautilus_trader             │
│ • 1000s of param combos        │   │ • Event-driven, look-ahead-safe   │
│ • coarse % fees/slippage       │   │ • realistic FillModel / L2 fills  │
│ • rank by Sharpe/Calmar/etc.   │   │ • fees + margin + borrow          │
│ • DISCARD the obvious junk     │   │ • walk-forward / OOS only         │
│ ⚠ treat results as OPTIMISTIC  │   │ • heavy-tailed stats validation*  │
└───────────────────────────────┘   └──────────────────────────────────┘
                 │  promote top N survivors only      │
                 └────────────────────────────────────┘
                                   │ passes validation gate
                                   ▼
                 ┌──────────────────────────────────────────┐
                 │ STAGE 3 — PAPER (SAME Nautilus strategy)   │
                 │ • identical Strategy class as Stage 2       │
                 │ • IBKR paper (native adapter) / crypto      │
                 │   testnet / Alpaca paper bridge (§7)        │
                 │ • compare live fills vs backtest fills      │
                 └──────────────────────────────────────────┘
                                   │ stable & matches backtest
                                   ▼
                 ┌──────────────────────────────────────────┐
                 │ STAGE 4 — LIVE (same code, real adapter)   │
                 └──────────────────────────────────────────┘
```
\* Heavy-tailed validation (bootstrap, block-bootstrap, deflated Sharpe, regime/tail stress) is covered in a separate ALPHA doc; it consumes Stage-2 Nautilus trade-level output.

**The rule:** *vectorbt never validates and never trades.* It only decides what is **worth** simulating properly. A strategy is "real" only after it survives a Nautilus event-driven walk-forward and then matches in paper. This guards against vectorized over-optimism while keeping research fast and cheap.

**Parity discipline:** the Stage-2 backtest `Strategy` and the Stage-3/4 paper/live `Strategy` are the *same Python class*. Only the venue/execution-client config and data feed swap. This is Nautilus's core design — lean on it.

---

## 7. Cleanest backtest→paper path to Alpaca / IBKR

| Broker | Nautilus status | Recommendation |
|---|---|---|
| **Interactive Brokers** | **Production-grade native adapter** (`InstrumentProvider`/`DataClient`/`ExecutionClient`); active 2026 fixes. IBKR offers a free **paper account**. | **Preferred parity path.** Same Nautilus strategy → IBKR paper → IBKR live, zero code change. Underlying transport related to the `ib_async` (ex-`ib_insync`) ecosystem. |
| **Crypto (Binance/Bybit/OKX/Coinbase/Kraken/etc.)** | **Native adapters, mature.** Testnets/sandboxes available. | **Cleanest of all.** Same strategy → exchange testnet → live. If ALPHA includes crypto, this is the lowest-friction paper path today. |
| **Alpaca** | **In progress** (RFC #3374): native HTTP/WS adapter, no SDK dependency, US equities/ETFs/options/crypto planned. | **Two options:** (a) **Wait/track** the native adapter and get full parity; or (b) **stopgap:** wrap Alpaca's free **paper API** via `alpaca-py` behind a thin custom Nautilus `ExecutionClient`/`LiveDataClient`, OR run the *same* strategy logic against Alpaca paper through a thin shim while the native adapter lands. Acceptable for a personal project; revisit when #3374 ships. |

- Sources: https://nautilustrader.io/docs/nightly/integrations/ib/ ; https://github.com/nautechsystems/nautilus_trader/issues/3374 ; https://github.com/ib-api-reloaded/ib_async ; https://alpaca.markets/

**Bottom line on parity:** If you can use **IBKR paper** or a **crypto testnet**, Nautilus gives you *true same-code* backtest→paper→live **today**. If you are committed to **Alpaca specifically**, accept a short bridge period (or track RFC #3374). Either way, Nautilus is still the right core — its whole architecture is built for this transition.

---

## 8. BUILD vs BUY — firm verdict: **BUY (adopt Nautilus)**

**Do not write a custom event-driven engine.** Reasons:

1. **Correctness is the hard part, and it's enormous.** A look-ahead-safe deterministic event loop, realistic matching engine (queue position, partial fills, L2 book walking), margin/borrow accounting, multi-venue routing, and *then* live broker adapters with reconciliation — this is a multi-engineer, multi-year body of work. Nautilus has already done it in Rust, battle-tested, and gives it away free.
2. **Parity for free.** The single hardest thing you'd be building — *the same code path for backtest and live* — is Nautilus's central design guarantee. Re-implementing that correctly alone would dwarf the rest of ALPHA.
3. **Opportunity cost.** Every hour on plumbing is an hour not spent on **strategies, signals, and the heavy-tailed validation** that is ALPHA's actual edge.
4. **Maintenance.** Exchange APIs, broker quirks, and instrument specs change constantly. Nautilus's active 2026 release cadence absorbs that churn for you.

**What you SHOULD build on top:** strategy classes, custom indicators, your data ingestion/point-in-time store, the heavy-tailed statistical-validation harness, reporting/journaling, and (if needed) a thin Alpaca paper bridge. That is the right altitude for custom code.

> The *only* scenario that would justify a custom engine is an exotic requirement no engine supports (e.g., a bespoke market-microstructure simulation). ALPHA has no such requirement. **Adopt Nautilus.**

---

## 9. Maintenance-status honesty roll-call (2025–2026)

- **nautilus_trader** — **Thriving.** v1.228.0 (2026-06-08), multiple releases/month, ~23.5k stars. ✅
- **vectorbt (OSS)** — **Alive but secondary** to the paid PRO; OSS core gets fewer updates. PRO is paid. ⚠️
- **QuantConnect LEAN** — **Very active**, but **local live/paper is paywalled**. ⚠️ (free for backtest only)
- **zipline-reloaded** — **Maintained** by Stefan Jansen (v3.1.x, Py3.12, 2025), but daily/US-equities-centric, no native live. 🟡
- **backtesting.py** — **Lightly maintained** (updates into 2025); single-asset, no live. 🟡
- **bt** — **Maintained** (v1.1.2, Apr 2025, Py3.13); allocation-focused, no live. 🟡
- **backtrader** — **ABANDONED.** Last commit/release **2023-04-19** (v1.9.78.123). Forks (`backtrader2`, `backtrader_next`, `cloudQuant`) exist but are not authoritative. **Do not adopt.** ❌
- **Qlib** — **Active** (Microsoft, RD-Agent integration); ML-research tool, not an execution engine. 🟡

---

## 10. Final Stack Decision for Project ALPHA

```
PRIMARY (event-driven core, validation + paper/live parity):  nautilus_trader   [LGPL-3.0, free]
RESEARCH (fast vectorized triage / param sweeps):             vectorbt (OSS)    [Apache-2.0+CC, free]
OPTIONAL ML alpha research (only if ML-heavy, later):         Qlib              [MIT, free]
PAPER/LIVE adapter path:                                      IBKR (native) or crypto testnet today;
                                                              Alpaca via native adapter (RFC #3374) or thin bridge
PLAN B (if willing to pay ~$20/mo for managed local live):    QuantConnect LEAN
REJECTED:                                                     backtrader (abandoned), backtesting.py (single-asset),
                                                              bt (allocation-only), zipline-reloaded (daily/no-live),
                                                              vectorbt PRO (paid)
```

**One-line mandate:** *Build strategies once as Nautilus `Strategy` classes; sweep ideas fast in vectorbt; validate honestly in Nautilus with realistic frictions and walk-forward; promote the same code to IBKR/crypto paper, then live — never let a vectorized result count as validation, and never write your own engine.*

---

## Sources

- NautilusTrader repo (stars, adapters, parity, license, latest release): https://github.com/nautechsystems/nautilus_trader
- NautilusTrader releases: https://github.com/nautechsystems/nautilus_trader/releases
- NautilusTrader PyPI: https://pypi.org/project/nautilus_trader/
- NautilusTrader backtesting docs (FillModel, L2/L3, queue, margin): https://nautilustrader.io/docs/latest/concepts/backtesting/
- NautilusTrader IBKR integration: https://nautilustrader.io/docs/nightly/integrations/ib/
- NautilusTrader Alpaca RFC #3374: https://github.com/nautechsystems/nautilus_trader/issues/3374
- NautilusTrader enhanced fill-sim issue #2194: https://github.com/nautechsystems/nautilus_trader/issues/2194
- NautilusTrader review (learning curve): https://dev.to/kpcofgs/nautilustrader-the-open-source-trading-platform-5dji
- vectorbt (OSS) repo: https://github.com/polakowo/vectorbt
- vectorbt docs: https://vectorbt.dev/
- vectorbt OSS vs PRO / pricing: https://algotrading101.com/learn/vectorbt-guide/
- Vector vs event-based backtesting (look-ahead pitfalls): https://www.interactivebrokers.com/campus/ibkr-quant-news/a-practical-breakdown-of-vector-based-vs-event-based-backtesting/
- QuantConnect LEAN repo: https://github.com/QuantConnect/Lean
- LEAN CLI: https://github.com/QuantConnect/lean-cli
- LEAN local live needs paid tier: https://www.quantconnect.com/forum/discussion/16036/lean-local-live-trading-does-it-need-paid-subscription/
- QuantConnect pricing: https://www.quantconnect.com/pricing/
- LEAN Alpaca brokerage docs: https://www.quantconnect.com/docs/v2/lean-cli/live-trading/brokerages/alpaca
- zipline-reloaded repo + releases: https://github.com/stefan-jansen/zipline-reloaded
- backtesting.py repo: https://github.com/kernc/backtesting.py
- bt repo: https://github.com/pmorissette/bt
- backtrader repo (abandoned) + PyPI: https://github.com/mementum/backtrader ; https://pypi.org/project/backtrader/
- Microsoft Qlib repo: https://github.com/microsoft/qlib
- ib_async (IBKR Python, ex-ib_insync): https://github.com/ib-api-reloaded/ib_async
- Alpaca: https://alpaca.markets/
