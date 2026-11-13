**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

```json
{
  "schema_version": 1,
  "title": "C04 risk metric-basis JSON, API and visible consumer integration",
  "context": "Adopt preserved35c4 CLI disclosure through negotiated HTTP API, strict provenance model and both actual risk views; maintain exact legacy payloads, unchanged metric calculations/defaults and explicit unknown capital/flow evidence.",
  "assumptions": [
    {
      "statement": "Preserved35c4efcb source is genuinely present and reproduced before edits; prior8b/C04/RR01/placebo candidates remain unchanged.",
      "verified_by": "git apply --index saved candidate patch; initial git write-tree35c4efcb in separate worktree."
    },
    {
      "statement": "Risk-specific API/model/UI files are cleared; reserved native/inspector/shared shell/CSS/README/SPA paths remain untouched.",
      "verified_by": "Parent relayed exact ownership boundaries before model/frontend edits; final path audit."
    },
    {
      "statement": "Existing CLI --json and HTTP defaults must remain legacy-compatible; absent metadata is not proof of verified capital/flows.",
      "verified_by": "Real HTTP-to-CLI public tests compare raw payloads and serialization, omitted/null legacy cases; visible legacy fallback."
    },
    {
      "statement": "Browser checks mount actual consumers against serialized real synthetic API responses using existing Chromium/Vite, not compiled production SPA.",
      "verified_by": "Risk-specific Playwright harness and actual typed API fixture capture; no shared assets rebuild or model/backend simulation."
    }
  ],
  "alternatives_considered": [
    "Use explicit CLI flag and HTTP query negotiation; do not unconditionally add fields to exact-schema legacy responses.",
    "Use one risk-only display component in both consumers; do not modify shared panel primitives/CSS/shell or duplicate financial calculations.",
    "Reuse actual typed response model and existing CLI subprocess; do not reconstruct unavailable owner candidates or create a separate reporting framework."
  ],
  "pre_mortem": [
    "Metadata is stripped by a strict model or arrives without the CLI flag: capture real argv/raw payload and assert HTTP serialization preserves it.",
    "Legacy absence/null could appear verified: show explicit unknown-basis fallback; keep missing fields absent through exclude_unset.",
    "Malformed/unsupported values could turn into verified conventions: typed server validation and defensive render reject them without leaking source values.",
    "Old-run anchor could remain while another run loads: clear run-detail state and guard both views by report.run_id."
  ],
  "slices": [
    {
      "title": "Preserved CLI version1 producer and compatibility",
      "verify": "Existing actual CLI JSON/human public tests and predecessor identity",
      "expected": "Legacy default unchanged; opted block explicitly unknown, no invented capital/return observations",
      "rollback": "Retain preserved35c4 predecessor and receipts",
      "files": [
        "apps/alpha-cli/src/alpha_cli/risk_cmds.py",
        "tests/integration/test_c04_risk_anchor_disclosure.py"
      ],
      "status": "done"
    },
    {
      "title": "Negotiated typed HTTP consumer",
      "verify": "Real CLI subprocess HTTP tests, raw serialization parity, legacy absent/null and malformed metadata cases",
      "expected": "Query opt-in reaches producer; typed block retained; old default shape unchanged; invalid data yields established fixed422 envelope",
      "rollback": "Revert backend/API model delta to35c4",
      "files": [
        "apps/alpha-web/src/alpha_web/_risk.py",
        "apps/alpha-web/src/alpha_web/api/risk.py",
        "apps/alpha-web/src/alpha_web/api/models.py",
        "apps/alpha-web/frontend/openapi.json",
        "apps/alpha-web/frontend/src/api/generated.ts",
        "tests/integration/test_c04_web_metric_basis.py"
      ],
      "status": "done"
    },
    {
      "title": "Visible risk-specific UI adoption",
      "verify": "Eight component render cases, actual mounted run-detail/monitor Chromium cases and frontend typecheck",
      "expected": "Both views request disclosure and render conventions/unknown evidence; legacy fallback/malformed handling/run-switch clearing",
      "rollback": "Revert client/risk-specific component and two consumer hunks; regenerate prior API types",
      "files": [
        "apps/alpha-web/frontend/src/api/client.ts",
        "apps/alpha-web/frontend/src/panels/RiskMetricBasis.tsx",
        "apps/alpha-web/frontend/src/panels/RiskMetricBasis.test.ts",
        "apps/alpha-web/frontend/src/panels/RiskMonitor.tsx",
        "apps/alpha-web/frontend/src/panels/rundetail/Risk.tsx",
        "apps/alpha-web/frontend/e2e/fixtures/riskMetricBasis.json",
        "apps/alpha-web/frontend/e2e/risk-metric-basis.html",
        "apps/alpha-web/frontend/e2e/riskMetricBasisHarness.tsx",
        "apps/alpha-web/frontend/e2e/risk-metric-basis.spec.ts",
        "apps/alpha-web/frontend/playwright.risk-basis.config.ts"
      ],
      "status": "done"
    },
    {
      "title": "Independent review and bounded evidence",
      "verify": "Scoped lint/types, API freshness/authority, public tests and independent Codex review on exact tree",
      "expected": "Actual receipts and preserved trees; source candidate only, no formal/full/product acceptance",
      "rollback": "Revert successor-only delta to35c4; retain all original candidates and receipts",
      "files": [
        "apps/alpha-cli/src/alpha_cli/risk_cmds.py",
        "apps/alpha-web/src/alpha_web/_risk.py",
        "apps/alpha-web/src/alpha_web/api/risk.py",
        "apps/alpha-web/src/alpha_web/api/models.py",
        "apps/alpha-web/frontend/openapi.json",
        "apps/alpha-web/frontend/src/api/generated.ts",
        "apps/alpha-web/frontend/src/api/client.ts",
        "apps/alpha-web/frontend/src/panels/RiskMetricBasis.tsx",
        "apps/alpha-web/frontend/src/panels/RiskMetricBasis.test.ts",
        "apps/alpha-web/frontend/src/panels/RiskMonitor.tsx",
        "apps/alpha-web/frontend/src/panels/rundetail/Risk.tsx",
        "apps/alpha-web/frontend/e2e/fixtures/riskMetricBasis.json",
        "apps/alpha-web/frontend/e2e/risk-metric-basis.html",
        "apps/alpha-web/frontend/e2e/riskMetricBasisHarness.tsx",
        "apps/alpha-web/frontend/e2e/risk-metric-basis.spec.ts",
        "apps/alpha-web/frontend/playwright.risk-basis.config.ts",
        "tests/integration/test_c04_risk_anchor_disclosure.py",
        "tests/integration/test_c04_web_metric_basis.py",
        "docs/work/2026-11-08-c04-risk-anchor-disclosure/02-plan.md"
      ],
      "status": "done"
    },
    {
      "title": "Disposable compiled SPA and live synthetic risk acceptance",
      "verify": "Explicit tsc noEmit; Vite --outDir disposable/spa; Playwright risk-live.config.ts against unchanged create_app API and real CLI; scoped lint and independent advisory review",
      "expected": "Both compiled risk views negotiate and render real disclosure; genuine legacy payload fallback via controlled request downgrade; invalid source/request rejected; reserved assets unchanged",
      "rollback": "Remove three acceptance-only files and this amendment; production bytes remain preserved13b0402",
      "files": [
        "scripts/run_c04_risk_live_acceptance.py",
        "apps/alpha-web/frontend/playwright.risk-live.config.ts",
        "apps/alpha-web/frontend/e2e/risk-live.spec.ts"
      ],
      "status": "done"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "docs/work/2026-11-08-c04-risk-anchor-disclosure/02-plan.md"
  ],
  "out_of_scope": [
    "Production metric calculations/defaults/statistical or admission policy; true baseline/cash-flow/UTC chronology verification",
    "Reserved native producer/signal_replay/native demo/UI/journey/browser/generatedSPA, inspector paths, shell/documents/shared panels/CSS/frontend README/BUILD-STATUS",
    "Protected tests/oracles/holdouts/transcripts, actualfits/studies/model/provider/marketdata, installs/broadfullgates/Atlas/commit/push/transfer/publication/live",
    "Claiming complete C04/canonicalv9/native numerical equivalence or scientific/product acceptance"
  ],
  "files": [
    "apps/alpha-cli/src/alpha_cli/risk_cmds.py",
    "apps/alpha-web/src/alpha_web/_risk.py",
    "apps/alpha-web/src/alpha_web/api/risk.py",
    "apps/alpha-web/src/alpha_web/api/models.py",
    "apps/alpha-web/frontend/openapi.json",
    "apps/alpha-web/frontend/src/api/generated.ts",
    "apps/alpha-web/frontend/src/api/client.ts",
    "apps/alpha-web/frontend/src/panels/RiskMetricBasis.tsx",
    "apps/alpha-web/frontend/src/panels/RiskMetricBasis.test.ts",
    "apps/alpha-web/frontend/src/panels/RiskMonitor.tsx",
    "apps/alpha-web/frontend/src/panels/rundetail/Risk.tsx",
    "apps/alpha-web/frontend/e2e/fixtures/riskMetricBasis.json",
    "apps/alpha-web/frontend/e2e/risk-metric-basis.html",
    "apps/alpha-web/frontend/e2e/riskMetricBasisHarness.tsx",
    "apps/alpha-web/frontend/e2e/risk-metric-basis.spec.ts",
    "apps/alpha-web/frontend/playwright.risk-basis.config.ts",
    "tests/integration/test_c04_risk_anchor_disclosure.py",
    "tests/integration/test_c04_web_metric_basis.py",
    "docs/work/2026-11-08-c04-risk-anchor-disclosure/02-plan.md",
    "scripts/run_c04_risk_live_acceptance.py",
    "apps/alpha-web/frontend/playwright.risk-live.config.ts",
    "apps/alpha-web/frontend/e2e/risk-live.spec.ts"
  ]
}
```

