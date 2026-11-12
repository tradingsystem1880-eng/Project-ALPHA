# Native job result view

Open **View → Research › Native job result**, or
`#page=research&pane=NativeJobResult` in the existing Workstation SPA. This is a
read-only consumer of `GET /api/native-jobs/{UUID}/result`; it does not create a
canonical run, publish a run manifest or enumerate native jobs through `/api/jobs`.
Obtain the UUID from the original native owner receipt or CLI output and enter it
manually. The identity is local component state; it is not saved as a run selection.

Press **Read result**. The server still selects trusted source/runtime/mode via the
existing deployment configuration described in [the API guide](native-result-api.md).
The browser cannot supply paths or choose a profile. Missing configuration/evidence
returns unavailable, and invalid hash/profile evidence remains invalid. Those states
show no prior result. An HTTP/network or malformed response failure shows a retryable
read error. **Retry read** performs another read; it cannot launch, repair or resume.
Editing the UUID aborts the previous request, clears evidence/loading/error state and
fences late responses by request generation. Navigation away also aborts/fences reads.
No immutable-result browser cache is used for this mutable verification read.

Completed means validated retrieval of synthetic fixture artifacts against the owner
observation. The view presents the exact job/reservation/owner/spec/profile identity,
synthetic fixture value, five recorded stages, fake-attempt/actual-call counts and
receipt/trace/checkpoint/source hashes. It labels synthetic-only/unqualified,
false scientific feedback and no resume authority. It is not accepted research,
qualified native inference, economic performance or a claim of current approval.
The client projection validates consumed contract fields and exact requested-job
binding before displaying them; backend validation remains authoritative.

## Focused reproduction

Use the existing installed frontend dependencies and native worker assets; this
slice does not install/download anything. The current executor reuses the existing
frontend node_modules by a local untracked symlink, with its actual installed package
versions recorded in the delivery evidence. Resolve the canonical locked environment
before any broader qualification; a build alone is no full-gate stamp.

From frontend, run scoped Vitest for `src/api/nativeResults.test.ts`, existing
`src/shell/workflowModel.test.ts` and `src/shell/documents.test.ts`, scoped oxlint,
and `npm run build`. The build updates the existing production SPA under
`src/alpha_web/static/app`; these are shared generated delivery outputs, not a new
frontend or service. The app.py import/mount is unchanged from the API predecessor.

The new public `tests/unit/test_native_result_web.py` accepts explicit existing
`ALPHA_RDAGENT_SOURCE`, `ALPHA_STOCK_PYTHON` and a fresh `ALPHA_NATIVE_WEB_EVIDENCE`
directory. It creates one fresh disposable approved synthetic native job, executes
the actual pinned upstream stock fixture and retains its owner receipt. Its dedicated
Playwright config avoids the default seeder's excluded fixture dependencies. Browser
requests reach a fresh actual loopback Uvicorn backend serving the built SPA, with no
API route interception. Controlled receipt changes affect only the new disposable
fixture and are restored; no owner data or production history is used. Backend restarts
exercise genuine connection failure/retry and server-selected profile mismatch.
The existing Linux run_owned_test.py subreaper owns browser-runner descendants on
timeout/crash; the outer fixture retains the wrapper until final cleanup. A focused
regression proves both timeout/crash descendants are reaped. Server stop waits for
actual exit, including after forced termination. The browser observer follows the
existing canonical-host redirect; it does not change Workstation host policy.

The test denies provider/network egress and credential-file reads in the Python
backend/read children, permits only its loopback server bind and fixed result-read
CLI (plus standard uname/ldconfig metadata), and prohibits ControlStore write-open.
It compares complete database row dumps before/after. Browser screenshots and raw
HTTP response evidence remain in the separate scratch evidence directory.

Canonical scope is v9 W04 receiver binding and W18 evidence-backed existing workspace,
not completion of either full work package. Private/protected/full gates, actual
combined-tree paper integration, production worker/inference and deployment remain
unverified. No authorization, budgets, accounting, dispatch, native execution semantics,
global state, Data Quality, paper reader, Qlib Results or saved inspector changes.
