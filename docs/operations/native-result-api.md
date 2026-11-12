# Server-owned native-job result API

`GET /api/native-jobs/{job_id}/result` is mounted in the existing Workstation app. It
reads a retained synthetic native job; it creates no run ID, run manifest, job, owner,
reservation, approval or execution. It invokes the fixed read-only `alpha research diagnostic native-result` CLI through
the existing command-scoped web environment. Owner-receipt recovery is not duplicated.
No engine or native study runs in the API process; the API cannot choose another command.

Clients provide only a UUID path identity. Every query string and nonempty GET body
is rejected with the existing redacted ApiErrorV1 response (422); malformed identities
and unsupported methods use the existing validation/error handlers. No client path,
profile, source, runtime, data-directory or environment selector is accepted. A UUID
is identity, not authentication: this inherits the existing loopback single-user
Workstation access model and introduces no authentication or remote-access settings.

## Deployment configuration

The dedicated NativeResultSettings subclass uses the existing AlphaSettings ALPHA_
environment/.env mechanism. These are non-secret server deployment fields:

| Field | Meaning |
| --- | --- |
| ALPHA_DATA_DIR | Existing shared Workstation store root; this slice requires a disposable synthetic fixture marker. |
| ALPHA_NATIVE_RESULT_SOURCE | Canonical existing pinned public RD-Agent source directory. |
| ALPHA_NATIVE_RESULT_RUNTIME | Canonical existing installed runtime bundle with its dependency lock, Python and pyvenv.cfg. |
| ALPHA_NATIVE_RESULT_MODE | Original closed fixture mode: resume, cancel, exhaust or tamper. |

All three profile fields default to absent. Missing/malformed configuration returns
unavailable before opening evidence or measuring assets. There is no snapshot-derived
mode, runtime search, environment credential lookup or paid/provider fallback. Settings,
source/runtime paths and configuration validation details never enter the response.
The feature adds no credential configuration and does not dump deployment settings.
Use trusted deployment configuration only; the API cannot set or persist these fields.

Normal stores, daily-study roots and unmarked arbitrary directories are unavailable
for this synthetic-only slice. No retained production data path is newly admitted.
A configured profile must still match the job's exact recorded contract, reservation,
consumption, owner and profile evidence. Wrong jobs, changed profiles and missing
receipts cannot cause a launch, reconciliation, redispatch or allowance reset.

## Read contract

A successful HTTP read returns NativeStockOperatorResultV1 with status completed,
invalid or unavailable. HTTP200 describes the read operation; domain invalid/missing
proof remains explicit in its JSON status. completed means exact artifact retrieval,
not accepted science, study settlement, current approval or runtime qualification.
Only completed responses contain the parsed validated receipt, synthetic result and
false feedback. Incomplete responses forbid those fields. Provenance hashes identify
the original byte snapshots; they do not hash reserialized response JSON.

The route uses dedicated closed nested response models and existing immutable owner
observations. Current receipt bytes must match the recorded owner hash; selected
profile and request declarations must match; cancellation/failed status and uncertainty
block recovery. Legacy rows without stock observations remain unavailable, never
backfilled. Every response retains synthetic_only_unqualified, resume_allowed=false
and scientific_acceptance=not_admitted. No cross-owner or mid-stage retry exists.

## Engineering assumptions and limits

The canonical requirement is W04 typed receiver binding for W02/T10; the following
API limits are conservative engineering defaults, not new scientific/budget policy:
source preflight4096entries/2048files, each source file4MiB and aggregate32MiB; runtime
Python64MiB, lock1MiB, pyvenv.cfg64KiB. CLI stdout/response128KiB, discarded stderr8KiB,
read deadline30seconds and the existing retained-child group cleanup (0.25second grace). The existing installed alpha
wrapper must be available on the trusted server PATH. Nonzero CLI invalid/unavailable
states remain typed; unsupported exits, malformed/duplicate JSON and timeout fail closed. Source metadata rejects
symlinks/special files; the existing venv Python symlink is allowed only as a bounded
regular resolved file. Existing exact artifact caps, duplicate-key checks, query-only
store reads and profile pin/fingerprint validation remain unchanged.

The retained read-child helper requires Linux and default SIGCHLD handling; unsupported
conditions fail closed. It observes exit without reaping, cleans the owned process group
even after leader exit, and only then releases its PID anchor. Unverified cleanup is
unavailable; a released numeric process group is never retried. This owns only the
fresh read command, not any recorded native worker or study process.

Configured assets must be trusted and stable. Metadata preflight is not an atomic
filesystem snapshot, hostile-writer sandbox or hard OS-level execution quota. SQLite
read-only access can use/create WAL/SHM sidecars; no database records are initialized,
repaired or mutated. Source/runtime measurement does not qualify every installed
package or prove historical runtime immutability. Full/private qualification remains
unverified. No frontend, Qlib Results, saved inspector, paper reader, ControlStore or
accounting implementation changes are required.

The only shared mount changes are in app.py: native_results_api import after ml_api,
and include_router immediately after jobs_api. Existing paper/research router entries
remain intact. The source-reader successor was unavailable in this executor; the exact
hunk was relayed to the coordinator and actual combined-tree integration remains to check.

## Reproduce bounded API proof

Public test_native_result_api.py creates a fresh approved/reserved synthetic fixture
using existing helpers and launches the actual pinned native loop once outside the API.
It then starts fresh Python subprocesses with explicit non-secret deployment variables
and calls the real create_app() route through TestClient (no Uvicorn/socket listener).
Fixture audit covers both fresh server and the actual installed alpha child: network,
credential reads and non-read command execution are denied; ControlStore write-open
is forbidden. The sole fixed result-read command is allowed. No provider credentials,
HOME or Codex authentication configuration cross the existing CLI environment boundary. Completed, missing/invalid config, profile/job mismatch, exact-byte change,
corrupt/missing receipt, ownerless/corrupt store and late-cancel cases are captured.
Whole-store row dumps remain unchanged by the API requests. No provider/model call,
real market input, installation, protected suite or live service is part of this proof.
