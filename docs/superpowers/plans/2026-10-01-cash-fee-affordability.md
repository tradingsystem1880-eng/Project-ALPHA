# CASH execution affordability including fees

**Status:** Historical source-branch implementation receipt. Recovery onto the cleanup tree is in progress; original approval and gate do not attest the new tree. See [current cleanup plan](2026-10-08-repository-hygiene.md).
**Goal:** Prevent fee-bearing CASH buys from spending beyond available cash after close-t signals meet the actual t+1 opening execution quote. Preserve MARGIN behavior, sells, and the close-to-next-open decision contract.

**Evidence:** The retained Tier-2 replay has a CASH balance of $920,929.27 before a buy of 7,513 shares at $122.57 ($920,868.41 principal) plus a $92.09 commission, leaving cash at approximately -$31.23. The simulator applies fees after matching principal; the later truncation check detects the damage but does not prevent it.

## Slices

1. **Pin the execution invariant — complete.** Regressions cover the retained Tier-2 path-3 cash/quantity/price/fee shortfall, exact cent boundary on either side, zero-fee principal boundary, full curve completion, and explicit rejection evidence. Focused integration tests pass.
2. **Implement cash affordability at the shared strategy execution point — complete.** `run_backtest` configures the shared strategy by a narrow hook; at the opening quote, after venue quantity normalization and using actual free quote-currency cash, it rejects a CASH buy if principal plus the exact currency-rounded fee model does not fit. The target is unchanged and no partial resize is introduced. Typed rejection details live in `BacktestResult.execution_rejections`; the CLI persists them as `pretrade_rejections.parquet`, and the digest reconciles that count separately from venue order statuses. Generic strategies retain the loud truncation guard.
3. **Verify, review, and document — complete.** Future-poison and exact fee-order/cent-boundary tests cover execution timing and fee parity. Focused tests pass. The independent risk review approved the risk-tier changes, and the canonical full gate passed on the final implementation tree.

## Contracts and boundaries

- DAG remains `alpha_backtest -> alpha_core + alpha_data` and `alpha_strategies -> alpha_core + alpha_patterns`. The engine passes an optional execution-cost configuration by a narrow strategy protocol; no package imports the other.
- Look-ahead: close-t signal/target remains unchanged. The t+1 open quote and current account free balance may constrain execution only after the decision exists.
- Determinism: no randomness or additional data reads. Currency rounding and size increments must match the instrument/fee model.
- CASH buys are the only orders constrained. CASH sells and all MARGIN orders preserve current behavior. Oversized and fee-unaffordable orders remain counted as rejected; no partial resize is introduced.
- The engine's fail-loud truncated-run check remains as a final invariant for strategies that bypass the shared execution guard.

## Recovery boundary (2026-10-08)

The cleanup ports the engine/strategy guard, typed rejection records, existing CLI artifact persistence, and its regressions. `research_execution_digest.py` and its tests belong to the undelivered research runtime and are excluded; the historical digest receipt above is not a claim about current main. Hidden-suite review and a fresh aggregate gate remain required before integration.


## Local reconciliation (2026-10-10)

Recovered onto `reconcile/preserved-features` from the verified preservation snapshot. Original receipts remain historical. Standing private-suite policy and mutation/maintainability changes are excluded. Focused checks and a fresh exact-tree aggregate are pending; no release acceptance or publication is claimed.

Fresh focused checks:69 backend regressions and eight chart browser tests pass on the recovered candidate. Two additional PNG omissions were reproduced and corrected: annotation-outside-window disclosure and the volume legend swatch. Final aggregate and independent acceptance remain pending.
