# Preserved feature reconciliation

**Current status — 2026-10-17:** The preserved feature and research deliveries were accepted through [PR #55](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/55) and [PR #56](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/56), each with seven successful required checks. This closes the authorized delivery scope only; private coverage remains UNVERIFIED and no standing exception is adopted.

Earlier dated status and incident entries are preserved as historical records.

**Historical delivery state before PRs #55 and #56:** In progress; local source recovery only.

```json
{
  "schema_version": 1,
  "title": "Finish preserved chart, CASH and PIT fixes without accepting policy changes",
  "context": "Owner requests finding originating chats and finishing still-needed local work. Verified original snapshot and binary diffs preserve shared index/source. Chart intent and cleanup adoption are established; CASH fix originated in committed 73fb2a94. Policy proposal and active mutation/maintainability owners remain separate.",
  "assumptions": [
    {
      "statement": "Source implementation already exists but integrated current-tree validation and release acceptance remain incomplete.",
      "verified_by": "Original snapshot has 1751 verified paths, historical plans/reviews and isolated source recovery."
    }
  ],
  "alternatives_considered": [
    "Discard preserved source rejected because requested useful features remain undelivered.",
    "Copying the full staged candidate rejected because it includes unaccepted policy and active mutation implementation."
  ],
  "pre_mortem": [
    "Mixed docs or generated artifacts silently introduce policy: verify control-plane base identity and regenerate artifacts after final sources.",
    "Heavy tests compete with active owners: coordinate one gate at a time.",
    "Historical receipts mistaken for current acceptance: bind fresh public checks and independent review to final tree."
  ],
  "slices": [
    {
      "title": "Recover accepted chart/CASH/PIT/hygiene source and regressions from verified preservation",
      "verify": "git diff --check; compare policy paths with main; compare source hashes with snapshot",
      "expected": "Only intended source/tests restored; policy and active owner changes absent; shared index remains unchanged",
      "rollback": "Remove isolated checkout; preserve snapshots and patches",
      "status": "done"
    },
    {
      "title": "Verify exact CASH rejection and PIT typed error contracts",
      "verify": "uv run pytest tests/integration/test_order_rejection.py tests/integration/test_frictions.py tests/bias_guards/test_cash_fee_affordability_future_poison.py tests/unit/test_pit_source.py tests/bias_guards/test_source_future_poison.py tests/holdout_seed/test_holdout_benchmark_defects.py tests/unit/test_runner.py tests/unit/test_core_types.py tests/unit/test_execution_trace_golden.py tests/unit/test_research_boundary.py -q",
      "expected": "Available cash includes exact rounded fees, close/next-open contract preserved, invalid future bars excluded and visible errors typed, artifact evidence retained",
      "rollback": "Revert isolated corrections only",
      "status": "done"
    },
    {
      "title": "Verify chart models, interactions, exports and generated assets",
      "verify": "npm run lint; npx tsc -b; npm run test:coverage; focused Playwright technical chart journey; npm run build",
      "expected": "Classic/Default grammar, native-volume viewport views, exact PNG labels and skipped-study disclosure verified without weakened budgets",
      "rollback": "Restore isolated recovered chart source from snapshot",
      "status": "done"
    },
    {
      "title": "Regenerate Atlas, complete public aggregate and independent review under existing acceptance rules",
      "verify": "uv run python scripts/gate.py full",
      "expected": "Fresh public checks and explicit private coverage limitation, exact-tree review; no publication or new exception",
      "rollback": "Preserve unaccepted local patch and report remaining acceptance dependency",
      "status": "done"
    }
  ],
  "tier_impact": [
    "protected",
    "dag"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    "docs/BUILD-STATUS.md",
    "docs/superpowers/plans/2026-10-10-preserved-feature-reconciliation.md"
  ],
  "out_of_scope": [
    "Standing private-suite policy and new exceptions",
    "Mutation/maintainability owner changes",
    "Research runtime feature promotion or private comparison datasets",
    "Feature publication or merge"
  ]
}
```


## Fresh focused verification

69 backend regressions pass. Both PNG omissions failed before correction, then all eight technical-chart browser tests pass with unchanged Classic/Default screenshots. Frontend lint/build/typechecks pass; full frontend unit coverage passes. Imports: 13 contracts kept; Python lint/format pass. Independent review then identified chart response rejection of CASH execution_rejection events and recorded-series PNG omission of visible value tags. The chart API/OpenAPI/frontend contract is extended; a real response regression fails before and passes after correction, and all 42 chart API tests pass. At that checkpoint before PRs #55 and #56, the first aggregate had been stopped for these repairs, so a fresh final-tree aggregate and independent acceptance still remained pending. Private standing-policy paths remain at main; original shared source/index remain preserved.


The native recorded-series Save PNG regression also fails before and passes after correction. Save/Copy/Open/menu/prompt remain native; only export compositing changes. Independent source inspection finds no issue in either integration correction. **At that historical checkpoint, before PRs #55 and #56, engineering acceptance remained BLOCK under the then-current absent-private-suite requirement.** PRs #55 and #56 later accepted the authorized delivery scope; private coverage remains UNVERIFIED. Final canonical full evidence is stored outside the source tree in `Project-ALPHA-reconciliation-evidence/feature-final-full.log` so verification receipts do not alter the frozen candidate. Quant-source verification scope is empty: no statistical module or validation/research source is changed; no empty-scope attestation is created. The original shared staged/unstaged/status bytes and 1,751 preserved path states were checked again and match recovery.
