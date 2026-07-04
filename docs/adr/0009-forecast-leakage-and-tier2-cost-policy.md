# ADR-0009: Pretrain-leakage policy + cache-first engine integration for model strategies

**Status:** Accepted
**Date:** 2026-07-04
**Deciders:** AI build agents (per `CLAUDE.md`)

## Context

Two honesty problems are unique to a *pretrained* forecaster and do not exist for the rule-based strategies.

**Leakage:** Kronos was pretrained on 12B+ K-lines across 45 exchanges through an **undisclosed** cutoff. Any backtest whose bars fall inside that window may be scoring *memorization*, not prediction — the exact failure mode the platform's PIT firewall exists to prevent, but occurring inside frozen model weights where no `as_of` accessor can reach.

**Cost:** the gauntlet's honest form would re-derive model signals everywhere. A naive per-bar model call inside `alpha validate` is ~63k forecasts (tens of hours on CPU); worse, strategies are rebuilt from pickled `RunSpec`s inside **spawn workers**, so a live torch model cannot ride into the engine at all.

## Decision

**Leakage: warn + flag, never block.** `AlphaSettings.forecast_pretrain_cutoff` defaults to `2025-08-02` (the Kronos paper's submission date — a conservative stand-in for the undisclosed truth). Every forecast artifact carries a `pretrain` block (`cutoff`, `overlap`, `overlap_start/end`); overlapping runs print a loud yellow warning in `forecast run`, `backtest run`, `validate`, and `alpha report`; `forecast eval` splits every skill metric **pre/post cutoff** and warns when zero post-cutoff origins exist. Research on historical data stays possible; the claim is labeled.

**Cost: cache-first.** The CLI precomputes signals at *exactly* the engine's rebalance-schedule indices into a content-addressed cache (`data_dir/forecasts/<key>`; key = sha256 over bars content, model identity+revisions+device, params, cadence, seed). The `kronos` strategy is a pure `SignalReplay` over that cache; ~56 model calls cover a 5-year daily backtest.

**Null-gate semantics (recorded, not hidden).** Tier-1 and the default Tier-2 (`tier2_mode="replay"`) rank the **observed signal sequence** against resampled paths — an *association* test of realized timing vs returns; they do not re-derive model signals on counterfactual data. `--tier2-mode model` does (per-synthetic-path caches computed in the parent; ~`tier2_paths ×` the model cost) and exists for final sign-off runs. The policy lands in `manifest["forecast"].tier2_policy` and the report output.

**Code anchors:**
- `alpha_cli/_forecast.py:pretrain_overlap`; `alpha_core/config.py:forecast_pretrain_cutoff`.
- `alpha_cli/_forecast_cache.py:{signal_indices, cache_key, ensure_forecast_cache}` — schedule pinned to `VolTargetStrategy` cadence by an instrumented-engine test.
- `alpha_cli/_surrogate.py:make_replay_surrogate` (Tier-1 semantics in its docstring); `alpha_cli/_synth.py:full_engine_null(spec_for_path=...)` (Tier-2 model mode); `alpha_cli/_gauntlet.py:GauntletParams.tier2_mode`.
- Bias guards: `tests/bias_guards/test_kronos_cache_no_lookahead.py` (index-keyed child seeds ⇒ cache prefix stability under future poison; engine-level proof that mutating future cache rows cannot bend past equity).

## Options Considered

### Option A: warn + manifest flag; cache-first engine; replay nulls with an honest model-mode opt-in (chosen)

| Dimension | Assessment |
|---|---|
| Complexity | Medium — cache layer + policy plumbing |
| Cost | ~56 model calls per backtest; model-mode Tier-2 priced explicitly |
| Correctness-risk | Low-medium — the replay null is weaker than recompute, but labeled everywhere |
| Fit | Excellent — keeps research usable while every artifact states its contamination |

### Option B: hard-fail on pretrain overlap

| Dimension | Assessment |
|---|---|
| Complexity | Low |
| Cost | Blocks nearly all historical research (the cutoff is recent) |
| Correctness-risk | Low leakage, high abandonment — users would bypass the tool |
| Fit | Poor for a research platform; the honest-labeling goal is met by A |

### Option C: no special handling (treat like any strategy)

| Dimension | Assessment |
|---|---|
| Complexity | None |
| Cost | None |
| Correctness-risk | High — silently inflated backtests presented as validated edge |
| Fit | Disqualifying — violates the fail-loud/no-look-ahead invariants in spirit |

## Trade-off Analysis

The residual risks are stated rather than solved: the cutoff is a **guess** (paper submission date) until upstream discloses it; replay-mode nulls can overstate robustness relative to full re-derivation. Both are visible in every manifest (`pretrain`, `tier2_policy`) and report line, and the expensive honest variants (`post-cutoff eval`, `--tier2-mode model`) are one flag away.

## Consequences

- **Easier:** kronos flows through backtest/validate/optim like any strategy; caches make reruns free; skill claims come pre-split by contamination.
- **Harder:** two run-dir namespaces (`forecast/` runs vs `forecasts/` signal caches — deliberate, documented); `RunSpec.forecast_cache` shifted run ids for new runs when it landed.
- **Revisit when:** upstream publishes the true training cutoff (tighten the default), or a multi-instrument engine makes per-path model Tier-2 cheap enough to default on.
