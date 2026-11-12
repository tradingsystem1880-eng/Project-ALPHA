# Inspect a synthetic native stock run

This diagnostic is for existing disposable synthetic stock fixtures only. It does not
run RD-Agent, reconnect an owner, load a pickle, reset allowance, retry a dispatch or
admit research evidence. Canonical v9 W02/T09/T10 inspection improves here; T07
cross-owner restart continuation remains unfinished.

From the successor source environment, inspect an existing fixture job:

```sh
python -m alpha_cli.native_stock_inspect --data-dir /tmp/alpha-native-fixture-EXAMPLE --job-id 00000000-0000-4000-8000-000000000001
```

Use the actual existing root/job identity. The command will not create a missing store.
It requires the synthetic-only marker, canonical job UUID, existing stock claim and
validated lifecycle journal. Daily-study workspaces are rejected. The SQLite connection
is read-only/query-only; SQLite may use WAL/SHM sidecars. No database records are written.

The JSON separates durable invocation consumption and observed process outcome from
worker progress. A charged stage is an **attempt before its body**, not completed work.
The fake-model attempt count comes from attempted stages; `simulated_model_counter`
can additionally contain the deliberate exhaustion injection. Neither is a spend ledger.
The progress file is atomic, bounded advisory evidence; its self-digest and dispatch
identity do **not authenticate its worker profile**. That binding remains explicitly
unverified. `success_receipt` remains unverified unless a new sealed stock observation
matches the exact current receipt bytes.
`artifact_validation` separately validates one bounded snapshot of current receipt,
trace and checkpoint bytes, including the exact synthetic contract and dispatch
identity. Each file is read once and those same bytes are hashed. This works without
advisory progress and never deserializes the checkpoint. It does not establish that
these are the bytes previously observed by the owner. New successful stock outcomes
now separately persist `stock_result` with schema `StockRDLoopObservationV1` and the
validated receipt hash; the distinct `rule_result` schema remains study-only. Old
stock rows without the observation remain unavailable and are never backfilled. A snapshot saying
completed cannot override missing/failed owner evidence or establish scientific acceptance.

For interruption or failure, preserve the original root and inspect the same job from
a new process. Inspect `invocation_consumed`, `observed_start`, `owner_outcome`,
`owner_returncode`, `owner_uncertainty`, and advisory `progress` together. Missing
snapshots are unavailable; malformed/differently bound or unsafe progress is separately
reported as `progress.status: invalid`, so it cannot hide independently valid success
bytes. Invalid journal/store/claim identity produces a fixed `invalid_or_unavailable`
JSON envelope (exit 2). Missing success receipts are separately unavailable;
invalid/incomplete success artifact snapshots are reported as
`artifact_validation.status: invalid`. Exit 0 means a diagnostic
report was generated, not that a run succeeded. Abrupt loss may leave an older snapshot; the
last attempted stage never proves completion. The copied coding checkpoint is only
hash-checked bounded bytes; no deserialization occurs. It is not necessarily the latest
upstream scheduler checkpoint.

Every report says `resume_allowed: false` and `resume_authority: none`. The original
issuing process, retained owner lock and outside-pickle guard are required by existing
continuation controls. This inspector cannot recreate them. If ownership is lost, keep
the outcome unresolved and reconcile through the existing owner process; do not start
a replacement job, borrow a reservation or refund/reset counters from these files.

Evidence limits: synthetic deterministic components exercise stock upstream RDLoop;
no real model inference, semantic research, economic validity, production dispatch
qualification, full-suite or private-suite acceptance is claimed. Claude review was
unavailable in the build environment; independent review uses Codex and is recorded in
the successor handoff. Shared generated outputs and production authority are unchanged.

## Compare an explicitly selected current profile

To compare current public source/runtime files to the recorded stock invocation, provide
all three selectors together. No mode, runtime or source is inferred from progress,
receipts, environment variables or authentication state:

```sh
python -m alpha_cli.native_stock_inspect --data-dir /tmp/alpha-native-fixture-EXAMPLE --job-id 00000000-0000-4000-8000-000000000001 --profile-source /path/to/pinned/public/source --profile-runtime /path/to/existing/runtime-bundle --profile-mode resume
```

Use the actual existing paths and originally selected mode (resume/cancel/exhaust/tamper).
The verifier rebuilds the recorded spec from the contract and reservation within one
read-only snapshot, verifies content/spec identities and the consumed profile, and reads
the current files through the existing StockFixtureLaunch measurement. It does not call
its command, request, admission or execution methods. It compares both the full profile
fingerprint and the complete implementation fingerprint dictionary. A second measurement
must agree; unstable or missing proof fails closed as unavailable.

`profile_verification.status` is verified, mismatch or unavailable, always scoped to
`current_files_match_recorded_only`. Verified means the selected current identity matches
the recorded profile. Changed mode/controller/worker/runtime/lock identities produce a
mismatch; missing selection, missing files, rejected source pin or invalid recorded proof
are unavailable. Neither status repairs records, chooses another runtime or changes an
allowance. Changed controller bytes legitimately prevent verifying older records.

Runtime measurement covers the existing Python executable, pyvenv.cfg, absolute runtime
selector and declared dependency lock. It does not measure every installed package or
qualify runtime behavior. It cannot prove the historical bytes that actually executed;
that remains unavailable even when the current profile matches. Existing historical
`worker_profile_binding` fields remain unverified for that reason. Legacy stock outcomes
lack a durable receipt hash; this profile verifier does not manufacture one. New
stock outcomes can independently establish owner-observed artifact-byte binding.

