# Project ALPHA — v1 Design Spec (Vertical Slice)

**Date:** 2026-06-14
**Status:** Proposed (awaiting owner review)
**Companion docs:** [`research/00-SYNTHESIS.md`](../../../research/00-SYNTHESIS.md) (architecture ADR + full roadmap) and reports `01`–`07`.

---

## 1. Purpose

Project ALPHA is a **personal, $0-budget, Python, institutional-grade** quantitative research platform — backtesting + heavy-tailed statistical validation + (later) paper trading — **built by AI coding agents** and maintained by a solo owner.

**v1 goal:** prove the entire **research → validation loop end-to-end** with a single, honest, literature-backed strategy on a small multi-asset *daily* universe, with **look-ahead-safety and the validation gauntlet enforced by tests from day one**. v1 is the thin vertical slice that de-risks the whole platform.

The point of v1 is **not** to find alpha. It is to build machinery we can *trust* — so that when a later strategy looks good, we believe it.

## 2. Scope

**In:**
- Data ingestion + storage for a small **daily** universe (equity ETFs + crypto + FX majors)
- Point-in-time corporate-action handling (no pre-adjusted prices)
- `nautilus_trader` event-driven backtest with realistic fees + slippage
- **Time-series momentum** strategy with volatility-targeted sizing (fixed params, no optimization)
- Validation gauntlet subset: walk-forward OOS w/ costs · randomized-price null · block-bootstrap CI · bias-guard tests
- A tear sheet + a CLI to drive the whole loop

**Out (deferred):** paper/live trading, intraday & the discretionary blueprint templates (ORB, Rejection Block), ML/meta-labeling, large-scale parameter optimization, broad universes, real money.

## 3. Target Architecture (context)

