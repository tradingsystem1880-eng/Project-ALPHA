# ADR-0005: A single point-in-time `as_of` firewall

**Status:** Accepted
**Date:** 2026-06-26
**Deciders:** AI build agents (per `CLAUDE.md`)

## Context

Look-ahead bias is the failure mode that makes a backtest a lie: a strategy that can see even one future bar will report an edge that does not exist. In an agent-built, multi-session codebase, "remember not to peek" is not a control — any new strategy or data path is a fresh opportunity to read the whole DataFrame and slice it wrong. We need look-ahead to be **structurally impossible**, concentrated at one seam that is cheap to audit and hard to bypass, rather than a property re-established by hand in every strategy.

## Decision

Route **all** data access for strategies and backtests through a single point-in-time accessor, `as_of(symbol, when)`, which **physically excludes future bars** (`filter(ts <= when)`) before returning anything. Strategies never touch the raw store; they read only typed `Bar` objects from this seam, and signals are computed on **trailing windows only**. The same accessor applies the knowledge-gated corporate actions (see [ADR-0004](0004-two-clock-corporate-actions.md)).

Back this with a CI-gated **bias-guard test pattern**: a *future-poison* test corrupts every bar strictly after `when` with absurd values and asserts `as_of(when)` returns byte-identical results — proving the firewall reads `<=` not `<` and ignores the future. A paired *non-vacuity* check edits the bar exactly at `when` and asserts the change **is** visible, proving the firewall isn't trivially returning nothing. Every data/strategy unit carries such a `@pytest.mark.bias_guard` test; the suite is the headline CI acceptance criterion.

**Code anchors:**
- `packages/alpha-data/src/alpha_data/pit.py:PointInTimeReader.as_of` — `read_bars(symbol).filter(pl.col("ts") <= when)  # firewall`; module docstring: "the look-ahead firewall. Strategies read ONLY here."
- `packages/alpha-data/src/alpha_data/source.py:PointInTimeSource.as_of` — typed-`Bar` seam over the reader (the interface strategies use).
- `tests/bias_guards/test_pit_future_poison.py`, `tests/bias_guards/test_source_future_poison.py` — future-poison + non-vacuity guards.
- `apps/alpha-cli/src/alpha_cli/_runner.py:load_bars` — even the full-history load goes through `PointInTimeSource` with a far-future `as_of`, not a raw read.

## Options Considered

### Option A: single `as_of` firewall + future-poison bias guards (chosen)

| Dimension | Assessment |
|---|---|
| Complexity | Low — one accessor, one test pattern |
| Cost | A cheap filter per read |
| Correctness-risk | Very low — future data is *physically absent* from what a strategy can see; guarded by tests that fail on regression |
| Fit | Excellent — one auditable seam for the platform's defining invariant |

### Option B: trust strategy code to slice trailing windows correctly

| Dimension | Assessment |
|---|---|
| Complexity | Low (no seam) |
| Cost | None |
| Correctness-risk | High — every strategy is a fresh chance to leak; impossible to audit centrally |
| Fit | Poor — exactly the discipline-not-control failure mode to avoid |

### Option C: pass the full frame but flag/mask future rows

| Dimension | Assessment |
|---|---|
| Complexity | Medium — masking convention to define and enforce |
| Cost | Carries future data in memory next to the code that must not read it |
| Correctness-risk | Medium–high — a mask is one `.fillna`/`.loc` mistake away from a leak |
| Fit | Poor — keeps the loaded gun in the room |

## Trade-off Analysis

Concentrating the invariant at one seam means there is exactly one place to get right and one place to audit, and the future-poison tests turn "did we get it right?" into a question CI answers on every push. Masking (C) is strictly worse than exclusion: if the forbidden data is never in the returned frame, no downstream mistake can read it; a mask leaves it present and one slip away from a leak. Trusting strategies (B) abandons control for the single most consequential bug class in the domain. The only cost of the chosen design — a filter per read and the discipline of always going through the accessor (even `load_bars` does) — is negligible.

## Consequences

- **Easier:** writing a new strategy without re-deriving look-ahead safety; auditing the whole platform's PIT correctness by reading one module + its guards; trusting a green result.
- **Harder:** any access pattern that *needs* the raw store (e.g. ingestion, snapshotting) must live below the seam in `alpha_data`, not in strategy/backtest code.
- **Revisit when:** a legitimately non-causal computation is needed (e.g. an offline labeling step) — it must be explicitly outside the strategy read path, never by relaxing `as_of`.
