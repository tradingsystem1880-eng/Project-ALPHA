# ADR-0003: t+1 fills via a dual-event feed encoding

**Status:** Accepted
**Date:** 2026-06-26
**Deciders:** AI build agents (per `CLAUDE.md`)

## Context

The execution convention is a correctness invariant, not a tuning knob: a strategy decides on the **close of bar `t`** and must fill at the **open of `t+1`**. Free daily data exposes only the official OHLC, never the closing-auction print, so assuming a fill *at* the decision-bar close is both look-ahead-flattering and unachievable in practice. `nautilus_trader`'s default bar execution, however, fills market orders at the **bar close**. We need the engine to honor decide-close-`t` / fill-open-`t+1` without writing a custom matching engine and while keeping backtest↔paper parity.

## Decision

Encode the convention in the **data feed**, not in strategy code. For each daily session, `to_execution_feed` emits **two chronological events**:

1. An **open-priced `QuoteTick`** stamped at the session open (`bar.ts`). This is the price a market order — decided on the prior session's close — fills against. `slippage_bps` widens it into a side-aware half-spread around the open (`bid = open·(1−s)`, `ask = open·(1+s)`), so a market buy fills at the ask and a sell at the bid (conservative). The spread is quantized to `price_precision`, so a sub-tick slippage has no effect.
2. The **decision `Bar`** (full OHLC) stamped at the session **close**, i.e. `open + 23h` (`_SESSION_CLOSE_OFFSET_NS`). Any offset in `(0, 24h)` keeps `close(t)` strictly before `open(t+1)` for calendar-spaced daily bars, so the next price event a strategy sees after deciding on the close of `t` is the open of `t+1`.

The venue runs with **`bar_execution=False`** so that **only the quotes fill orders** — bars drive decisions exclusively. Equity is marked to market once per session on each open quote.

**Code anchors:**
- `packages/alpha-backtest/src/alpha_backtest/feed.py:to_execution_feed` (and `_SESSION_CLOSE_OFFSET_NS = 23 * 3600 * 1e9 ns`; `daily_bar_type`).
- `packages/alpha-backtest/src/alpha_backtest/engine.py:run_backtest` (`bar_execution=False`) and `_EquityRecorder` (subscribes to quote ticks, marks to market per session).

## Options Considered

### Option A: dual-event feed (open quote + close-stamped decision bar), `bar_execution=False` (chosen)

| Dimension | Assessment |
|---|---|
| Complexity | Low–medium — confined to the feed seam; no engine fork |
| Cost | One extra event per bar (quote); negligible at daily frequency |
| Correctness-risk | Low — t+1 fill is true *by construction*, independent of strategy code |
| Fit | Excellent — reuses nautilus event semantics; preserves backtest↔paper parity |

### Option B: nautilus default `bar_execution=True` (fill at bar close)

| Dimension | Assessment |
|---|---|
| Complexity | Lowest — no feed gymnastics |
| Cost | None |
| Correctness-risk | High — fills at the decision-bar close; look-ahead-flattering; assumes the unobtainable auction print |
| Fit | Poor — violates the execution invariant |

### Option C: custom fill/matching model intercepting orders

| Dimension | Assessment |
|---|---|
| Complexity | High — bespoke matching logic to write, test, and keep parity with paper |
| Cost | Higher engine overhead; more surface for subtle bugs |
| Correctness-risk | Medium — correct in principle but a large hand-rolled component |
| Fit | Poor — heavyweight for a convention the feed can express |

## Trade-off Analysis

Pushing the convention into the feed makes look-ahead-free execution a property of the *data*, not a discipline strategies must each implement correctly — the strongest possible guarantee for an agent-built codebase. It costs one extra event per bar and a small amount of conceptual surprise (the +23h decision-bar stamp), both trivial at daily frequency. The default close-fill (B) is rejected as a correctness violation. A custom matching model (C) achieves the same end with far more code and a parity risk against the paper venue; the feed encoding gets the same result while reusing stock nautilus execution semantics, which is exactly what preserves backtest↔paper parity.

## Consequences

- **Easier:** trusting any strategy's fills regardless of how it's written; backtest↔paper parity (the sandbox paper venue uses the same convention); modeling conservative slippage at one well-defined point.
- **Harder:** intrabar limit/stop fills (out of scope for the daily, market-order-at-open slice); the +23h decision-bar timestamp is a deliberate encoding artifact a reader must understand (documented in the feed module).
- **Revisit when:** intraday bars or limit/stop order types are added — the offset/encoding and the no-intrabar-fill assumption would both need revisiting.