The full platform is a **`uv` workspace** of small, strictly-typed `src/`-layout packages (hard import boundaries = the #1 reliability lever for AI-written code). v1 builds the subset marked ✅ below:

| Package | Role | In v1? |
|---|---|---|
| `alpha-core` | Domain types + `Protocol` interfaces + errors + time/PIT primitives. Depends on nothing. | ✅ |
| `alpha-data` | Ingestion adapters, Parquet store, DuckDB as-of query layer, immutable snapshots. | ✅ |
| `alpha-strategies` | Strategies as `nautilus` `Strategy` subclasses. | ✅ (TS momentum) |
| `alpha-backtest` | nautilus engine config/wrappers, cost models, run harness, result schema. | ✅ |
| `alpha-validation` | Walk-forward, Monte Carlo nulls, bootstrap CIs, metrics, tear sheets. | ✅ |
| `apps/alpha-cli` | CLI commands tying the loop together. | ✅ |
| `alpha-paper` | nautilus `SandboxExecutionClient` paper trading. | ❌ Phase 4 |

## 4. Repository Layout (v1)

```
Project-ALPHA/
├── pyproject.toml            # uv workspace root
├── uv.lock
├── CLAUDE.md                 # build conventions + guardrails for AI agents
├── .github/workflows/ci.yml  # ruff → mypy → pytest → bias_guards
├── packages/
│   ├── alpha-core/src/alpha_core/        # types, protocols, errors, pit/
│   ├── alpha-data/src/alpha_data/        # adapters/, store/, snapshot/, pit_view
│   ├── alpha-strategies/src/alpha_strategies/  # ts_momentum.py, sizing.py
│   ├── alpha-backtest/src/alpha_backtest/      # engine.py, costs.py, results.py
│   └── alpha-validation/src/alpha_validation/  # walkforward.py, montecarlo.py, bootstrap.py, metrics.py, tearsheet.py
├── apps/alpha-cli/src/alpha_cli/          # data, backtest, validate, report commands
├── tests/
│   ├── bias_guards/          # future-poison, causality/shift, PIT-only, survivorship
│   ├── unit/ · integration/  # per-package + full-slice on a tiny fixture dataset
├── research/                 # marimo notebooks + the 8 research reports (never imported)
├── docs/                     # specs, ADRs
└── data/                     # gitignored; raw/, snapshots/, manifests/
```

## 5. Components

Each unit has one responsibility, a defined interface, and explicit dependencies.

- **`alpha-core`** — `Bar`, `Instrument`, `Signal`, `Order`, `Fill`, `PortfolioState`; `Protocol`s: `DataSource`, `Strategy`, `Validator`; typed error hierarchy; `PointInTimeFrame.as_of(t)` primitive. *No external deps.*
- **`alpha-data`** — adapters (equities EOD: Stooq→Tiingo→yfinance; crypto daily: ccxt + binance.vision; FX daily: Dukascopy; macro: FRED); a Parquet store partitioned by `symbol/date`; a **separate bitemporal instrument-lifecycle table** (splits, dividends, and — generalized beyond equities — FX re-denominations and crypto symbol migrations / token splits, via an `action_type` enum; see §6.1); a DuckDB **as-of view** that applies actions *at query time* via `ASOF JOIN`, gating *availability* by knowledge-time and *application* by ex-date (§6.1); **immutable content-hashed snapshots + a JSON manifest recording adapter & parser version and source revision** (so a hash change is attributable to upstream-revision vs our code), plus an `alpha data verify` re-snapshot/integrity utility. *Strategies never see a raw DataFrame — only PIT-filtered data.*
- **`alpha-strategies`** — `TimeSeriesMomentum(Strategy)`; `sizing.py` (vol targeting). *Depends on `alpha-core` + nautilus.*
- **`alpha-backtest`** — nautilus `BacktestEngine` config, `FillModel` + fee tiers, a run harness, and extraction of trades/equity into a standard result schema. *Depends on `alpha-core`, `alpha-data`.*
- **`alpha-validation`** — purged/embargoed walk-forward splitter; randomized-price null (phase-randomization / stationary-block bootstrap of returns); block-bootstrap BCa CIs; metrics via `empyrical-reloaded`/`quantstats`; tear-sheet output. Runs are **parallelized** (process pool) and the randomized-price null is **tiered** — cheap returns-/trade-level resampling for the bulk distribution, plus a smaller set of full-engine runs on synthetic price paths as a faithfulness check. *Depends on `alpha-core`.*
- **`apps/alpha-cli`** — `alpha data pull|snapshot`, `alpha backtest run`, `alpha validate`, `alpha report`.

## 6. Data Flow

```
ingest → Parquet (raw, partitioned by symbol/date)
       → snapshot (immutable, content-hashed, + manifest)
       → DuckDB as-of view (point-in-time corporate actions)
       → PointInTimeFrame.as_of(t)        ← strategies can ONLY read here
       → nautilus data feed (chronological event bus)
       → Strategy emits Orders
       → engine fills with fees + slippage
       → trade log + equity curve (standard result schema)
       → validation gauntlet
       → tear sheet
```

## 6.1 Corporate actions & instrument lifecycle — the two-clock model

Corporate actions are the highest-risk component of `alpha-data`: every action carries *several* dates, and conflating them silently injects look-ahead or mis-adjustment. ALPHA keeps **two independent clocks**:

- **Valid time = ex-date** — the session on which the series mechanically changes (a split ratio applies to all bars *strictly before* ex-date; a cash dividend drops the price on ex-date). Governs **how** prices are adjusted.
- **Knowledge time = announcement/declaration date** — when the action first became knowable. Governs **whether** a backtest at simulated time `t` is even aware of it.

The DuckDB as-of view applies **two distinct filters that must never be merged**: an action is *available* only when `knowledge_time <= as_of`, and its price multiplier is *applied* to bars by `valid_time` (ex-date).

**Handling the dirty dates** (provider-reported date ≠ true market execution date):

1. **Store the full date taxonomy** per action — `announce_date`, `ex_date`, `record_date`, `pay_date` — never a single ambiguous "date".
2. **Canonicalize:** valid-time := `ex_date`; knowledge-time := `announce_date` when present, else a conservative fallback of `ex_date` (optionally minus a configurable lag), with a `knowledge_is_estimated` flag so approximations stay visible.
3. **Cross-source reconciliation:** ex-date and ratio/amount are verified across ≥2 providers (Tiingo / yfinance / EDGAR). Agreement within tolerance → accept; mismatch → **quarantine and flag**, never silently pick one source.
4. **Decouple price from cash:** the price series adjusts on ex-date; cash dividends are credited to the portfolio on `pay_date`. Different events in the engine.
5. **Same-day actions** (e.g. split + dividend sharing an ex-date) compound multipliers in a deterministic, documented order.
6. **Non-equity lifecycle events** use the *same* table with an `action_type` enum — FX re-denominations and crypto symbol migrations / token splits are PIT events too; `alpha-data` never assumes actions are equity-only.
7. **Provider revisions:** the snapshot manifest records `source_revision` + `parser_version` alongside the content hash, so any hash change is attributable to *upstream data revision* vs *our parsing logic* — not unexplained drift.

A dedicated bias guard pins a known action (the AAPL 4-for-1 split, 2020-08-31): pre-ex bars must scale by 1/4 **only** when `as_of >= announce_date`, be invisible before it, and leave the ex-date bar onward untouched.

## 7. The v1 Strategy — Time-Series Momentum

Fixed, pre-registered parameters (no optimization in v1 — that would overfit the first honest test):

- **Signal:** sign of the trailing `L`-bar return, skipping the most recent `S` bars (classic "12-1": `L ≈ 252` trading days, `S ≈ 21`). Long if positive, flat/short if negative.
- **Direction:** equities ETFs **long-flat**; crypto & FX **long-short** (no borrow constraints to model in a backtest; flagged for paper later).
- **Rebalance:** monthly (every ~21 trading days), on the close.
- **Sizing:** volatility targeting — scale each position to a constant annualized target vol using rolling realized vol / ATR, with a per-position and portfolio notional cap. Formula vetted in [report 06](../../../research/06-strategy-encoding-ml.md).
- **Costs:** per-asset-class fee + a volatility-scaled slippage assumption (conservative).

All parameters live in typed config; they are **constants for v1** and documented as the pre-registered hypothesis.

**Execution convention:** signals are computed on the **close of bar `t`** and orders execute at the **open of `t+1`** (market). This is look-ahead-free by construction (consistent with the causality guard) and sidesteps the closing-auction-price problem — free daily data exposes only the official OHLC, never the auction print — by never assuming we can transact *at* the decision-bar close. Slippage is modeled on the `t+1` open.

## 8. Validation Gates (v1 acceptance)

A v1 result is only reportable if it clears:

1. **Bias guards (CI-gated, must pass):** future-poison test (post-cutoff data → NaN must not change pre-cutoff outputs), causality/shift test (signal at `t` fills at `t+1`), PIT-only access enforced by construction.
2. **Walk-forward OOS with costs** — report the out-of-sample equity curve, not the in-sample fit.
3. **Randomized-price null** — the strategy's OOS Sharpe must beat the distribution produced by running the *same* strategy on randomized/bootstrapped price paths; report the percentile. (Directly tests the blueprint's own "patterns appear on random charts" admission.)
4. **Block-bootstrap BCa confidence interval** on Sharpe/CAGR — report the interval, never a bare point estimate.

