# ADR-0007: Content-addressed run id + independent child seeds

**Status:** Superseded for v3 by ADR-0013 (retained for v1/v2 interpretation)
**Date:** 2026-06-26
**Deciders:** AI build agents (per `CLAUDE.md`)

## Context

Reproducibility is a success criterion: the same inputs must yield byte-identical results, and a result must be re-locatable from its inputs alone. Two design choices put this at risk if made naïvely. First, **run identity**: a timestamp- or UUID-based id makes every run unique even when nothing changed, so re-running can't reuse or verify a prior artifact and "did this change?" becomes unanswerable. Second, **randomness ordering**: the gauntlet runs several stochastic gates (two-tier null, Sharpe CI, CAGR CI, risk-of-ruin); if they draw from one shared global RNG, reordering, adding, or removing a gate shifts every downstream gate's draws and silently changes results.

## Decision

**Content-addressed run id.** `run_id` is the SHA-256 (first 16 hex chars) of the **canonical, sorted-key, separator-normalized JSON** of the run's parameters — symbol, fixed strategy params, costs, walk-forward geometry, seed. **No wall-clock** enters the payload, so the same inputs always produce the same id, the same artifact directory, and byte-identical output. Strategy params are parsed into a *sorted* tuple, so CLI argument order can't change the id.

**Historical child-seed policy.** All randomness derives from `AlphaSettings.random_seed` (default
`7`). Schema-v1/v2 gauntlets assigned independent child streams by position using
`np.random.SeedSequence(master).spawn(n)`. This is deterministic for a fixed ordered gate list, but
the assignment is **not** insertion- or reorder-stable: adding a family before an existing family
changes that family's child stream. ADR-0013 replaces positional assignment for new v3 work with
stable semantic namespaces. Manifests remain byte-stable (sorted keys, `allow_nan=False` —
non-finite values must already be `null`).

**Historical implementation note:**

- v1/v2 run IDs and seed results are already embedded in their immutable manifests; schema-agnostic
  `apps/alpha-cli/src/alpha_cli/run_store.py:read_manifest` preserves access without rewriting them;
- `apps/alpha-cli/src/alpha_cli/_runner.py:parse_strategy_params` still sorts `name=value` input, but
  the current `run_identity_for` writer implements ADR-0013 and must not be cited as an ADR-0007
  writer; and
- all current v3 identity and semantic seed derivation is anchored by ADR-0013. Positional child
  assignment is retained here only to interpret historical v1/v2 evidence.

## Options Considered

### Option A: content-addressed id + positional `SeedSequence.spawn` children (historical choice)

| Dimension | Assessment |
|---|---|
| Complexity | Low — a hash helper + a seed-spawn helper |
| Cost | Negligible |
| Correctness-risk | Medium — deterministic for a fixed list, but family insertion changes assignments |
| Fit | Good for schema v1/v2; superseded by semantic namespaces for v3 |

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

Content addressing makes the run id a *function of the inputs*, which is what turns "reproducible"
into something checkable. Per-gate child streams prevent gates from consuming one shared RNG, but
positional assignment did not fully solve family insertion/reordering. ADR-0013 closes that
remaining hazard by deriving each child from its semantic namespace while preserving the historical
v1/v2 interpretation.

## Consequences

- **Easier:** verifying a fixed schema-v1/v2 run reproduces (re-run → same id → diff the manifest);
  caching/deduplicating identical runs.
- **Harder:** every value entering the id payload must be canonically serializable and wall-clock-free; non-finite stats must be normalized to `null` before a manifest is written (`allow_nan=False`).
- **Revisit when:** interpreting a historical v1/v2 run; all new v3 seed and identity changes follow
  ADR-0013.
