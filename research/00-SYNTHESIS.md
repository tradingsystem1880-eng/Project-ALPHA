# Project ALPHA — Research Synthesis & Architecture Decision Record

**Date:** 2026-06-14
**Scope locked by owner:** Personal (single-user) · $0 budget (free data + open-source only) · Python-first · backtesting + statistical validation + **paper** trading (no real money yet) · built by AI coding agents (Claude Code).

This document consolidates seven parallel deep-research streams (reports `01`–`07` in this folder) into a single recommended architecture, the hard truths that change the original blueprint, and the open decisions.

---

## TL;DR — The Converged Stack

Every research stream independently pointed at the same spine. Nothing here costs money.

| Layer | Decision | Why | Report |
|---|---|---|---|
| **Backtest + Paper engine** | **`nautilus_trader`** | Only free engine with **parity by construction** — the *same* `Strategy` class runs in backtest, paper, and live. Rust core (fast). Look-ahead is *physically impossible* (single timestamp-ordered event bus). Institutional friction models. Built-in reconciliation. | 03, 05 |
| **Storage** | **Parquet (truth) + DuckDB (query) + Polars (frames)**, Arrow zero-copy | Zero ops, no server, columnar speed rivaling ClickHouse under solo workloads. DuckLake later for ACID/versioning. | 02 |
| **Fast research sweeps** | **vectorbt** (OSS core) | Thousands of param combos in seconds for *triage only* — never for validation (it's look-ahead-prone). | 03 |
| **Validation** | `arch` + `skfolio` + `empyrical-reloaded` + `quantstats` + `scipy`/`statsmodels` | Walk-forward → CPCV → PBO → Deflated Sharpe → SPA → bootstrap CIs → Monte Carlo. All free/BSD. | 04 |
| **Data — crypto** | `ccxt` + `data.binance.vision` bulk + Bybit depth dumps | **Free institutional-grade tick + full L2 order book.** | 01 |
| **Data — equities** | Stooq/Tiingo/yfinance (EOD) · Alpaca (1-min, IEX) · SEC EDGAR (fundamentals) | Daily/minute bars + fundamentals are fully free; **tick/SIP/L2 are NOT free.** | 01 |
| **Data — FX / macro** | Dukascopy (FX tick) · FRED (macro) | FX tick free back to ~2003; FRED is best-in-class free. | 01 |
| **Paper trading** | nautilus `SandboxExecutionClient` + crypto testnets (Binance/Bybit) | Same matching engine as backtest, fed live data, broker-independent, free. | 05 |
| **Repo + tooling** | **`uv` workspace** of small `src/` packages · Polars · pydantic-settings · strict mypy · pytest + Hypothesis · marimo · GitHub Actions | Hard structural module boundaries = the #1 reliability lever for AI-written code. `uv` decisively (nautilus recommends it; TA-Lib ships wheels now). | 07 |

---

## The Single Most Important Finding: the Free-Data Reality

Free data quality is **wildly asymmetric** across asset classes. This is the fact that should shape product direction more than any other.

| Asset class | Daily/EOD | 1-min intraday | Tick | L2 order book | Real-time stream | Free paper trading |
|---|---|---|---|---|---|---|
| **Crypto** | ✅ free | ✅ free | ✅ **free** | ✅ **free, full depth** | ✅ **free, 24/7** | ✅ testnets |
| **US equities** | ✅ free | ✅ free (IEX only, ~2-3% vol) | ❌ paid (SIP) | ❌ paid | ⚠️ IEX-only free; SIP $99/mo | ✅ Alpaca/IBKR |
| **FX** | ✅ free | ✅ free | ✅ free (Dukascopy) | ❌ none exists (OTC) | ⚠️ limited | ⚠️ IBKR |
| **Futures** | ⚠️ weak | ⚠️ weak | ⚠️ one-time Databento $125 credit | ⚠️ | ❌ | ⚠️ |

**Implication:** Genuine microstructure research + honest, full-fidelity paper trading is **only fully free in crypto.** Equities/FX are viable on **daily + minute bars** (signals, swing/positional strategies) but data-starved for serious intraday/microstructure work.

---

## Hard Truths (where the original blueprint was wrong or oversold)

1. **The prop-firm "EV alchemy" claim is a fallacy.** The blueprint claimed optimized leverage/sizing can make *near-zero-EV strategies* net positive against a prop firm. Mathematically false: position sizing scales drift **and** volatility *together* (μ,σ → ℓμ,ℓσ), so with zero raw edge (μ=0) the pass-probability collapses to `B/(A+B)` — **provably independent of leverage** — and EV is exactly zero before fees, negative after. With negative edge, leverage makes it strictly worse. Sizing optimization only helps **when a real edge already exists (μ>0)**. The only loophole is payout/fee *convexity* (you risk the fee, not your capital), but firms price that to ≤0 for zero-edge traders. → *Edge must come first; sizing is amplification, not creation.* (Report 04)

2. **The "AI dev harness" (Phases 4–5: OpenHands, Kilo Code, Daytona, HierFinRAG) is not a product — it's just us.** Cut entirely. (Confirmed by owner.)

3. **Institutional infra is unnecessary at this scale.** ClickHouse Cloud, Databento paid, kdb+, AWS Batch — all overkill for one person. DuckDB + Parquet matches their single-node performance at $0 and zero ops. (Report 02)

4. **The blueprint's strategy templates are low-prior hypotheses.** The blueprint itself admits SMC/support-resistance patterns appear with *identical frequency on random charts*. So the templates (8AM ORB, Rejection Block) must beat a **randomized-price null** before being believed. The moat is the **methodology**, not the strategies. (Report 06)

5. **Two recommended-sounding libraries are NOT free for this use:** `mlfinlab` (now proprietary/commercial license) and `ArcticDB` (Business Source License — not free where "economic benefit is derived"). Avoid both; open substitutes exist. (Reports 02, 04, 06)

---

## The Real Moat: Look-Ahead-Safety by Construction + the Validation Gauntlet

What makes this "institutional-grade" on a $0 budget is **rigor**, enforced mechanically:

- **Engine-level:** nautilus's event bus makes peeking at future bars physically impossible.
- **Data-level:** strategies may *only* read via a point-in-time accessor (`as_of(t)` filtered to `available_at <= t`) — never a raw DataFrame.
- **Test-level (the killer feature):** a `bias_guards/` test suite gating CI:
  - **Future-poison test** — replace all post-cutoff data with NaN; assert outputs are byte-identical to the clean run. Any difference = the code peeked.
  - **Causality/shift test** — a signal at bar *t* can only fill at *t+1*.
  - **Purged k-fold + embargo** in the validator itself.
  - **Survivorship guard** — the as-of universe must include later-delisted names.
- **Validation pipeline:** walk-forward → CPCV (purge+embargo) → PBO → Deflated Sharpe → Hansen SPA → block-bootstrap BCa CIs → GARCH-t / Markov / Student-t Monte Carlo (incl. the randomized-price null).

These tests are the **acceptance criteria** that turn "the backtest looks great" into "it provably didn't cheat."

---

## Recommended Build Roadmap (replaces the blueprint's 6 phases)

Built **interface-first** and **phase-gated** (each phase: define interfaces → write tests incl. bias guards → implement → CI green → short ADR). A **thin end-to-end vertical slice** comes first, then we broaden.

- **Phase 0 — Rails.** `uv` workspace scaffold, `alpha-core` types + Protocol interfaces, `CLAUDE.md`, pytest + bias-guard harness, mypy + CI. *(No trading logic yet — just the guardrails AI agents will build inside.)*
- **Phase 1 — Data spine.** Crypto ingest (ccxt + binance.vision) → Parquet + DuckDB; point-in-time corporate-action handling for equities; immutable hashed snapshots + manifest for reproducibility.
- **Phase 2 — Backtest core.** Adopt nautilus_trader; thin project wrappers; encode the **first strategy**; configure realistic frictions.
- **Phase 3 — Validation gauntlet.** The full pipeline above, with the randomized-price null as the first gate.
- **Phase 4 — Paper trading.** nautilus `SandboxExecutionClient` against a crypto testnet; same strategy code; reconciliation.
- **Phase 5 — Research UX.** marimo dashboards (equity curves, drawdowns, Monte Carlo fans), quantstats tear sheets, a CLI.
- **Phase 6 (later) — Broaden.** More assets, parameter optimization, meta-labeling ML *only if* a rules edge survives.

---

## Open Decisions (need owner input)

1. **Asset-class focus for v1.** Recommendation: build the engine **asset-agnostic** (nautilus is multi-asset) but do first validation + paper trading on **crypto** (the only fully-free, full-fidelity path), while keeping equities/FX on daily+minute bars. *Confirm this matches your trading interest — the blueprint's templates are intraday equity/index/FX setups, where free data is thinner.*
2. **First strategy to encode** for the vertical slice: one of the two templates, or a simpler liquid baseline (e.g., a vol-targeted momentum/MA-cross on a major crypto pair) to prove the pipeline before tackling the discretionary state machines.

---

## Detailed Reports

- `01-free-market-data.md` — free data sources per asset class
- `02-storage-layer.md` — DuckDB/Parquet/Polars vs ClickHouse/Arctic
- `03-backtesting-engine.md` — nautilus_trader vs LEAN/vectorbt/backtrader/…
- `04-statistical-validation.md` — Monte Carlo, CPCV, DSR/PBO, prop-firm math
- `05-paper-trading-feeds.md` — paper parity + free real-time feeds
- `06-strategy-encoding-ml.md` — the two templates as state machines, sizing, ML
- `07-architecture-ai-workflow.md` — repo layout, tooling, AI-build phasing, bias tests