**Delivery state:** Completed for bounded source integration and isolated live-risk acceptance. Shared production asset composition and formal qualification remain pending. See the dated acceptance amendment below; earlier source-mounted receipts remain historical.

## C04 and preserved baseline

[C04](../../context/feature-readiness-checklist-2026-10-27.md) covers independent Qlib accumulation/annualization/benchmark/drawdown conventions and initial wealth, without universal zero-return padding. The Git mirror identifies version3; full canonicalv9 parity is not claimed. This successor uses actual source present locally, reproducing preserved35c4efcb706d9cae4dceaad7172d856cd9d73c55 exactly before edits on main snapshot3f7b23185c29b2542605bd41b9485016c2ef3e79. It does not reconstruct or compose unavailable owner candidates.

## Actual production chain and compatibility

Frontend api.riskScenario explicitly sends include_metric_basis=true → /api/risk/scenario forwards that option → _risk.scenario adds --include-metric-basis to the real CLI invocation → existing recorded-equity/scenario computation → CLI version1 provenance block → strict RiskMetricBasis/RiskReport validation → API JSON serialization → one risk-only RiskMetricBasis display component mounted by both RiskMonitor and run-detail Risk.

Legacy CLI --json is unchanged. Legacy HTTP requests omit the new query and retain their prior JSON shape. Optional model default None plus exclude_unset preserves an absent block as absent, while explicit null remains null. Both forms get an explicit unknown-basis UI fallback; absence never implies verification. The route validates the full response and returns the established fixed422 API-error envelope for malformed metadata without exposing raw values. The current frontend opts in rather than silently changing all existing API clients.

