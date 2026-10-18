# Proposed minimal Playwright evidence helper

**Delivery state:** Implementation candidate; final acceptance pending.
**Plan base:** `fbdcbcfdf29aebe3fd43e38bf5ae4051cbf23b98`.
Reconcile actual accepted main before final acceptance. Keep PR71 and the separate prevention draft
unchanged. This revision supersedes the larger plan; its review history is retained.

```json
{
  "schema_version": 1,
  "title": "Fresh Playwright output paths and bounded evidence export",
  "context": "Allocate fresh output for each focused invocation, check its public listing, and optionally export one stopped run. Leave browser execution and acceptance with existing mechanisms.",
  "assumptions": [
    {"statement": "Existing utilities own backend isolation, not evidence preservation.", "verified_by": "Navigator inspected public run_playwright_backend.py, playwright_investigation_fixture.py and test_playwright_backend_port.py; no reusable evidence primitive."},
    {"statement": "Installed Playwright 1.61.1 emits usable JSON listing identities and argv.", "verified_by": "Owned-process public dialog-completion listing: corrected filter exit 0, one case; original zero-case exit 1 retained before correction."}
  ],
  "alternatives_considered": ["Manual unique paths remain possible; a small allocator reduces accidental reuse.", "Reject full expected-set schemas, execution wrappers, state machines and generic backup machinery."],
  "pre_mortem": ["Caller reuses an emitted command: disclose that no helper enforces later execution.", "Empty/wrong selection: reject errors, zero intended cases or missing requested IDs.", "Copy failure: keep originals/partials and return nonzero without retry or cleanup."],
  "slices": [
    {"title": "Fresh output and focused listing preflight", "verify": ".venv/bin/python scripts/run_owned_test.py -- .venv/bin/python -m pytest -q tests/unit/test_playwright_evidence.py -k prepare", "expected": "Wrong/empty selections rejected; distinct allocations preserve earlier artifacts.", "rollback": "Withdraw isolated helper/test patch; retain evidence.", "status": "pending"},
    {"title": "Bounded stopped-run export", "verify": ".venv/bin/python scripts/run_owned_test.py -- .venv/bin/python -m pytest -q tests/unit/test_playwright_evidence.py", "expected": "Links rejected; copy failures retain originals/partials; failed test status remains failed.", "rollback": "Withdraw candidate without deleting evidence.", "status": "pending"},
    {"title": "Usage, independent review and frozen validation", "verify": "Focused lint/type/plan/link checks, Atlas freshness, independent exact-diff/evidence review, then uv run python scripts/gate.py full.", "expected": "Actual results preserved without publication or gate waiver.", "rollback": "Withdraw candidate/necessary producer outputs, retaining receipts.", "status": "pending"}
  ],
  "tier_impact": ["none"],
  "docs_to_update": ["docs/superpowers/plans/2026-10-17-playwright-evidence-preservation.md", "docs/operations/development-loop.md"],
  "out_of_scope": ["Browser execution, new process ownership, hidden gates, installs, retries or cleanup", "Protected/private content, old archives or owner stores", "Assertion/config/dependency changes, PR71 edits, commit/push/publication/merge", "Full expected-case schemas, config/lock copies, state machines or complete/atomic snapshot claims"],
  "files": ["scripts/playwright_evidence.py", "tests/unit/test_playwright_evidence.py", "docs/superpowers/plans/2026-10-17-playwright-evidence-preservation.md", "docs/operations/development-loop.md"]
}
```

## Reuse and scope

One stdlib script, one synthetic unit-test module, this plan and short usage in the existing
development loop. Coordinate usage with the prevention draft; keep one guidance location. Existing
backend isolation/fixture utilities remain unchanged; no useful evidence primitive needs extraction.
Reuse the existing process owner. No runner, gate, dependency, policy tree or parallel inventory.

## Exact CLI contract

`prepare --output-parent ABS --project NAME --file REL [--grep REGEX] --expect-id ID [--expect-id ID ...]`

