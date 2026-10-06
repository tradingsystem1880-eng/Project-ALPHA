# Connected edge research workspace

**Delivery state:** Completed

```json
{
  "schema_version": 1,
  "title": "Connected edge research workspace",
  "context": "Owner approved TrendSpider-inspired connected chart, conditions, advisory native Codex and result workflow. Core purpose is finding and testing tradable edge after costs, improving trading decisions and retaining negative findings.",
  "assumptions": [{"statement":"Native assistant uses existing local Codex authentication, with remote model inference and bounded attached context","verified_by":"Owner selected Local Codex in planning"}],
  "alternatives_considered": ["Separate billed model API rejected in favour of local Codex", "New chart engine unnecessary; retain Lightweight Charts", "Unrestricted autonomous agent deferred; structured advisory drafts use existing action paths"],
  "pre_mortem": ["Assistant answers attached to stale context", "Checklist and strategy semantics diverge", "Archive or snapshot context silently falls back to current store", "Concurrent tests collide", "Advisory text mistaken for admitted evidence"],
  "slices": [
    {"title":"Shared rule explanation projection","verify":"Focused rule/CLI/API equivalence and cutoff tests","expected":"Server-evaluated conditions preserve existing signal semantics","rollback":"Revert additive trace and route","status":"done"},
    {"title":"Connected chart workspace and result drilldown","verify":"Frontend models and browser journeys at supported viewports","expected":"Explicit context links chart, checklist, scans and trades","rollback":"Revert presentation slice","status":"done"},
    {"title":"Bounded local Codex assistant","verify":"Isolation, context, citation, draft, cancellation and unavailable-state tests","expected":"Advisory explanations and drafts without mutation authority","rollback":"Disable assistant entry point","status":"done"},
    {"title":"Evidence-centred results and indicator usability","verify":"Rendering and existing run/trade identity regressions","expected":"Costs, validation limits and negative outcomes remain explicit","rollback":"Revert presentation slice","status":"done"},
    {"title":"Integrated verification and review","verify":"Full gate, real browser journeys, independent review","expected":"Honest current-tree evidence and documented limitations","rollback":"Retain prior stable UI","status":"done"}
  ],
  "tier_impact": ["none"],
  "docs_to_update": ["CLAUDE.md", ".claude/rules/alpha-web.md", "apps/alpha-web/frontend/README.md", "docs/BUILD-STATUS.md", "docs/audit/2026-09-30-edge-workspace.md"],
  "out_of_scope": ["Live capital routing", "Autonomous promotion", "Arbitrary generated code", "Paid provider subscriptions", "New interval calculations", "Scheduled live alerts", "Automatic integration of the separate research branch"],
  "files": ["apps/alpha-cli/", "apps/alpha-web/", "packages/alpha-strategies/", "tests/", "docs/"]
}
```

Implementation ownership: root owns frontend, integration and docs; navigator owns additive rule trace/CLI/API/tests; assistant_backend owns new assistant CLI/service/web modules/tests. Existing dirty work is preserved. Numerical engines remain behind CLI; assistant inference receives bounded server-built context, never arbitrary browser market facts. No production dependency on benchmark code. Authority remains with CLI/ControlStore, point-in-time inputs and existing explicit owner actions.

Assistant public interface: new `/api/assistant` session and turn routes plus existing durable job status/stream/cancel where suitable. Explicit origin checks for mutations. Advisory persistence stays outside admitted research evidence. Rule explanation: `/api/rules/evaluate` relays `alpha rules explain`, including rule hash, cutoff, evaluation bar, operands, status and signal. Unsupported dataset contexts are unavailable rather than silently substituted.
