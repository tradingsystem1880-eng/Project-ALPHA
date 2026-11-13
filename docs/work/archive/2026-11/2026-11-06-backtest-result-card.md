# Opt-in backtest result card

**Delivery state:** Completed — merged via PR #119

**Historical delivery state (as first recorded):** Implemented and independently source-reviewed; native UI base merged; delivery qualification and publication pending.

```json
{
  "schema_version": 1,
  "title": "Opt-in backtest result card",
  "context": "Render original plain language from the existing typed EquitySeries projection. Backend drawdown uses recorded equity and existing v3 artifact verification. No invented return, currency, confidence or STE certification.",
  "assumptions": [{"statement": "Implementation is authorized; native UI delivery integrates first.", "verified_by": "Delegated implementation handoff and owner request."}],
  "alternatives_considered": ["Full STE or narrative rewriting exceeds scope.", "Plain backtest manifests record no headline return metric or currency."],
  "pre_mortem": ["Legacy manifests bypass verification.", "Prior-run async values may leak.", "Malformed inputs may appear supported."],
  "slices": [
    {"title": "Evidence model and adversarial fixtures", "verify": "npm test -- src/panels/rundetail/backtestResultModel.test.ts", "expected": "Exact finite values, units and missing evidence behavior are deterministic.", "rollback": "Remove additive model and tests.", "status": "done"},
    {"title": "Opt-in card and selected-run lifecycle", "verify": "npm run build; focused browser checks; independent review", "expected": "Default-off preserves summary; enabled invalid evidence never falls back; stale responses are discarded.", "rollback": "Disable Backtest result card in Settings.", "status": "done"}
  ],
  "tier_impact": ["none"],
  "docs_to_update": ["CLAUDE.md", "README.md", "docs/BUILD-STATUS.md"],
  "out_of_scope": ["LLM rewriting", "STE compliance", "Empirical claims", "Authority changes", "Changing artifact verification"],
  "files": ["apps/alpha-web/frontend/src/panels/rundetail/backtestResultModel.ts", "apps/alpha-web/frontend/src/panels/rundetail/BacktestResultCard.tsx", "apps/alpha-web/frontend/src/panels/rundetail/index.tsx", "apps/alpha-web/frontend/src/state/settings.ts", "apps/alpha-web/frontend/src/App.tsx"]
}
```

Unrelated run summaries and loading errors retain their existing behavior. The card requires the existing API's verified v3 backtest manifest and equity artifact metadata.
It shows final server-computed drawdown as a fraction (zero at the running peak, negative below),
its readable whole-second UTC time (years 0000–9999), exact raw Unix seconds in Source,
and count of curve observations. Fractional display precision is explicitly disclosed. Numeric strings retain the JavaScript
value without rounding or percent conversion. No currency, risk-free rate, interval, cost model
or forecast is synthesized. The backend hash check establishes byte integrity; this display
adds no empirical validation. React escapes free text. Invalid, missing or failed evidence
produces an explicit unavailable state. Existing governance watermarks remain visible.

Revised focused results: 28 model/settings tests; all 481 frontend tests across 72 files;
coverage 93.23% statements, 83.87% branches, 96.41% functions, 95.13% lines.
Lint and production build passed. Ten minimum-viewport browser cases passed, including non-backtest scope and readable UTC regressions, after correcting
the initial fixture/settings-path failure; that failed run remains retained separately.
Independent source review APPROVE followed a required late-response test correction.
Canonical full gate, full browser matrix, Atlas regeneration/freshness and guarded publication
remain pending integration; this is not aggregate acceptance or production readiness.
README was updated for activation, rollback and evidence limits. No Python API/schema,
engine, DAG, point-in-time, randomness or statistical formula changed.

Parent inspection found and corrected the original global-summary scope regression and dropped
manual requirements. The revised card applies only to backtest-family summaries; other summaries
and load errors are unchanged. UTC charts, exact exports and no-project browsing remain required.
Unavailable output retains the selected run and known artifact hash. The original bundle and
receipts remain historical; revised final-source independent review is required separately.

Integration preparation: the isolated native-UI overlay uses published commit
`896b6779d8fa6de574e5a9a08853409ac196258f`, whose tree
`acb3cbe48a8995be34e5149524e2338b3260af0d` exactly matches the original UI bundle's supplied
tree. The Library download failed before archive bytes were available, so archive SHA-256
verification remains unavailable. The authored card code applies cleanly; only the append-only
build record required preserving both histories. The UI owner's funding-reconciled successor
is separate, and actual merged-head qualification remains required.

Overlay verification passed: 57 focused unit cases and all 487 frontend cases (74 files), lint,
production build and API freshness; 12 card/coexistence browser cases plus seven existing race
cases at chromium-minimum. Native panes use saved fixtures through an API-mocked shell; no
engine rerun or economic claim follows. Independent integration source review APPROVE has no
required findings. This preparation leaves actual merged-head qualification and publication pending.

Qualified UI/funding-head preparation: the successor isolated worktree starts at exact PR118
head `d5af71a226419eabb0a9bbb30a8016b585e7ab8e`, verified tree
`eaf3b458bc753d7970aaa4eb18adbae9650877b7`. This head is not merged main. The denied UI merge
is not retried. Existing funding and native UI source and history are preserved. The card code
and browser coexistence cases apply unchanged; only shared manual/build documentation needs
reconciliation. Focused results for this exact successor are recorded separately from predecessors.

Qualified-head focused results: 57 focused cases; all 487 frontend cases (74 files), lint,
production build/API freshness, 12 card/coexistence plus seven existing race browser cases passed.
Independent source review has no required findings. Actual delivery-head full qualification and
publication remain separate and pending; this does not authorize retrying the denied UI merge.

Merged-main reconciliation (2026-11-07): UI PR118 merged as
`8db344908f0530a03ed238c69bd9c1a40bf00afc`; fetched main tree
`eaf3b458bc753d7970aaa4eb18adbae9650877b7` exactly matches the prior qualified base.
The candidate transferred without source conflicts. Prior candidate tree
`6379c8fbc5a12971d5024fd196b75ea231b130ee` passed the canonical full gate across all six
components on one stable tree, including the configured 459-case browser matrix; backend
coverage was 93.15%. Its independent review and failure history remain preserved. This
historical pass does not establish post-merge CI completion or qualify later content/base
changes. Fresh README/review bindings and applicable delivery verification remain required.
Private holdouts remain UNVERIFIED; no protected contents were read or edited.