Each independently valid progress/receipt request also gets `profile_declaration.status`.
That separately compares its declared three-worker-file manifest, explicit mode and CPU
limit against the selected matching profile and recorded reservation. The worker manifest
is different from the full launch-profile fingerprint. CPU is outside that fingerprint;
its existing min(60000, reserved CPU) bound is checked separately. Native request validation
retains the existing fixed 5/2/2 limits. A self-consistent but altered request may pass
current byte validation while its declaration reports mismatch. Invalid or absent evidence
cannot become verified. None of these results proves execution success, scientific
acceptance, ownership, current approval or permission to resume. No T07 takeover exists.

## Execute the existing native fixture and recover its result

The actual same-owner continuation boundary is the existing post-coding checkpoint:
stock RDLoop stops normally at its step limit, verifies the checkpoint hash, then
loads it in the same worker process with the same live Effects counters and executes
running, feedback and record. No step repeats. This is already the fixed `resume`
fixture behavior. A cancelled/failed stage closes the guard; it cannot be reopened.
T07 process/owner replacement and mid-stage interruption retry remain unsupported.

For a fresh **already approved/reserved synthetic-only job**, the existing launch API
remains `StockFixtureLaunch(public_source, "resume", stock_runtime=runtime_bundle)`
passed to `start_synthetic_owner(root, job_id, fixture="native_loop", seconds=40,
native=launch)`. This requires the original approved profile, reservation and issuing
process/retained lock; it rejects consumed jobs. Do not create a replacement dispatch
for recovery. This diagnostic feature creates no job, approval, reservation or budget.

On clean success, that retained owner validates receipt/trace/checkpoint, freezes the
exact receipt hash in a distinct stock observation, and commits it with the existing
job/reservation/spec/owner binding. The new field has no rule-study acceptance meaning.
No reservations, balances, consumption or scientific state are settled or reset.
Uncertain/nonstock outcomes and mixed rule/stock observations cannot produce a valid
stock observation. A cancellation racing after clean receipt validation can coexist
with that byte observation while the existing job closure becomes cancelled. Recovery
reads cancellation/failed status in the same snapshot and stays unavailable even when
those exact owner-observed bytes still match. Old rows remain readable without new proof.

Run the existing inspection command with all three explicit profile selectors after
completion (from a new process if needed). `result_recovery.status: verified` requires
an exact validated artifact snapshot, owner-observed receipt-hash match, selected current
profile match and request-declaration match. This recovers the result bytes and bindings;
it does not deserialize/resume the checkpoint. Missing proof stays unavailable, changed
exact bytes or stale profile report mismatch—even if parsed JSON semantics still match.
The result stays synthetic/unaccepted and reports `resume_allowed: false`.

`owner_receipt_match` is reported separately from profile eligibility. A receipt may
match its durable owner observation while the selected current profile is unavailable
or mismatched; that cannot produce a verified result-recovery workflow. Losing the
original owner does not grant permission to relaunch, restore counters or publish.

## Canonical result command and fixture preflight

Use the existing read-only diagnostic group for the result-retrieval operation:

```sh
alpha research diagnostic native-result --data-dir /tmp/alpha-native-fixture-EXAMPLE --job-id 00000000-0000-4000-8000-000000000001 --profile-source /path/to/pinned/public/source --profile-runtime /path/to/existing/runtime-bundle --profile-mode resume
```

All five selectors are explicit and required. The command is discoverable through
`alpha research diagnostic --help`; its diagnostic prefix keeps it out of the new-run
catalog. The existing module inspector remains available for lower-level diagnostics.
This command calls the same recovery function and creates no job, owner, reservation,
allowance or artifact. It never launches or resumes a worker.

Preflight for a synthetic engineering proof: use the already installed ALPHA Python3.12+
console environment and existing pinned native Python3.11 runtime bundle/public RD-Agent
source. No installation, Docker, provider/model access or credentials are needed. The
root must be a disposable Linux synthetic fixture with its exact marker and existing
approved/reserved stock job; source/runtime/mode must match its recorded profile. A fresh
native fixture run uses the existing retained-owner API and existing admission controls.
Those fixture-setup helpers occur only in public tests, never in the operator callback.
Owner loss/consumed dispatch does not authorize starting a replacement.

Output schema is NativeStockOperatorResultV1. `completed`/exit0 means result retrieval
completed: receipt and synthetic result values passed the existing exact snapshot,
owner-byte, selected-profile, declaration and cancellation checks. It does not mean a
research study was accepted or settled. Receipt values are parsed validated JSON;
provenance SHA256s refer to the original exact artifact bytes, not reserialized output.
`invalid`/exit2 covers mismatched/corrupt result artifacts. `unavailable`/exit3 covers
missing owner binding/receipt/proof or cancellation. Invalid/unavailable output never
includes receipt or result values. Usage errors are handled by the normal CLI parser.
Errors expose fixed messages, never raw exception/SQL/path/prompt contents. Settings
are not loaded: no default data directory, dotenv, authentication or provider fallback.

Reproduce the native command-level proof from this candidate using the existing installed
environments, with a new empty evidence directory and explicit non-secret fixture asset
selectors ALPHA_RDAGENT_SOURCE, ALPHA_STOCK_PYTHON and ALPHA_STOCK_RECEIPTS. Run the new
public test file tests/unit/test_native_stock_operator_cli.py with candidate apps/alpha-cli/src,
packages/alpha-core/src and repository root on PYTHONPATH. Its fixture launches the real
stock native loop once, then invokes the installed alpha console in fresh subprocesses
for completed, changed bytes, corrupt JSON, missing receipt, missing owner and late-cancel
outcomes. Test fixtures remain synthetic; no empirical/live/model qualification follows.
