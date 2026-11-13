# Full Qlib model zoo and fold-by-fold counterfactual retraining (W11/W12)

**Status:** Scoped
**Rough size:** XL

## Problem / why

Only a bounded Qlib subset is implemented (fold-local Alpha158-style features, LightGBM, a rank
ensemble; five backends/eight recipes locally gated). Full counterfactual fold retraining is not
implemented, and the W11 refit packet is blocked on governed execution and statistical
qualification. W12 asks for a worker-only Qlib 0.9.8 migration and all 25 pinned model entries.

## What "done" looks like

- W11: every fitted component refit within folds and counterfactuals on real data, with
  sizing/common-risk and full cash/dividend/opportunity accounting.
- W12: the isolated worker on Qlib 0.9.8 and all 25 declared model entries with their pinned
  variants, delivered in separately reviewable waves.

## Dependencies

W09 (current Qlib routed through the native case), W10 controls, contract/position data. The
blocked [W11 refit plan](../../work/2026-10-26-qlib-w11-refit/02-plan.md) is the live engineering packet.

## Sources

- [Checklist W11](../../context/feature-readiness-checklist-2026-10-27.md#w11-qualify-retraining-and-sizing-risk-experiments) and [W12](../../context/feature-readiness-checklist-2026-10-27.md#w12-migrate-qlib-and-deliver-model-waves)
- [Checklist: All 25 declared model entries](../../context/feature-readiness-checklist-2026-10-27.md#all-25-declared-model-entries)
- [README: Implemented scope and limits](../../../README.md#implemented-scope-and-limits)
- [Qlib worker README](../../../workers/qlib/README.md)
