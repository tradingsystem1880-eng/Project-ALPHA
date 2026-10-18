# Recorded-run investigations in the workstation

**Current status — 2026-10-17:** Accepted through [PR #56](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/56) with seven successful required checks. Live Tiingo acceptance remains UNVERIFIED; fixture-based tests are not live-provider acceptance.

Earlier dated status and incident entries are preserved as historical records.

**Historical delivery state before PR #56:** Implemented; final-tree aggregate acceptance required before commit.

```json
{
  "schema_version": 1,
  "title": "Recorded-run investigations in the workstation",
  "context": "Continue 4b93c97 with a usable run-report investigation workflow, without replacing concurrent primary workstation work.",
  "assumptions": [{"statement": "The shared RunDetail component is the narrow integration point; primary's uncommitted chart/rule assistant is a separate runtime.", "verified_by": "Two navigators compared current primary and clean runtime source on 2026-10-04."}],
  "alternatives_considered": ["Do not import all uncommitted workstation changes or overwrite its assistant.", "Use opaque IDs and CLI-owned cases instead of exposing path-taking diagnostic commands.", "Keep same-case follow-ups within existing budgets rather than silently creating new cases."],
  "pre_mortem": ["Cancelling only the CLI can orphan Codex's separate process group: propagate cancellation, supervise parent death, and test real processes.", "Refresh or follow-up resets budgets: use durable cases and retain immutable turn inputs/reservations.", "Browser supplies arbitrary paths or source identity: closed typed request contracts and server-derived roots/cutoffs.", "Model prose looks like established cause: render findings, evidence, hypotheses, proposed tests and limitations separately."],
  "slices": [
    {"title": "Lifecycle and same-case follow-ups", "verify": "uv run pytest -q tests/unit/test_investigation_lifecycle.py", "expected": "Known cancellation reaps owned processes; retries and follow-ups retain budgets and inputs.", "rollback": "Remove optional workstation entry; retain all cases and receipts.", "status": "done"},
    {"title": "Opaque-ID CLI workspace and comparison handoff", "verify": "uv run pytest -q tests/unit/test_investigation_workspace.py", "expected": "Verified state survives refresh, rejects unsafe identity, and links all-pass comparison revisions.", "rollback": "Remove optional workstation entry; retain all cases and receipts.", "status": "done"},
    {"title": "Typed web relay and run-report controls", "verify": "uv run pytest -q tests/unit/test_web_investigations.py", "expected": "Only closed CLI operations; no engine in web, raw paths or credentials in browser input.", "rollback": "Remove optional workstation entry; retain all cases and receipts.", "status": "done"},
    {"title": "Browser acceptance and delivery documentation", "verify": "ALPHA_PLAYWRIGHT_PORT=8820 npx playwright test e2e/investigations-real.spec.ts --project=chromium-reference", "expected": "Browser-to-CLI persisted workflow, recovery/cancellation and explicit operational limits.", "rollback": "Remove optional workstation entry; retain all cases and receipts.", "status": "done"}
  ],
  "tier_impact": ["protected", "dag"],
  "docs_to_update": ["CLAUDE.md", "docs/BUILD-STATUS.md", "docs/operations/codex-investigations.md", "docs/governance/capability-authority-matrix.md"],
  "out_of_scope": ["No trading/research admission, strategy execution, automatic skill activation or broader model tools.", "Live provider acceptance is unverified unless an actual credential-backed request succeeds; fixtures are not provider acceptance.", "No wholesale merge of the concurrently edited primary workstation."],
  "files": ["apps/alpha-cli/src/alpha_cli/", "apps/alpha-web/", "tests/", "docs/", "architecture/atlas/"]
}
```

The owner explicitly authorized the proposed workstation integration. This opens only a bounded
advisory investigation surface in the previously frozen REST/Terminal area; existing governed
research, D2, owner actions, paper, broker and order authority stay unchanged. The clean runtime
branch contains the implementation and browser acceptance. The shared report insertion is kept
small and compatible with the primary checkout's richer report, whose uncommitted changes are
preserved. Separate branch acceptance is not combined-tree acceptance.

Better means a user can select an eligible recorded run, obtain cited findings, ask a same-case
follow-up, cancel/resume within durable limits, inspect missing-data proposals and explicitly
acquire comparison data into a linked new exposed case. No manual CLI coordination is required.
Historical runs without the required research cutoff remain ineligible; no manifest is rewritten.
Proactive hypotheses and proposed tests are visible suggestions, not automatically executed research.

No estimator changes. All run/data reads retain existing point-in-time and provenance contracts.
Only CLI composes research/data; web remains a typed subprocess relay. Follow-up input is retained
with its turn reservation. Existing case identities, old session readers and Claude artifacts remain
compatible. No new model, package or inference framework is introduced.

## Acceptance record

Targeted lifecycle, workspace, comparison-data and web tests pass. The browser acceptance uses
real HTTP, CLI subprocesses and persisted cases, with explicitly labeled inference/provider doubles.
It covers a new investigation, follow-up, cancellation, refresh, comparison preview/acquisition and
linked-child navigation. Separate live Codex acceptance exercised CLI launch, an actual web-launched
follow-up and cancellation of an active resumed turn. Cancellation reported interrupted, left none
of four observed child processes alive, and exhausted rather than reset the four-turn allowance.
The earlier failed-status cancellation receipt is retained alongside the corrected result.

Private acceptance evidence: `/private/tmp/alpha-workstation-investigation-live-20261004`.
These operational smokes are not a trading-judgment benchmark. Live Tiingo remains unverified.
Independent review and the canonical full gate must bind the final tree before commit; the gate
receipt, rather than this narrative, records aggregate acceptance against `4b93c97`.

Independent review also identified concurrent workspace-capacity reservation and stale browser job-ID
recovery gaps. Both are fixed with concurrent-process and browser regressions. The canonical full gate and
review attestation are mandatory final delivery steps, separate from the implementation slices above.

The first aggregate test run passed 4,979 tests but missed the unchanged 93% coverage threshold
(92.91%). Added lifecycle and CLI recovery tests exercise signal restoration, progress filtering
and comparison handoff. They exposed and fixed a successful acquisition being reported as failed
solely because its parent model turn had failed. Acquisition exit status now follows its own
verified result and child publication. Final aggregate acceptance must include these corrections.
