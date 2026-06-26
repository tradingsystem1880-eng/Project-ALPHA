# ADR-0007: Content-addressed run id + independent child seeds

**Status:** Accepted
**Date:** 2026-06-26
**Deciders:** AI build agents (per `CLAUDE.md`)

## Context

Reproducibility is a success criterion: the same inputs must yield byte-identical results, and a result must be re-locatable from its inputs alone. Two design choices put this at risk if made naïvely. First, **run identity**: a timestamp- or UUID-based id makes every run unique even when nothing changed, so re-running can't reuse or verify a prior artifact and "did this change?" becomes unanswerable. Second, **randomness ordering**: the gauntlet runs several stochastic gates (two-tier null, Sharpe CI, CAGR CI, risk-of-ruin); if they draw from one shared global RNG, reordering, adding, or removing a gate shifts every downstream gate's draws and silently changes results.

## Decision

**Content-addressed run id.** `run_id` is the SHA-256 (first 16 hex chars) of the **canonical, sorted-key, separator-normalized JSON** of the run's parameters — symbol, fixed strategy params, costs, walk-forward geometry, seed. **No wall-clock** enters the payload, so the same inputs always produce the same id, the same artifact directory, and byte-identical output. Strategy params are parsed into a *sorted* tuple, so CLI argument order can't change the id.

**Independent child seeds.** All randomness derives from `AlphaSettings.random_seed` (default `7`). The gauntlet spawns one **independent child seed per stochastic gate** via `np.random.SeedSequence(master).spawn(n)`. `spawn` is deterministic and order-independent: each gate gets its own statistically-independent stream, so gate order can be changed without affecting any gate's results. Manifests are written byte-stable (sorted keys, `allow_nan=False` — non-finite values must already be `null`).

**Code anchors:**
- `apps/alpha-cli/src/alpha_cli/_runner.py:run_id_for` — `json.dumps(payload, sort_keys=True, separators=(",",":"), default=str)` → `sha256(...).hexdigest()[:16]`; docstring: "No wall-clock goes in, so re-running is byte-identical."
- `apps/alpha-cli/src/alpha_cli/_runner.py:parse_strategy_params` — sorts `name=value` params so order doesn't affect the id; `RunSpec` is frozen/picklable.
- `apps/alpha-cli/src/alpha_cli/_gauntlet.py:_child_seeds` — `[s.generate_state(1)[0] for s in np.random.SeedSequence(master).spawn(n)]`; `GauntletParams.seed` defaults to 7.

## Options Considered

### Option A: content-addressed id + `SeedSequence.spawn` children (chosen)

| Dimension | Assessment |
|---|---|
| Complexity | Low — a hash helper + a seed-spawn helper |
| Cost | Negligible |
| Correctness-risk | Very low — identity and randomness are both functions of inputs only |
| Fit | Excellent — satisfies the byte-identical-reproducibility criterion directly |

### Option B: UUID / timestamp run id + single global seed

| Dimension | Assessment |
|---|---|
| Complexity | Lowest |
| Cost | None up front |
| Correctness-risk | High — re-runs aren't deduplicable/verifiable; gate reordering changes all draws |
| Fit | Poor — defeats reproducibility and provenance |

### Option C: content-addressed id, but one global seeded RNG shared across gates

| Dimension | Assessment |
|---|---|
| Complexity | Low |
| Cost | None |
| Correctness-risk | Medium — reproducible only if gate *order* never changes; fragile to refactors |
| Fit | Medium — half the solution; couples results to execution order |

## Trade-off Analysis

Content addressing makes the run id a *function of the inputs*, which is what turns "reproducible" into something checkable: identical inputs collide on the same directory and must produce identical bytes, and a changed input visibly changes the id. The one subtlety — every field in the payload must serialize canonically and deterministically (hence sorted keys and sorted params) — is a small, contained discipline. Per-gate `SeedSequence` children solve the orthogonal ordering hazard that a single shared RNG (C) leaves open: without independent streams, a harmless-looking refactor that reorders gates would silently alter every result. The combined cost is two tiny helpers; the payoff is that both *what* a run is and *how* its randomness flows are pinned to inputs alone.

## Consequences

- **Easier:** verifying a run reproduces (re-run → same id → diff the manifest); caching/deduplicating identical runs; reordering or adding gauntlet gates without perturbing existing results.
- **Harder:** every value entering the id payload must be canonically serializable and wall-clock-free; non-finite stats must be normalized to `null` before a manifest is written (`allow_nan=False`).
- **Revisit when:** a new stochastic gate is added (give it its own spawned child seed, never reuse another gate's), or a new artifact field risks non-determinism (keep it out of the id payload or canonicalize it).
