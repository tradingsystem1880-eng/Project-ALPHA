# Canonical native result operator command

**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

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
