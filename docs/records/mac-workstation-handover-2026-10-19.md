# Mac workstation handover refresh — 2026-10-19

This is a bounded local refresh, not a repository-wide handover closure. The
accepted-main checkout after [PR77](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/77)
has HEAD `59b92919a3fb2efcbb2159063d2801c10693e47c`, tree
`c8fdb502cbd59d1ccbcee915073be1cae2d42128`. Before this documentation candidate
was added, the isolated checkout was clean and its HEAD matched fetched
`origin/main`. This candidate commit contains the documentation changes described
here. The original shared checkout and preserved worktrees were left untouched.

## Completed

- Rebound the clean checkout to accepted main with fast-forward-only Git
  operations. Read-only GitHub verification confirmed all seven jobs in
  [post-merge run
  39245184680](https://github.com/tradingsystem1880-eng/Project-ALPHA/actions/runs/39245184680)
  passed on this exact head.
- Ran a local headless startup/UI smoke on the exact checkout using an empty
  synthetic data directory, isolated HOME, a sanitized environment, and the
  existing Python environment. No packages were installed. All 12 imported
  workspace packages, plus `alpha_research.weekly_diagnostic`, resolved to source
  files under this checkout.
- Rendered `ALPHA · Overview` with the main region visible. All 17 observed HTTP
  responses were successful; expected startup requests were present; browser
  console errors, runtime exceptions, and external host requests were absent.
- Disabled paper and IBKR paper. No provider credentials were supplied. The SPA
  fetched `/api/providers` for local registry metadata; no provider check,
  acquisition, pull, broker operation, or external provider request was made.
- Stopped the smoke-owned browser and server. Ports 18882 and 19224 were free
  afterward.
- A read-only process/launch metadata check found no matching ALPHA/Workstation
  launch label or LaunchAgent filename, no app/smoke process, and no listener on
  ports 8801, 18881, 19223, 18882, or 19224. No launch configuration was changed.
- Preserved the first failed smoke attempt and its full diagnostics. It failed
  because the sanitized PATH omitted the existing `alpha` command. The corrected
  retry added the existing environment's `bin` directory and passed without
  installing dependencies or changing application source.

The smoke manifest, request/result receipt, import paths, logs, and screenshot are
under the owner-only ignored directory
`.alpha/state/mac-handover-2026-10-19/attempt-2-current-main-pr77/`; its
`run-manifest.json` is the entry point. Sibling receipts in
`.alpha/state/mac-handover-2026-10-19/` include `postmerge-ci-summary.json` and
`local-process-audit.json`. The earlier Desktop evidence was not moved or deleted;
it remains at
`/Users/hunternovotny/Desktop/Project-ALPHA-reconciliation-evidence/current-main-browser-rendering-smoke-2026-10-18/attempt-5-cdp-correct-binding/smoke-result.json`.

## Still open

**Cloud-only reconciliation (2026-10-30):** The [existing hygiene plan](../superpowers/plans/2026-10-08-repository-hygiene.md#cloud-visible-ledger-reconciliation-2026-10-30) now records the observed cloud refs, worktrees and preservation dispositions. The saved Mac path/branch/operation ledger and physical storage were unavailable and remain unverified; this does not close their owner-disposition obligations below.

- Reconcile the full saved path, branch, and operation ledger and obtain owner
  disposition before retiring anything. Keep the original dirty checkout,
  archives, branches, and worktrees preserved until then.
- Investigate the displayed “Expansion SSD blocked” state only when the owner
  authorizes a physical-storage check. This smoke used synthetic empty data and
  did not establish mount, storage, or launch-persistence readiness.
- Live provider access, credentials, broker connectivity, mutation adequacy,
  upstream dependency advisory status, and the full canonical gate remain
  separate evidence items. No conclusion about them follows from this smoke.

The smoke exercises bounded workstation startup and overview navigation only; it
does not replace frontend E2E, full-gate, live-provider, or physical handover
acceptance. Its older comparison receipt remains in
`Project-ALPHA-reconciliation-evidence`; all earlier failed attempts remain
preserved with their original result. The external completion ledger now records
this workstation result, updates current-main to PR77, and keeps
`final_clean_handover` blocked. On 2026-10-20 the reported path
`/Users/hunternovotny/Desktop/Project-ALPHA-preflight-tooling-delivery` was absent
in this execution environment. The existing accepted checkout at
`/Users/hunternovotny/Desktop/Project-ALPHA-handover/accepted/pr59-preflight-tooling`
was present and clean on `fix/preflight-tooling-delivery` at
`e57b18c2fc71a1bfa88e3aa6ab4320d24e76f7eb`, tracking the same origin branch and
based on `31479cad85d345786de911968828cef1b8c9d4d6`. PR #59 is merged. Its
recovery receipt lists 12 files, all of whose current content hashes match the
receipt. This verifies the accepted PR #59 checkout only; it does not establish a
separate newer checkout or unfinished source delta. The external ledger keeps the
reported path as an unverified timing discrepancy, so do not replay accepted PR
#59 content. Targeted assertions on the recorded ledger entries passed; the
whole-ledger checker was not run because it inspects protected paths.
