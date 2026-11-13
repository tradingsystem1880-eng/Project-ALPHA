# Canonical native result operator command

**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

```json
{
  "schema_version": 1,
  "title": "Canonical native result operator command",
  "context": "Canonical v9 W02/T10 requires attempt-bound result/receipt recovery and wrong/missing artifact rejection; add `alpha research diagnostic native-result` to the existing read-only non-admitted command group, reusing the module CLI's recovery. Front block added 2026-11-13 during the plan status pass; every field restates this plan's own text. Implementation slices are marked done because the named code and tests exist in candidate a631e8e7; review slices stay pending unless the text records a review.",
  "assumptions": [
    {
      "statement": "The read-only non-admitted diagnostic group is already excluded from the launchable catalog.",
      "verified_by": "Plan text; no frontend/info/science command edits needed."
    },
    {
      "statement": "Predecessor 8eb6c160 and all earlier exports are preserved.",
      "verified_by": "Plan text 'Preserve 8eb6c160...'."
    }
  ],
  "alternatives_considered": [
    "Another inspector or loop; rejected in favour of reusing the existing module CLI recovery."
  ],
  "pre_mortem": [
    "Raw errors/logs or non-completed results could leak through the operator output; only completed artifact recovery exposes receipt/result.",
    "Registration could construct AlphaSettings or call models/providers; tests assert it does not."
  ],
  "slices": [
    {
      "title": "Retain validated receipt and trace; thin CLI binding",
      "verify": "Exit/status projection tests: completed 0, invalid 2, unavailable 3",
      "expected": "Explicit root/job/source/runtime/mode; owner/profile/spec/hash provenance kept",
      "rollback": "Not stated in the original plan text; revert this slice's candidate changes.",
      "files": [
        "apps/alpha-cli/src/alpha_cli/native_stock_cmds.py"
      ],
      "status": "done"
    },
    {
      "title": "Idempotent registration through main._group",
      "verify": "CLI discoverability, non-launchable classification and fail-closed output tests",
      "expected": "Registered alongside the lazy research add-on without settings, model/provider calls or another data source",
      "rollback": "Not stated in the original plan text; revert this slice's candidate changes.",
      "files": [
        "apps/alpha-cli/src/alpha_cli/main.py"
      ],
      "status": "done"
    },
    {
      "title": "Actual console subprocess journey and independent review",
      "verify": "Fresh disposable synthetic native job: checkpoint stop, remaining stages, owner validation, new-process durable read; changed bytes, missing owner binding, late cancellation",
      "expected": "Exit/status/provenance verified and no result promotion",
      "rollback": "Not stated in the original plan text; revert this slice's candidate changes.",
      "files": [],
      "status": "pending"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "docs/operations/native-stock-inspection.md"
  ],
  "out_of_scope": [
    "Any launching feature; the operator never creates job, owner, reservation or allowance.",
    "T07 resume and accounting/policy/guard/schema/worker semantic changes.",
    "Statistics, as-of or market data changes.",
    "Broad/full or private gates, publication, transfers and installs.",
    "Shared generated outputs and shared README/CLAUDE documentation."
  ]
}
```

Canonical v9 W02/T10 (Library libfile_181ac6079dcc8191b222b76c1f10bf17) requires
attempt-bound result/receipt recovery and wrong/missing artifact rejection. Preserve
8eb6c16020136992a5701b1f3598515fc2dd0bbd and all predecessors/exports.

Existing module CLI exposes hashes/status but discards validated receipt/trace values
and is absent from the canonical alpha console tree. Reuse its recovery, not another
inspector/loop. Add `alpha research diagnostic native-result` to the existing read-only
non-admitted command group. That group is already excluded from launchable catalog, so
no frontend/info/science command implementation edits or new run authority are needed.

1. Retain receipt and trace already validated from the exact bounded byte snapshot.
   Add thin callback-local CLI binding with required explicit root/job/source/runtime/mode.
   Project completed/0, invalid/2, unavailable/3; expose receipt/result only for completed
   artifact recovery. Keep owner/profile/spec/hash provenance, never raw errors/logs.
2. Register idempotently through main._group alongside its existing lazy research add-on.
   Test CLI discoverability, nonlaunchable classification and fail-closed output without
   AlphaSettings construction, model/provider calls or another data source.
3. Execute actual alpha console subprocess against fresh disposable synthetic native job:
   existing checkpoint stop→same-guard remaining stages→owner validation/journal→newprocess
   reads durable result. Exercise changed bytes, missing owner binding and late cancellation;
   verify exit/status/provenance and no result promotion. Focused tests/independent Codex
   review (Claude unavailable unless an existing authorized route appears).

No launching feature; fixture preparation uses existing synthetic admission helpers only
in public tests. Operator itself never creates job/owner/reservation/allowance, no settings
or env inference. No T07 resume, accounting/policy/guard/schema/worker semantic changes.
DAG unchanged; no statistics/as-of/market data changes. Dedicated operator guide updated;
README/CLAUDE no_change: shared docs outside scope and this remains unqualified synthetic
engineering. No broad/private gates, protected contents, installs/transfers/publication.
A single base→latest cumulative source route will be prepared once after final source.