Resolve checkout/frontend from the script location and use only canonical `playwright.config.ts`.
Require one existing public `e2e/*.spec.ts` file, one configured project, at least one expected native
spec ID, and an existing absolute private output parent outside frontend. Reject traversal/links.
Exclusively allocate mode-0700 `playwright-<unique>/`, with `artifacts/` for Playwright and log paths
outside that subdirectory. No caller-selected reusable run path, overwrites or cleanup.

Build the local Playwright argument vector with explicit config, file/project/optional grep and
absolute `--output`. Playwright's positional file filter is a regex: use the escaped absolute selected
file path anchored at both ends, not raw user text. Through `scripts/run_owned_test.py`, with frontend cwd, run only its listing
variant: append `--list --reporter=json`. Retain listing stdout/stderr/exit in this fresh directory.
No build, server or browser run. The emitted test vector removes only those two listing overrides;
the caller later uses that vector through the same existing owner, after a fresh build/authorization.

Fail on nonzero exit, report errors, malformed/unsupported JSON, wrong config/argv, zero cases in
the requested project, or missing expected IDs. Match `spec.id` within the requested project; record
identities as `(projectName, spec.id)` plus readable file/title. Do not require a full expected set.
Count flattened listed specs/tests, not `stats.expected` (zero even in the successful smoke).
Reject any requested-project spec whose resolved report file differs from the selected file.
Record all requested-project cases separately from dependency/additional-project cases; do not
disable dependencies. Other projects cannot satisfy intended-case/ID checks. Report metadata does
not prove why an additional project was included; do not infer dependency edges from it.

Write one `run.json`: paths, list/test argv, list exit and case groups, config/lock hashes and installed
Playwright version. No config/lock copies or environment dump. Failure retains the directory/logs,
returns nonzero, prints the absolute path/error, and emits no runnable command. Success prints JSON
with `run_dir`, `output_dir`, `stdout_log`, `stderr_log`, `cwd`, and owner-wrapped `test_argv`.

Example using the observed public case (native ID depends on tree/tool):

```sh
.venv/bin/python scripts/playwright_evidence.py prepare \
  --output-parent /workspace/Project-ALPHA/.alpha/state/browser-runs \
  --project chromium-minimum --file e2e/dialog-completion.spec.ts \
  --grep 'dialog completion waits for the actual acceptance promise' \
  --expect-id 090732d0863281082be4-a66622007d7cabab6fb1
```

Use returned cwd/argv/log paths and prepare anew before every later invocation. Do not reuse this
ID after a tree/tool change without checking an intended fresh listing. The helper does not execute
the returned test vector, authenticate execution or enforce that later flags/config remain the same.

`export --run-dir ABS --destination ABS --test-exit INTEGER --stopped`

Accept one prepared run and a previously nonexistent absolute destination outside it. `--stopped`
attests the producer/log writers ended; it is not process probing or proof. Traverse only the run's
regular files/directories. Reject symlinks, hard links, special files, traversal, overlap and existing
destination/linked ancestors; never follow external attachment paths. Exclusively create destination,
copy without overwrite, verify copied sizes/SHA256, and write a manifest of relative paths, sizes,
hashes and caller-reported test exit/result. Export covers enumerated files from a stopped run, not
a complete/atomic snapshot; no before/after inventory or repeated-preservation/completion protocol.

Copy/validation/hash errors return nonzero with the retained partial path; originals and partials
remain. No retries, deletion or success claim. Export exit 0 means copying only: test exit 1 remains
`test_result: failed` in manifest and printed result. Listing/copy success never implies test success.

```sh
.venv/bin/python scripts/playwright_evidence.py export \
  --run-dir /ABSOLUTE/returned-playwright-directory \
  --destination /ABSOLUTE/new-private-export-directory --test-exit 1 --stopped
```

## Direct tests, observed listing and limits

