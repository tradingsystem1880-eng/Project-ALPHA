# Workflow UI repair evidence — 2026-09-29

**Status: implementation and independent review complete; offline component checks passed.**

Verification record updated 2026-09-30 (Australia/Brisbane). Whole-tree acceptance is determined by
`uv run python scripts/gate.py check --tier full`; component results alone are not a full stamp.

Owner approved replacing terminal-style menus/docks with seven workflow sections. The baseline
1440×900 browser inspection showed research inputs clipped by permanent side panes. Most prior
browser tests intercepted all API calls; three tests exercised real backend case/workspace flows.

## Capability inventory

Every existing document pane is checked by `workflowModel.test.ts` for profile-appropriate
reachability. Every real task is opened in both profiles by `workflow.spec.ts`; this establishes
read-plane reachability, not success of every possible state-changing action.

| Section | Existing capabilities retained | Verification |
|---|---|---|
| Overview | Research backlog, active job count, next-task links, system readiness link | Browser navigation and case selection |
| Data & Assets | Downloads, stored assets, snapshots/verification, quality, bulk storage, watchlist/live toggle, chart types/zoom/crosshair/grid, indicators, chart comparisons, chart table/export, funding/open interest/on-chain/DEX presets | Real stored charts; mocked provider/acquisition/error paths; Python API tests |
| Research | Capture/open case, material questions, study/decision, owner-action ceremony, backlog, evidence, literature, Codex notes/context packets, crowding | Real capture; mocked lifecycle/Touch ID and evidence tests; Python API tests |
| Strategies & Tests | Builder validation/save/load/delete, scanner save/run/check/delete, governed lab/development/stages, next-step pipeline, standalone sandbox | Real rule/scan/job journeys; mocked stage/gate paths; Python API tests |
| Results | Run library/report, comparison, figures/export, forecast, ML experiments/diagnostics, risk, findings | Real run persistence/report; mocked figures/ML/forecast; Python API tests |
| Operations | Job status/log/cancel, providers/system, activity/SSE, paper session monitoring, data jobs, scan alerts | Browser and Python integration tests; live provider/paper acceptance not established |
| Settings | Display preferences, per-project guided/advanced mode, saved workspaces, owner enrollment and governance | Workspace round trip; mocked governance/authentication; preference regressions |

## Reproduced defects and repairs

- Terminal dock layout clipped primary research controls. Full-width tasks replace permanently mounted docks.
- Asset entry lacked a shared inventory selector. Searchable choices now use stored inventory, with explicit manual download entry and source/venue inspection.
- Bulk storage errors prevented unrelated provider and symbol reads from rendering. Reads now complete independently, with retryable errors and late-response guards.
- Editing a saved rule left sandbox testing enabled for the older saved bytes. A saved-form signature now requires saving current edits before testing or handing off to the lab.
- New-shell review found stale local asset state on market switches, duplicate history entries, skip-link route changes, and unguarded browser storage writes. Each has a targeted regression.
- Suggestion collapse could move the Pull button during a click. Dismissal now occurs after the destination click.
- Browser harness previously isolated only the main store and silently reused existing servers. It now isolates bulk state and cwd too, and refuses server reuse.
- Tests registered at helper-import time duplicated mocked scenarios inside the nominal real-backend suite. Lifecycle test registration is now explicit.
- Full-gate load testing exposed stopped ML children left durably running when terminal journal RPCs timed out. Terminal callbacks now reconcile through CLI job-show before one bounded retry, accept an already committed matching outcome, reject conflicts, and log persistent uncertainty. Heartbeat limits and cleanup-before-release remain intact.
- Deterministic regressions cover cancellation/failure writes before and after commit, retry-after-commit, permanent failures, conflicting terminal states and failed reads.
- Forecast capacity tests now hold their fake child until explicit cancellation; real browser deletion assertions allow the existing CLI response-and-refresh latency.

## Verification record

- Frontend: **193 browser tests passed** across 1280×720, 1440×900 and 1920×1080, including accessibility, keyboard/scroll reachability, latency, chart evidence, real persisted research/rule/scan/workspace journeys and sandbox-to-report history. Build, lint, types, API generation/freshness and packaged SPA freshness passed.
- Frontend unit suite: **312 passed** across 53 files; coverage 93.22% statements, 82.86% branches, 96.14% functions, 94.90% lines.
- Backend: every full component step passed, including the full pytest/coverage suite (**93.17%** coverage), import/type/static checks, OpenAPI authority/freshness, wheel smoke, slow oracles and branch-selected mutation checks.
- Targeted web integration suite: **187 passed, 497 deselected**. ML unit suite after repair: **30 passed**, including 12 uncertain-write cases; six core regression cases were observed failing before the repair. Durable-lease and capacity checks: **31 passed**.
- Real task inventory: **65 profile/task combinations** visited; no page errors or alerts. Only expected 404s for four unseeded default-watchlist assets. This is navigation coverage, not state-changing acceptance of every capability.
- Literature, Qlib and evaluator component checks passed. Atlas tests passed; generated architecture maps were refreshed after the source/manual changes and checked again.
- Independent source review: no remaining production blockers or new authority bypass found.
- Owner application: read-only Chromium smoke check opened all seven primary pages successfully at localhost:8801. The application was restarted with the backend repair.

Earlier aggregate attempts exposed the forecast-test lifetime assumption, uncertain ML terminal
journaling and a five-second browser deletion/refresh deadline. These were repaired and rerun.
The subsequent backend and frontend steps passed, but their receipts were correctly rejected as
whole-tree stamps while concurrent benchmark audit/results and BUILD-STATUS updates landed.
Git tree comparisons confirmed those concurrent changes were outside the UI/backend repair.
The final aggregate run must be assessed through its current matching-tree gate receipt, not by
reusing those rejected receipts. Evidence-only documentation does not confer application authority.

## External acceptance limits

Physical Touch ID requires the owner. Live vendor downloads, authenticated provider checks, model
weights/workers and broker paper operation must be distinguished from offline fixtures. No owner
research records are mutated by these tests. Provider-discoverable security-master search is not
exposed by the existing bounded API; manual download symbols are explicitly unverified.

Plan: [workflow UI repair](../superpowers/plans/2026-09-29-workflow-ui-repair.md).
