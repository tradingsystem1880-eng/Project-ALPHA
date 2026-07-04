# ADR-0006: Two-tier null model (returns-level + full-engine)

**Status:** Accepted
**Date:** 2026-06-26
**Deciders:** AI build agents (per `CLAUDE.md`)

## Context

The headline gauntlet gate asks: *is this strategy's out-of-sample Sharpe better than what the same strategy produces on price paths with no real structure?* A null model answers it — but two opposing pressures collide. To get a stable null distribution you want **many** resampled paths (hundreds–thousands), which is only affordable if each path is cheap. But cheap, vectorized return-level resampling is an **approximation** of the real backtest: it skips the actual engine, the t+1 fill model, intrabar OHLC, and close→open gaps. A null that is fast but unfaithful can clear a strategy that the real engine would reject (or vice-versa). A null that is faithful but runs the full engine thousands of times is too slow to be the bulk distribution.

## Decision

Use a **two-tier null**, and require the observed result to beat the threshold percentile in **both** tiers (conservative — pass only if both agree).

- **Tier 1 — returns-level surrogate (bulk, engine-free).** Resample the observed price *returns* and run a **vectorized surrogate** of the strategy directly on each return path. The surrogate reconstructs a synthetic close path, calls the strategy's *pure* signal on trailing closes only (look-ahead-free by construction: `closes[t+1]/closes[t]-1 = pr[t]`, so a weight from `closes[:t+1]` never peeks), sizes to target vol, and charges turnover costs. `--null-model` selects the resampler: `bootstrap` (stationary block bootstrap) or the fat-tailed parametric generators `student_t` / `garch` (more adversarial than a normal assumption). This is cheap, so it carries the large path count.
- **Tier 2 — full-engine on synthetic OHLCV (faithfulness check).** Block-bootstrap whole OHLCV *rows* (preserving intrabar OHLC consistency and close→open gaps), re-stamp them onto the original strictly-monotone session axis, and run the **real engine + walk-forward OOS** on each synthetic path — the exact code path the observed run used. Fewer paths, but a true faithfulness check that Tier 1's approximation didn't flatter the result.

A degenerate (flat / zero-variance) OOS short-circuits to a clean FAIL, never an undefined-Sharpe crash.

**Code anchors:**
- `apps/alpha-cli/src/alpha_cli/_gauntlet.py:run_gauntlet` — assembles both tiers (`randomized_price_null` / `parametric_price_null` for Tier 1; `full_engine_null` for Tier 2) and reports `("returns_level", "full_engine")`.
- `apps/alpha-cli/src/alpha_cli/_surrogate.py:make_surrogate` (and `make_ts_momentum_surrogate`) — the engine-free vectorized strategy analogue.
- `apps/alpha-cli/src/alpha_cli/_synth.py:synthetic_bar_paths` / `full_engine_null` — synthetic OHLCV generation + real-engine scoring (deterministic, order-preserving `ProcessPoolExecutor` with the `spawn` context to avoid nautilus/Cython fork deadlocks).

## Options Considered

### Option A: two tiers, both must pass (chosen)

| Dimension | Assessment |
|---|---|
| Complexity | High — two resampling schemes + a surrogate that must match the engine's logic |
| Cost | Tier 1 cheap × many paths; Tier 2 expensive × few — bounded total |
| Correctness-risk | Low — speed *and* faithfulness; the two cross-check each other |
| Fit | Excellent — directly answers "is this just luck?" with a conservative verdict |

### Option B: single cheap returns-level null only

| Dimension | Assessment |
|---|---|
| Complexity | Low |
| Cost | Lowest |
| Correctness-risk | Medium–high — engine/fill/OHLC effects unmodeled; can flatter or unfairly fail |
| Fit | Medium — fast but not trustworthy alone |

### Option C: single full-engine null only

| Dimension | Assessment |
|---|---|
| Complexity | Medium |
| Cost | High — full engine × enough paths for a stable distribution is slow |
| Correctness-risk | Low on faithfulness, higher on noise (few affordable paths → unstable percentile) |
| Fit | Medium — correct but impractical as the bulk distribution |

## Trade-off Analysis

The two tiers exist precisely because neither pressure can be conceded: Tier 1 buys the path count needed for a stable null, Tier 2 buys the faithfulness Tier 1 approximates away, and requiring **both** to pass means a strategy clears the gate only when the cheap-but-broad and the faithful-but-narrow views agree — a deliberately conservative posture for a platform whose whole purpose is to *not* believe luck. The cost is genuine implementation complexity: the surrogate must mirror the engine's economic logic, and the synthetic OHLCV generator must preserve intrabar structure and determinism under a process pool. That complexity is justified by the stakes — this is the gate that decides whether an "edge" is reported as real.

## Consequences

- **Easier:** trusting a passing verdict (it survived two independent nulls); swapping in more adversarial return distributions (`student_t`/`garch`) without touching Tier 2.
- **Harder:** keeping the Tier-1 surrogate economically faithful to the engine as strategies grow (a surrogate is required per strategy); Tier 2's parallelism must stay deterministic and order-preserving.
- **Revisit when:** a strategy's economics can't be faithfully vectorized into a surrogate (then lean harder on Tier 2), or when multi-instrument strategies need a panel-aware synthetic generator.
