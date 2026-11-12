# Native job result web consumer

**Delivery state:** Implemented and scoped-tested; full qualification unverified.

```json
{
  "schema_version": 1,
  "title": "Read retained native-job evidence in existing Research workspace",
  "context": "Canonical v9 W04/W18 typed evidence consumer; synthetic-only scoped successor to f0a44b3a, not package-wide qualification.",
  "assumptions": [
    {
      "statement": "No trustworthy native-job enumeration or canonical run binding exists in this slice",
      "verified_by": "Existing native CLI/API source; manual UUID input only"
    },
    {
      "statement": "Existing installed assets and loopback backend suffice without setup",
      "verified_by": "Production build and real native-owner to browser journey"
    }
  ],
  "alternatives_considered": [
    "Reuse existing Research pane registration and dedicated reader; reject fabricated run manifests and native enumeration through transient jobs."
  ],
  "pre_mortem": [
    "Superseded reads could repopulate stale evidence: generation fencing plus AbortController and real rapid-change test.",
    "Browser runner timeout could orphan backend: existing subreaper and retained wrapper ownership plus timeout/crash regression."
  ],
  "slices": [
    {
      "title": "Typed UUID-only read client",
      "verify": "Scoped nativeResults Vitest",
      "expected": "Reject malformed/binding/promotion errors and no paid/execution fallback",
      "rollback": "Remove dedicated reader/test",
      "status": "done"
    },
    {
      "title": "Research pane and stale-safe local state",
      "verify": "Scoped navigation Vitest, oxlint and production build",
      "expected": "Additive pane; no global state or other-owner edits",
      "rollback": "Remove dedicated panel/CSS and two documents.ts additions",
      "status": "done"
    },
    {
      "title": "Real built-SPA synthetic evidence journey",
      "verify": "tests/unit/test_native_result_web.py focused classes",
      "expected": "Actual native receipt, real backend/browser, negatives/retry/rapid change and unchanged store",
      "rollback": "Remove dedicated fixture/spec/config and generated SPA delta; retain evidence",
      "status": "done"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "docs/operations/native-result-view.md"
  ],
  "out_of_scope": [
    "Live inference/provider calls",
    "Protected/private/full gates",
    "Cross-owner resume and accounting policy",
    "Paper/Qlib/DataQuality/saved inspector/global state",
    "Publication or deployment"
  ],
  "files": [
    "apps/alpha-web/frontend/src/api/nativeResults.ts",
    "apps/alpha-web/frontend/src/api/nativeResults.test.ts",
    "apps/alpha-web/frontend/src/panels/NativeJobResult.tsx",
    "apps/alpha-web/frontend/src/panels/nativeJobResult.css",
    "apps/alpha-web/frontend/src/shell/documents.ts",
    "apps/alpha-web/frontend/playwright.native-result.config.ts",
    "apps/alpha-web/frontend/e2e/native-result-real.spec.ts",
    "tests/unit/test_native_result_web.py",
    "docs/operations/native-result-view.md"
  ]
}
```

Canonical v9 W04 shared typed receiver and W18 evidence-backed existing workspace
(Library libfile_181ac6079dcc8191b222b76c1f10bf17 version9). Preserve parent staged
tree f0a44b3a71a5f179a1cc1abe88966db23572b1fe and all exports unchanged.

This bounded successor exposes only the completed synthetic native-job read contract.
No trustworthy native-job enumeration exists; manual UUID lookup is an explicit input,
not a claim that transient /api/jobs enumerates durable native jobs. No canonical run ID,
manifest publication, profile selector, launch/resume control or scientific authority.

1. Dedicated typed nativeResults API client/parser and focused fake-response tests;
   reject malformed bindings and incomplete values, keep server-selected configuration.
2. Dedicated NativeJobResult React panel, local-only state and cancellation/generation
   fencing. Editing the UUID immediately clears results, loading and errors; stale
   async completion cannot repopulate them. Form, retry, explicit domain states and
   exact provenance. Minimal documents.ts import/research-pane registration only.
3. Production SPA build using existing installed packages, then real loopback FastAPI
   serving the built files against actual pinned synthetic stock-loop owner evidence.
   No browser API interception; missing/profile/corrupt and rapid-change cases.
   Focused checks and independent Codex review if existing Claude unavailable.

Owned source: frontend/src/api/nativeResults.ts and test, panels/NativeJobResult.tsx
and CSS, additive shell/documents.ts; dedicated native-result browser test/config and
synthetic launcher/test only; dedicated guide/plan. Built static SPA is a generated
shared delivery output, kept separate for assembly. app.py mount unchanged.

No imports across backend DAG, data look-ahead/statistical semantics or RNG changes.
No global state, DataQuality, paper, QlibResults, saved-inspector, ControlStore or
accounting edits. No protected/full/private gate, installs, source transfer or publish.
Normal local Workstation access model remains inherited; manual UUID is not auth.
README/CLAUDE review: no_change to shared manuals for this isolated unqualified
successor; update owned guide with exact navigation, assumptions and evidence.