Version1 declares the first recorded row actually used (value, ISO representation and recorded units), unknown initial-capital/external-flow evidence, compounded simple-return accumulation, non-positive fractional drawdown from each scenario wealth path's peaks including its normalized initial anchor, no benchmark adjustment by this projection, and pre-anchor losses not measured. Annualization remains existing periods_per_year. Stress-path peaks are hypothetical; only the base reconstructs the recorded path. Parsing the anchor timestamp verifies its syntax, not timezone/chronology or true initial-capital provenance. No zero return, inferred cash amount, cash-flow adjustment or upstream metric is introduced.

Later-valuation fixture[900,950,1000] with declaredcash1000 keeps source anchor900, base drawdown0 over that recorded path, and totalreturn1/9. UI explicitly says capital/flow coverage is unknown. Explicit[1000,900,1000] and normalized[1,.9,1] remain legitimate distinct test cases. Existing return/annualization/benchmark conventions and all numerical scenarios are unchanged.

## Tests and evidence boundary

Public backend cases run the real alpha subprocess under TestClient, capture actual argv/raw JSON, and compare every serialized field. Cases cover legacy absent/null, unsupported version including bool, invented verified states, invalid/nonfinite/bool anchors, invalid timestamp, accumulation/drawdown mismatch and unknown fields. The error envelope contains no raw invalid metadata.

Frontend component tests render actual React markup. Risk-specific Chromium tests mount each actual consumer and its actual API client against fixture JSON serialized by the real HTTP/CLI/model path. They verify visible unknown/convention/anchor text, negotiated requests, run-switch loading without stale anchors, legacy fallback and malformed cached data. The Vite harness overrides base only for tests, uses installed Chromium, and never builds shared SPA assets. It is a source-mounted consumer test, not a completed built-application journey or live-backend browser acceptance.

Generated OpenAPI changes are limited to RiskMetricBasis, RiskProvenance and /api/risk/scenario; generated TS types mirror these. No new framework or dependency is installed. Production SPA rebuild/composition remains with its owner; the served compiled assets are not changed by this candidate.