(Deflated Sharpe + PBO are wired but only meaningful once we run parameter sweeps — deferred with optimization.)

## 9. Error Handling & Logging

- **No empty `except` blocks.** Every failure is logged with context and either handled or re-raised. (Blueprint quality rule, kept.)
- **Fail loud** on data gaps, unexpected NaNs, timestamp disorder, or any look-ahead-violation assertion — these are bugs, not conditions to paper over.
- Structured, auditable logging across data + execution layers (stdlib `logging` + `structlog`).

## 10. Testing Strategy

- **`pytest`**, with the **`bias_guards/` suite as the headline** acceptance criteria.
- **Property-based tests (Hypothesis)** for market-data invariants: OHLC consistency, monotonic non-duplicate timestamps, portfolio accounting identities.
- **Unit tests** per package against `Protocol` interfaces; **one integration test** running the full slice on a tiny committed fixture dataset (offline, deterministic).
- **Meta-test:** deliberately introduce a look-ahead and assert the future-poison guard *fails* — proving the guard actually guards. Must be deterministic (fixed seeds + fixtures) and run on every CI pipeline; a flaky guard is worse than none.
- **Universe-permutation invariance:** shuffling asset order must not change portfolio-level returns. Catches order-dependent sizing/allocation bugs. (If a later portfolio-level notional cap legitimately makes order matter, the tie-break must be explicit and deterministic — the test then pins *that* behavior.)
- **Point-in-time action guard:** a pinned known action (AAPL 4-for-1, 2020-08-31) adjusts pre-ex bars by 1/4 *only* when `as_of >= announce_date`, is invisible before it, and leaves the ex-date bar onward untouched (§6.1).
- **Architectural contract (CI):** `import-linter` enforces the package dependency DAG — `alpha-core` imports nothing internal, no cycles — as a hard CI gate, not a convention.
- **CI:** `ruff` → `mypy --strict` → `pytest` → bias-guard gate (GitHub Actions free tier).

## 11. Success Criteria (v1 is "done" when)

1. `alpha backtest run ts-momentum --universe v1` produces a trade log + equity curve over multi-year daily data across all three asset classes.
2. `alpha validate` runs walk-forward + randomized-null + bootstrap CI and emits a tear sheet.
3. All bias-guard tests pass in CI, **and** the meta-test confirms the future-poison guard fails on a planted leak.
4. **Reproducible:** the same data-snapshot hash yields byte-identical results.

## 12. Tooling & Conventions

`uv` workspace · Python 3.12+ · **Polars** default (pandas only at library edges) · **pydantic-settings** for typed config · **strict mypy/pyright** · **ruff** · **marimo** research notebooks (kept out of the package import path) · **git from Phase 0** · GitHub Actions CI.

## 13. Open Questions / Risks

- **nautilus_trader is heavyweight for daily bars — an accepted tradeoff.** We pay engine overhead (negligible at daily frequency — thousands of bars, not billions of ticks) to buy backtest↔paper parity and look-ahead-impossible-by-construction. The real risk is not latency but the **intrabar fill assumption**: to fill limit/stop orders *within* a bar, nautilus must assume an intrabar path (e.g. O→H→L→C), which can flatter results. Mitigations: v1 rebalances with **market orders at the `t+1` open** (no intrabar fills to assume), a test asserts fill price equals the intended reference, and an early **Phase-2 spike** validates daily-bar + mixed-asset (equity/crypto/FX) handling and end-of-day clock processing *before* we build on it.
- **FX daily data** via Dukascopy — verify coverage/reliability during Phase 1.
- **Long-short realism** — fine in a backtest; borrow/financing must be revisited before any paper/live phase.
- **Universe construction** — the v1 universe is hand-picked and *current-listings* based; survivorship bias is acknowledged and documented (free data limitation), and the survivorship guard test makes the assumption explicit.

## 14. Build Sequence (feeds the implementation plan)

Phase 0 (rails) → Phase 1 (data spine) → Phase 2 (backtest core + strategy) → Phase 3 (validation gauntlet) → Phase 5 (tear sheet + CLI). Phase 4 (paper) intentionally follows v1.
