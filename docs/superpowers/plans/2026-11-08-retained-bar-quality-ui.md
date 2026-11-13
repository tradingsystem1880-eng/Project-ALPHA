# Connect retained bar diagnostics to Coverage & Quality

**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

Canonical v9 W05, W18 and market-data slice F require the existing CLI-authoritative
quality evidence to be reachable through thin API/UI parity. Predecessor deb5399 provides
only the opt-in CLI evaluator. The existing CryptoQualityView displays stored mechanical
quality, but has no way to invoke or display caller-grid coverage findings.

Predecessor tree: deb5399c952edebfda47df4f1a8058096f3066b4.
Cumulative base: 3f7b23185c29b2542605bd41b9485016c2ef3e79.
All original candidates, patches and receipts remain separately preserved.

```json
{
  "schema_version": 1,
  "title": "Connect retained bar diagnostics to Coverage and Quality",
  "context": "A manual read-only journey from existing retained dataset quality selection through a closed REST relay to the real CLI evaluator; no provider route, mutable state, acquisition or admission.",
  "assumptions": [
    {"statement": "A caller-grid diagnostic can return CLI exit1 without being a transport failure.", "verified_by": "Real API/CLI synthetic gapped/conflicting artifacts return typed inspected findings; malformed/unexpected process output yields sanitized503"},
    {"statement": "Stopping browser waiting is not proof that synchronous server work was cancelled.", "verified_by": "Explicit Stop waiting caption, AbortController/epoch/key cleanup and browser late-result tests; existing finite60s subprocess timeout remains"}
  ],
  "alternatives_considered": ["Evaluate in browser or web process: rejected; CLI remains sole data evaluator.", "Broaden generic catalog nonzero-exit handling: rejected; dedicated closed quality relay preserves existing consumers.", "Add a dashboard/global shell state: rejected; mount a dedicated child inside existing quality view keyed by manifest."],
  "pre_mortem": ["Exit1 findings disappear into generic HTTP errors.", "Missing response identity or another requested grid is attributed to the selected manifest.", "A late result reappears after view cancellation or manifest selection.", "Synthetic capacity or provider responses accidentally enter production configuration."],
  "slices": [
    {"title": "Project strict retained diagnostics through the existing API ownership", "verify": "Real synthetic API→CLI retained-artifact cases plus invalid input, timeout, identity/grid and exit/outcome mismatch regressions", "expected": "Closed command and environment; explicit bounds; preserved diagnostic exit1; sanitized transport errors; no provider calls or evidence writes", "rollback": "Remove dedicated route/relay/models; old quality endpoint and persisted schemas remain intact", "status": "done"},
    {"title": "Render manual selected-manifest inspection with truthful lifecycle states", "verify": "Fresh SPA build, listing/evidence preflight and owner-wrapped focused browser tests; types/lint and independent source review", "expected": "Explicit grid/hash cap, missing ranges/native integrity findings and stored quality shown separately; unavailable/error/view-cancel states; selection resets; zero automatic evaluation", "rollback": "Remove child import/mount then dedicated component/client; original shell and quality selection remain unchanged", "status": "done"}
  ],
  "tier_impact": ["dag", "bias", "determinism"],
  "docs_to_update": ["docs/superpowers/plans/2026-11-08-retained-bar-quality-ui.md"],
  "out_of_scope": ["Acquisition, providers, credentials or production stores", "Source-history completeness, PIT/research/admission authority", "Global shell, Qlib, Results, inspector, paper, RD, science or ControlStore edits", "Durable accounting or server cancellation protocol", "Protected/full gates", "Dependency installation, transfer or publication"],
  "files": ["apps/alpha-web/src/alpha_web/api/crypto_data.py", "apps/alpha-web/src/alpha_web/api/retained_coverage_models.py", "apps/alpha-web/src/alpha_web/_retained_coverage.py", "apps/alpha-web/frontend/src/panels/CryptoQualityView.tsx", "apps/alpha-web/frontend/src/panels/RetainedBarCoverage.tsx", "apps/alpha-web/frontend/src/api/retainedCoverage.ts", "tests/integration/test_web_retained_coverage.py", "tests/fixtures/retained_coverage_web_fixture.py", "apps/alpha-web/frontend/e2e/retained-bar-coverage.spec.ts"]
}
```