Synthetic tests: intended case plus separately recorded dependency case; wrong/missing ID; zero
intended cases even with dependency cases; listing errors/nonzero exit/wrong config or argv; two
near-matching filenames cannot broaden the selected file; two
distinct absolute preparations cannot overwrite; a simulated second run leaves first trace bytes
intact; links/existing export destination rejected; copy failure after one file retains source and
partial; size/hash mismatch fails; failed test status remains failed after successful export. Use
temporary synthetic bytes/injected faults, no real traces/private fixtures or broad framework tests.

Smoke: installed Playwright 1.61.1, existing owner, only public `e2e/dialog-completion.spec.ts`.
Anchored bare-title grep produced exit 1, `No tests found`, empty suites; retained before correction.
Unanchored title grep produced exit 0, no errors, one intended case, ID shown above. Observed JSON:
`config.argv`, `configFile`, `rootDir`, nested suites/specs, `spec.id`, test `projectName`; listed tests
have empty results and status `skipped`, not execution. No browser/protected collection ran. This
smoke did not exercise dependency expansion; synthetic tests cover grouping, not actual dependency
runtime behavior. No further smoke runs proposed.

Fresh exclusive directories prevent accidental cross-invocation reuse when preparation is repeated
per invocation. Synthetic trace-isolation tests must prove that limited property. Caller reuse of
an emitted command can still overwrite that run's outputs. The helper cannot enforce later argv,
writer shutdown or truthful test status; hashes bind recorded inputs, not execution provenance.

## Validation and remaining scope decisions

Small red/green increments; focused unit/lint/format/type, plan/link and actual Atlas freshness checks.
The new test predicts producer-owned `architecture/atlas/generated/{inputs,graph}.json` and
`architecture/atlas/generated/views/unknowns.json`. Review exact required output additions (including
any changed existing `docs/atlas/` files) before generation; no hand edits. Required manual/build
updates also need explicit path/scope coordination. Coordinate development-loop usage before editing.
Independent exact-diff/evidence review and unchanged full validation are required on the frozen
candidate in the provisioned checkout. Preserve failures before retries; no parallel canonical runs,
install/repair/waiver. Return exact diff/base/results and verified private recovery. No commit,
publication or merge; implementation remains held for parent review of this reduced plan.

## Implementation candidate (2026-10-17)

Parent approved reduced plan SHA256
`89d4f8e72383bbf81de894777fbdd0f06f364a7f90f93a90a30dfb5f9a544546`.
Implementation uses an isolated branch from accepted main
`fbdcbcfdf29aebe3fd43e38bf5ae4051cbf23b98`; coding need not wait for PR70/PR71,
but actual main must be reconciled before final acceptance. Neither candidate is edited.

The helper now implements the approved prepare/export CLI. Eighteen synthetic checks passed,
including retained partial copy failure, trace isolation, wrong/empty selection and failed status.
The single authorized compatibility listing passed with escaped anchored absolute file and explicit
absolute output arguments: one intended public dialog-completion case on Playwright 1.61.1,
no listing errors and no browser execution. Earlier zero-selection listing evidence remains retained.
Dependency runtime expansion remains untested by this smoke. No runtime receipt authenticates a
later caller's command/status. Independent final review and full validation remain pending.
Independent code review identified glob traversal's suppressed directory errors. A direct scandir
walk now propagates those failures; an injected PermissionError fails without a manifest and retains
the source and partial copy. The failing regression and intermediate checks remain preserved.

Usage is inserted beside the existing browser commands, before the unchanged tail used by the
retained prevention draft. That draft remains separate. At its later integration, replace its
helper-proposal-only sentence with an accurate reference to this delivered usage; do not duplicate
instructions or its incident history. Parent approved precisely the three producer-owned Atlas JSON
paths reported by freshness. The documented producer changed only those JSON bytes: one new unit-test
input/node and corresponding aggregate hashes/counts; existing edges and unknown-node membership
remain unchanged. Its five Markdown outputs retain their original bytes. Independent generated/final
review and the frozen canonical full gate remain required. No public release or merge is authorized.