## Ownership and remaining qualification

The parent cleared risk-specific models/API/client/consumer changes after receiving native and inspector reservations. Those reserved paths, shell/documents.ts, generic shared panel components, shared CSS, frontend README, BUILD-STATUS and generated SPA remain untouched. The new shared display is risk-specific, not a generic panel primitive. Scoped browser harness/config/fixture files are risk-only.

No true baseline/cash-flow proof, native installed-runtime reconciliation, full C04/v9/scientific/product acceptance, protected suites, full gate, actual fits/studies/models/providers, owner data, installs, Atlas, commit/push/PR, external transfer or live action occurs. Independent review is advisory rather than a formal gate attestation. Parent serializes plan ordering, source composition, production asset rebuild and any separately authorized qualification. README reviewed without edits: existing setup/command guidance remains accurate and the reserved README is not changed; exact new behavior and limits are recorded here.

Pinned source-only audit from the preserved slice: worker pins pyqlib0.9.7. Native risk_analysis defaults and formulas differ from ALPHA and are not silently replaced here. Primary reference: https://raw.githubusercontent.com/microsoft/qlib/v0.9.7/qlib/contrib/evaluate.py ; upstream record consumer: https://raw.githubusercontent.com/microsoft/qlib/v0.9.7/qlib/workflow/record_temp.py . Those references do not validate a runtime comparison or empirical acceptance.


## 2026-11-08 disposable compiled-SPA/live-risk acceptance amendment

Preserved predecessor tree13b0402bd555b2134f26d42b1448d6d3858ca011 was reproduced exactly before this amendment in separate branch codex/c04-risk-live-20261108 at main snapshot3f7b23185c29b2542605bd41b9485016c2ef3e79. No application source or financial calculation changed. The only successor additions are a risk-specific synthetic server helper, Playwright configuration and live-browser spec, plus this plan amendment. Earlier source-mounted/SSR/backend receipts keep their original scope; they are not relabeled as live-browser results.

TypeScript noEmit passed. Vite8.1.5 compiled the actual full application source into /workspace/scratch/c04-risk-live-20261108/spa, never tracked static/app. The installed Vite/TypeScript/Playwright/React versions match this checkout's lockfile; no install occurred. Build emitted existing Bokeh direct-eval and large-chunk warnings. The normalizer and standard asset-freshness/full gate were not run; this is an isolated raw Vite build, not canonical generated-asset publication. A SHA256/size manifest covers all52 built files (4,804,164 bytes). Browser checks compare served JavaScript bytes with those isolated files.

The helper serves disposable static assets alongside the unchanged create_app backend, sets the successor source roots for both backend and real alpha CLI child, and uses only an isolated temporary synthetic store. Three labeled SYNTHETIC_C04_NO_FIT runs contain independently constructed Parquet curves [900,950,1000], [1000,900,1000] and [NaN,950,1000]. Their actual file hashes bind the source-artifact assertions; declared cash1000 deliberately cannot prove that900 is true initial capital. No fit or study runs. GET/HEAD-only isolation permits risk-scenario/run reads and blocks unrelated API requests/mutations; shell inventory failures in screenshots therefore do not establish whole-shell health. No owner store or .env is used.

Five Chromium cases passed against the real HTTP API plus CLI and compiled full-App routing: both RunDetail/Stress test and RiskMonitor opt in, display anchor900, compounded-return conventions, unknown capital/flows and no benchmark adjustment, with real base totalreturn1/9. Both views also display unknown fallback for genuine legacy responses: these cases deliberately remove only the outgoing opt-in query and never fulfill or fabricate a response. A nonfinite stored curve produces the established real422 error and no basis note, and an invalid boolean query is rejected422. This does not claim live malformed-disclosure-field coverage: the present producer always constructs a valid fixed version1 block; those malformed-field cases remain covered by earlier public model/consumer tests. No production validation was bypassed.

Screenshots, actual response attachments, request logs, synthetic identity metadata and build manifest are local receipts under /workspace/scratch/c04-risk-live-20261108. The request boundary deliberately prevents unrelated shell APIs; no combined owner source, native demo/inspector journey, standard deployed SPA, protected suites, formal/full qualification, scientific readiness or complete C04/v9 acceptance is established. No reserved source, generated assets, README or BUILD-STATUS changed. README no-change rationale remains: these are private acceptance instructions for an isolated disposable composition, not a new supported public startup path. Independent advisory review is separately bound to the successor tree and retained with its receipts.