## Operator journey and response contract

Select an existing retained dataset's Quality button. The existing Coverage & Quality view
now offers Inspect retained daily bar coverage. Only Binance spot market_bars/native OHLCV,
1d/interval_start_utc is supported. Other identities show an explicit unsupported state.
No evaluation occurs on mount, refresh or selection. Enter explicit aware ISO start,
exclusive end, closure cutoff and positive hash-byte cap. Cadence is explicitly labelled
86400 native seconds. The API validates whole closed periods, bounded rows/input/metadata
and missing-range output before launching the CLI. It receives identifiers and the declared
grid only; no arbitrary path/URL, credentials or provider options are accepted.

POST /api/crypto-data/quality/{manifest_id}/retained-coverage is an evaluation-only extension
of the existing quality route. Its model is strict. The dedicated relay reuses the existing
CLI command/environment and finite60s timeout while accepting only expected exit0/1.
An explicit matching response manifest, matching UTC instants/cadence and consistent exit
and diagnostic result are required. The route projects a stable typed subset of the CLI
receipt; it never evaluates bars in-process. New TS types follow the existing dedicated
read-plane client precedent; aggregate OpenAPI/generated outputs remain an integration task.

The UI shows expected/covered/missing slots, compact missing intervals, duplicate/conflict
and invalid timestamp/numeric/order findings, output truncation, separately unchanged stored
quality, resource reads and retrieval-after-cutoff caveat. It renders Python counts/ranges;
it computes no bars or expected market values. Inspected grid satisfaction grants neither
provider-history completeness, historical availability/PIT eligibility nor admission.
Unavailable evidence is distinct from HTTP/input/transport failure. Failure text is fixed;
raw process stdout/stderr/exception details are not forwarded to the browser. This does not
claim clearing Python exception context, traceback frame locals or all diagnostic channels.

The view's Stop waiting action aborts/ignores the browser result. The synchronous server
inspection may finish within its own timeout; no acquisition has begun. Manifest-keyed
mounting and epoch checks reject stale late responses. Changing explicit inputs clears the
previous result. No durable job, server cancellation state or acquisition journal is added.

## Fixture and execution boundaries

The dedicated ordinary test fixture seeds actual immutable synthetic raw/Parquet artifacts
in a temporary root. Only its explicit test CLI child supplies synthetic identity/capacity;
production admission, reserve, _bulk_store and storage configuration stay unchanged.
The real production route invokes that actual CLI/evaluator. No final diagnostic report is
mocked for the successful browser journey. Other Workstation inventories are isolated test
fixtures. Failure/latency browser scenarios deliberately inject HTTP errors and hold replies;
those are separately labelled, not real transport qualification.

The canonical browser backend remains the documented disposable runner, with fresh built
SPA and listing-ID preflight/owner wrapper. Dependencies reuse existing installed locked
environments; no sync/install, credentials or external service is required. Build outputs
are preserved executor-locally, then restored out of this source delta. Shared static assets,
aggregate generated OpenAPI/types and README/manual/Atlas updates remain for integration;
this source-only successor is not a release-qualified installed wheel or full frontend gate.

Inherited encoded-input/hash/metadata/returned-row limits remain distinct. Neither the
Parquet decoder's peak RSS nor physical I/O has a hard bound here. Existing subprocess.run
capture_output is not a hard stdout/stderr byte limit. Its library timeout is finite, not a
claim of complete process-group cancellation. No new provider quota, calendar or freshness
policy is chosen, and no source or stored quality is repaired/requalified.

Claude is unavailable through current authorized tools/executable. Independent review is
an available Codex subagent and remains source review, not native approval or a full gate.
