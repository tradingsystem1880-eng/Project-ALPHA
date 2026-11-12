# Exercise retained coverage with ready synthetic project context

This successor closes the disposable-project inventory limitation of preserved assembly
30dcbf4a8db4e7c38a1d723cf10ea8adb101b27b. It changes only the fixture, focused public
browser/API tests and this candidate-local record. No production app, shell, ControlStore,
API contract, provider, admission, scientific or generated-output implementation changes.

```json
{
  "schema_version": 1,
  "title": "Exercise retained coverage with ready synthetic project context",
  "context": "Complete a production-served operator smoke journey using supported disposable project/case records rather than a deliberately blocked inventory fixture.",
  "assumptions": [
    {"statement": "Synthetic projects are setup records only, not authority to launch studies or use real data.", "verified_by": "Existing capture_research_case plus draft_exploration_contract in a temporary root; zero attempts/activejobs; runtime create/capture/admit commands refused"},
    {"statement": "Project changes clear the whole non-chart pane, while manifest changes reset the retained-grid child.", "verified_by": "Existing unmodified App.tsx project key and CryptoQualityView manifest key, exercised by real production browser selection"}
  ],
  "alternatives_considered": ["Fake browser inventory responses: rejected; use actual supported store/CLI/API reads.", "Change global picker loading or remount behavior without reproducing a source defect: rejected; current source already handles settled requests and context changes.", "Use a real project/store or weaken admission: rejected; fixture-only synthetic root and capacity remain."],
  "pre_mortem": ["Only one of the two project inventories loads and the picker still reports failure.", "Research command-prefix whitelisting accidentally admits a write subcommand.", "A test assumes a form remains mounted after a legitimate project remount.", "Selecting the already-default profile fails to trigger a real refresh."],
  "slices": [
    {"title": "Prepare legitimate bounded synthetic project reads", "verify": "Real API inventory/case/options/quality tests and runtime create/capture/register refusal tests", "expected": "Two supported draft cases with no study attempts; read-only inventories available; retained hashes/project rows unchanged", "rollback": "Use preserved30dcbf4a fixture/export; no production record or schema was changed", "status": "done"},
    {"title": "Exercise ready, reset, unavailable and retry states in served production SPA", "verify": "Fresh public listing/fixture preflight and owned browser wrapper; focused types/lint and independent exact-tree source review", "expected": "Ready picker A/B; projectA→manualquality→projectB remount→reselect→bounded unavailable→manifestreset; actual server inventory failure stops loading and retry recovers", "rollback": "Remove only new fixture mode and smoke tests; production UI/API/assets remain unchanged", "status": "done"}
  ],
  "tier_impact": ["determinism"],
  "docs_to_update": ["docs/superpowers/plans/2026-11-08-retained-project-production-smoke.md"],
  "out_of_scope": ["Production project/store creation or migration", "Study execution, providers or credentials", "Global shell or other owners' source changes", "Protected/full gates", "Installations, transfers or publication"],
  "files": ["tests/fixtures/retained_coverage_web_fixture.py", "tests/integration/test_web_retained_project_fixture.py", "apps/alpha-web/frontend/e2e/retained-project-production.spec.ts"]
}
```

## Source diagnosis and tested behavior

The current picker uses Promise.allSettled for the paginated strategy-project and research
case inventories, then sets loading false and exposes any failures separately
(ContextBar.tsx:42–60). The mounted non-chart pane is already keyed by project identity
(App.tsx:189). No stuck-loading/source error-handling defect was reproduced with the
legitimate synthetic store, so no shared-shell source edit is justified or included.

The first browser assertion wrongly expected the quality form to remain present after
changing projects. Evidence instead showed the correct whole-pane remount: the old result,
form and selection were gone. The test now reselects the manifest explicitly and checks
empty inputs. A subsequent fault test initially selected Crypto when it was already the
default, producing no refresh. It now verifies an actual server422 and forces a real
Equities→Crypto refresh before asserting failure/loading/retry behavior. Both failed-run
receipts remain separate; neither is described as a fixed product defect.

The optional serve-projects fixture uses existing ControlStore.capture_research_case and
research_intake.draft_exploration_contract in its temporary root. These are draft-only
synthetic cases with no attempts or active jobs; no real project, history or entitlement is
replaced. Runtime permits only named read commands, with research data list matched by its
full three-word prefix. Project create, research capture and research data register remain
refused before cwd/store access. Server and child retain disposable cwd isolation.

Inventory fault injection is a test-only in-memory switch installed only in serve-projects.
It returns a real standard API error through the normal server boundary. No browser route
interception, fake inventory JSON or production fault endpoint exists. The retry action
then reads the same supported store normally. The production SPA/API/CLI/evaluator remain
those of the preserved assembly, with its generated schema/types/static assets unchanged.

The read-only quality test compares crypto/bulk content hashes and public project inventory
before/after. It does not prove SQLite/WAL/mtime/global-host immutability. It preserves no
new acquisition, PIT, rights, source-history or admission claim. Project context selection
is not scientific or trading approval. No real protected outcomes are read.

## Delivery bounds

All predecessor source/build exports remain unchanged. The four-path fixture/test/doc
successor and cumulative route are recorded locally. The generated-output identity remains
that of30dcbf4a; explicit equality/freshness receipts show no generated delta is needed.
Other owners' candidates are not composed. Full/private/native release gates, all viewport
and performance/accessibility aggregates, real host qualification and provider admission
remain unrun. Claude is unavailable through existing authorized routes; independent review
uses the available Codex reviewer, labelled accordingly. No transfer or publication occurs.
