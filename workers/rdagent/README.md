# Pinned native loop development probe

This isolated Python 3.12 project exercises RD-Agent commit
`484776c211e4fbbeef03e0ec00d6bbee7362a4f4` with fixed synthetic inputs. It has no application
dispatch route. No ALPHA package imports this worker. `NativeFixtureLoop` explicitly uses
upstream `LoopMeta` and inherits upstream `run`, `_run_step`, `dump` and `load` without overrides.
That original fixture never imports or instantiates stock `RDLoop`; the separate
stock continuation diagnostic below does.

## Reproduce

Obtain upstream commit `484776c211e4fbbeef03e0ec00d6bbee7362a4f4` as a pristine checkout, either
from `https://github.com/microsoft/RD-Agent/archive/484776c211e4fbbeef03e0ec00d6bbee7362a4f4.tar.gz`
(expected archive SHA-256 `4c5d1c792b133d7148bb4d59aea09b8accf4d14deb4a10ffed276ce178dd855c`) or by
fetching that exact commit with git and checking `git rev-parse HEAD`. Keep it unmodified.
Its root contains a top-level `test/` package, which the shadow check below always rejects because
`test` is a standard-library name. Point `ALPHA_RDAGENT_SOURCE` at a separate derived root holding a
byte-identical copy of `rdagent/` plus upstream `LICENSE` (and optionally `pyproject.toml`); nothing
outside `rdagent/` is imported. Record the pristine origin, HEAD and every excluded entry.

The probe verifies all 694 files under `rdagent/` (except bytecode) against the aggregate digest
in `source_pin.py` before any upstream import, rejects symlinks/drift and records each imported
source file's hash. That tree digest is the only measured source identity: results report
`source_pin.verified.source_tree_sha256`, while the commit and archive checksum appear only under
`source_pin.expected` and are listed in `source_pin.not_verified`. Verify the archive checksum
yourself when you download it. Source remains external; no upstream scheduler is vendored here.
The external source root is never placed on `sys.path`: a narrow finder resolves only `rdagent`
within the verified directory and binds each worker helper to its reviewed source file. Importable
source-root shadows of worker, standard-library or installed dependency modules are rejected.
The fresh bytecode cache is selected before importing even the local source verifier. Every
successful probe validates both upstream and worker helper origin hashes.

From the repository root, using the normal ALPHA test environment:

```sh
uv sync --locked --project workers/rdagent
ALPHA_RDAGENT_SOURCE=/absolute/path/to/derived-rdagent-484776-root \
  uv run --no-sync pytest -q tests/unit/test_native_loop_conformance.py
```

Optionally set `ALPHA_RDAGENT_RECEIPTS` to a disposable evidence directory. Each probe writes a
unique JSON receipt there, preserving failures across reruns. Without an explicit source path,
the public tests skip and confer no native qualification. The isolated `uv.lock` is a focused
import dependency subset, **not** upstream's full application dependency environment. Root
dependencies and lock are unchanged.

## Install on a development machine

`bash scripts/setup_rdagent.sh` (idempotent; about 1.1 GB, under a minute with a warm uv cache)
fetches the pinned commit into `.alpha/state/runtime/rdagent-pristine` when absent, derives
`.alpha/state/runtime/rdagent-source`, verifies the source-tree digest, syncs `.venv` and builds
and validates `.venv-rule-qualified` and `.venv-economics-qualified`. It is the RD-Agent part of
`ALPHA_CLOUD_FOUNDATION=1 ALPHA_CLOUD_RDAGENT=1 scripts/cloud_setup.sh` without Git hooks, npm,
browser download or fontconfig. All of it is gitignored (`.alpha/state/`, `.venv-*/`). It prints
`export ALPHA_RDAGENT_SOURCE=…`, which runs the conformance, W04, rule and daily tests. The daily
tests also need the qualified Docker image below. `ALPHA_STOCK_PYTHON` (stock `RDLoop`) is NOT
provisioned: that runtime needs upstream packages (`docker`, `litellm`, `openai`, `tiktoken`, …)
that no committed lock pins. Smoke check: `uv run python scripts/run_owned_test.py -- uv run pytest
-m smoke tests/smoke/test_rdagent_smoke.py`.

## Contracts exercised

- `direct_exp_gen` returns native `Hypothesis` and `Experiment` under `propose`/`exp_gen`.
  Coding is a noop, running attaches only fixed metrics, feedback is a native
  `HypothesisFeedback` subclass, and record uses native `Trace.sync_dag_parent_and_hist`.
- SUPPORTED, CONTRADICTED, INCONCLUSIVE and INVALID are **supplied synthetic labels**, not
  classifications produced by ALPHA's scientific acceptance logic. Labels and metric names,
  values and units survive recording and signed checkpoint loading. Native `decision` and
  `acceptable` remain false for every fixture; truth conversion raises instead of collapsing
  a label into generic success. No label grants evidence or approval authority.
- Native `run(step_n=0)` executes one stage; `step_n=1` executes two. These post-effect stop
  knobs are not admission budgets. A separate ephemeral fixture allowance checks each stage
  before its fixed operator, and remains outside the pickle. It tests only the fixture guard,
  **not ControlStore reservation, settlement, exposure or economics integration**.
- One live fixture owner guards the entire run/load/resume operation. Native tasks are drained
  before unlocking. Duplicate start, stale/foreign checkpoint and concurrent continuation are
  rejected. Successful checkpoints resume once under that same owner. Cancellation closes the
  owner and retains the fixture charge for interrupted work.
- Upstream advances its in-memory cursor in `finally` even when a stage is cancelled, but writes
  no checkpoint for that incomplete stage. Tests load the actual last successful checkpoint
  and reject further execution through the cancelled owner. No durable consumption ledger or
  cross-owner recovery is added.

## Scope and limits

Every test launches a new sanitized subprocess in an empty temporary directory. Environment,
HOME, log path, signing-key path and bytecode cache are fixture-local. The key is generated by
the existing upstream signed-pickle implementation. An import allowlist excludes backends and
stock loops; Python audit tripwires reject network connection/DNS and subprocess effects. These
checks contain trusted fixture mistakes; they are not hostile-code or same-UID security isolation.

No real provider, LLM, generated code, market data, holdout, broker, live database, migration or
real owner-approval action executes. ALPHA retains admission/budget/exposure/execution/economics/
evidence/approval responsibility. Owner-death recovery, physical containment, production
activation and scientific artifact admission remain unqualified. Public focused checks are not a
full gate or release approval.

## Bounded W04 admission fixture

`test_native_w04_admission.py` composes this actual child with the existing synthetic process
owner and scratch-created ControlStore. It approves measured worker/code/lock/interpreter/config
fingerprints through existing synthetic test helpers, reserves the full remaining D1 envelope,
requires one reserved variant and positive CPU allocation, and commits a single trusted owner
claim before child effects.
The closed `native_loop` launcher accepts only fixed fixture modes; there is no caller command,
dynamic operator, provider, model or production route. Interpreter/config and lock identity are
measured; they do not qualify the installed dependency environment or enforce CPU/token usage.

The child receives a reference-only JSON admission identity, never a ControlStore handle or owner
lock. Its existing ephemeral stage guard derives `loop_steps` from the actual reservation. The
signed native pickle includes a digest of job/reservation/spec/manifest/owner/mode/allowance.
Resume is allowed only in the same live child; path, byte digest and admission binding are checked
before continuing. The reserve is charged once and never restored from checkpoint state.

The supervisor retains the actual native child handle and applies the existing independent lease
and process-group cleanup. After cleanup, exact feedback labels and metric names/values/units are
validated against the admitted fixed mode. Every successful result remains process-only and
`pending_scientific_admission` / `not_admitted`. No scientific run ID or completed D1 attempt is
invented. Failure/cancellation reconciles through existing failed-attempt/link/status records;
unknown cleanup or result/journal publication retains capacity and the complete charge.

The W04 process-only lifecycle event schema and fields are unchanged. The later closed rule
workflow adds the narrowly validated `rule_result` binding described below; old readers must not
write/read those new outcomes in a mixed deployment. Study `ExplorationMandateV1`
references grant no launch authority; this fixture is not a new registration in the closed
scientific operator registry. It exercises existing reservation exposure, not generic study/trial
admission or scientific acceptance. Full resource metering, durable scientific artifact admission,
cross-owner recovery and production activation remain W08 gaps. See
[`2026-10-26-native-w04-admission.md`](../../docs/work/archive/2026-10/2026-10-26-native-w04-admission.md).

## Closed frozen-rule authority profiles (2026-10-26)

See the [current handoff plan](../../docs/work/archive/2026-10/2026-10-26-native-rule-authority.md).
The old `.venv` and `uv.lock` above remain the W04 conformance environment. Two **fresh-only**
environments add closed position and costed synthetic profiles, with hash-pinned requirements
reusing already approved root/worker versions. Root `uv.lock` is unchanged. The economics profile
uses root-pinned Nautilus 1.228.0, pytz 2026.2 and tqdm 4.68.2; it does not overwrite the old profile.

On a fresh checkout with the normal locked root environment and complete pinned upstream available:

```sh
uv venv --python 3.12 workers/rdagent/.venv-rule-qualified
uv pip install --python workers/rdagent/.venv-rule-qualified/bin/python --require-hashes --no-deps -r workers/rdagent/rule-requirements.lock
.venv/bin/python -B workers/rdagent/install_rule_profile.py
uv venv --python 3.12 workers/rdagent/.venv-economics-qualified
uv pip install --python workers/rdagent/.venv-economics-qualified/bin/python --require-hashes --no-deps -r workers/rdagent/economics-requirements.lock
.venv/bin/python -B workers/rdagent/install_rule_profile.py --economics
```

`.gitignore` now covers both through its `.venv-*/` entry (checked 2026-11-14 with
`git check-ignore`); `cloud_setup.sh` still also lists `/workers/rdagent/.venv-rule-qualified/` and
`/workers/rdagent/.venv-economics-qualified/` in the clone-local `.git/info/exclude`. Unignored, the
generated environments would be hashed into the gate tree and scanned by ruff and semgrep as source.
These are generated-environment excludes, not test or coverage exclusions.

Do not run these commands over preserved environments. The installer copies complete noncache
source/resources, compares original distribution metadata to pyproject, preserves Requires-Dist,
and writes honest source-install provenance and RECORD. It invokes no build backend and installs
no editable hooks. It rejects symlinks, duplicate metadata and unexpected site hooks. Profile
inventories bind every installed dependency/source byte, source pyprojects and root/profile locks;
pre-effect admission and result checks compare them to the owner-approved fingerprints. Runtime
imports record actual package and metadata origins. Fresh bytecode is selected before imports.

The positions profile omits Nautilus, so alpha-strategies has an explicitly unsatisfied declared
dependency. Economics includes Nautilus and its required closure; alpha-data still has unqualified
provider dependencies, listed precisely in its installed PROFILE.json. Full package API qualification
is false for every local distribution. No fallback root sys.path or merged package environment is
used. These are local fixture source installations, not built wheels or upstream full applications.

V1 evaluates the original visible bars through actual rule_signal. V2 owns a separate seven-row
synthetic dataset (one warmup and six execution bars); it runs actual run_backtest/RuleStrategy
sequentially for the baseline and flat control before Feedback. The unchanged audit hook was
exercised by the real compiled engine. Only serializable canonical results enter checkpoints;
Nautilus resources are disposed by the canonical engine. Synchronous execution relies on the
external supervisor deadline; no immediate cooperative cancellation or hard real-time claim is made.

An exact approved contract and consumed real local-confirmation receipt are required before the
existing reservation/claim. Two outcome exposures share one trial. D0 uses the existing three-variant
engineering allowance; the caller must explicitly approve a sufficient budget. No repair/default
budget is invented. Signed checkpoint continuation and publication recovery do not create another
trial or refund charges. Scientific acceptance and empirical W08 remain blocked.

### Observed result byte binding

For closed rule success only, the trusted supervisor validates one bounded receipt read after
cleanup and records `rule_result` with nested schema `SyntheticNativeRuleObservationV1` and the
SHA256 of those same bytes. The existing100000-byte fixed receipt cap is enforced during that read.
This field is accepted only for the registered native rule reservation and clean successful
outcome; original process-only V1 fields stay unchanged. The issuer detaches and freezes the
closed nested string mapping; journal serialization copies it without exposing mutable owner
evidence. The hash alone proves no execution.
Completion compares the captured bytes to the trusted observation, publishes those exact bytes,
and pins `native_receipt_ref` in existing immutable attempt details. The verified completed-attempt
reader rechecks it before accepting derived numerical artifacts; general case summaries return
metadata and do not revalidate D1 artifacts. Self-consistent rehashing
of receipt/economics/projections cannot replace the recorded result. No SQL schema or ledger is
added. Unbound historical rule outcomes/artifacts cannot be upgraded into completion; retained
charge/capacity and investigation are required. Older writers/readers do not understand the new
rule binding; deployment cutover remains unqualified. Generic standalone UI/report readers keep
their existing integrity/unknown-state behavior and are not newly qualified by this boundary.

### Storage and history preflight

Linux execution may use the existing `cloud_root_identity` backend with control, manifests,
runs and bulk on one explicitly retained mount/device/owner. A study with a temporary duration
still needs retained storage: `/tmp`, tmpfs and overlay roots remain rejected, and the reserve
is still the larger of 15% and 100 GB. Verify underlying capacity and retention too; free space
reported by a thin virtual disk is not proof of available backing-disk space or a backup.

This option does not change the native `macos_volume_uuid` backend. Keep existing Mac profiles,
archives and authoritative history intact. A separate Linux root must not evade the existing
database-wide one-trial reservation guard. No new Mac/Linux UUID bridge is implemented.

Before designating an execution root, run the explicit-root metadata reader against existing
authority, using the installed project environment:

```sh
uv run python scripts/inspect_daily_rule_history.py --data-dir /absolute/existing/data
```

It opens one read-only schema-7 snapshot, selects closed routing metadata rather than project
prose or full contracts, and counts daily deep reservations across all projects. Counts cover
the entire selected store even when the contract list is paged. Event-study job counts also
cover unlinked jobs and other research routes; they do not prove process liveness. Malformed,
oversized, missing or older-schema history is unknown, never an empty installation. SQLite may
use WAL/SHM sidecars; this path does not write database records or change journal settings.

The report always grants no authority to initialize, migrate or switch roots. Reconcile prior
and unknown records first; do not import artificial ledgers, copy stale authority over later
state, or reset consumption. Actual activation still requires qualified Linux process/container
boundaries, retained storage, real input bindings and exact local owner confirmation. See the
[implementation record](../../docs/work/archive/2026-10/2026-10-31-linux-storage-history.md).

## Stock RDLoop continuation diagnostic

The additive `stock_fixture_entry.py` now executes the actual pinned
`rdagent.components.workflow.rd_loop.RDLoop`. Its constructor loads fixed native
Scenario, HypothesisGen, Hypothesis2Experiment, Developer (coder/runner) and
Experiment2Feedback implementations from `stock_fixture.py`. All five stock stage
methods and upstream run/dump/load remain unchanged; the trace guard delegates
recording to native `Trace.sync_dag_parent_and_hist`. This uses an isolated pinned
source loader, not the stock CLI or a financial scenario.

The public `test_native_stock_fixture.py` obtains a reference through
`alpha_cli.native_stock_fixture.request_from_owner`, checking the existing exact
synthetic owner, canonical running reservation, cancellation, code/evaluator
fingerprint and minimum reserved envelope. It runs only with explicitly supplied
`ALPHA_RDAGENT_SOURCE`, `ALPHA_STOCK_PYTHON` and `ALPHA_STOCK_RECEIPTS` paths.
Root test dependencies and the full native application environment are separate;
no installation or dependency change is part of this slice.

The child rejects malformed/oversized requests before native imports, rechecks
worker/source identity, clears inherited environment, uses public synthetic
signing material and rejects network, provider, shell and credential-file effects.
Only the existing read-only `uname -p` and `ldconfig -p` dependency import probes
are allowed. No generated code or real tool executes.

Native `step_n=1` completes proposal AND coding before stopping. The last successful
signed checkpoint is hash-checked and loaded into a fresh checkout directory;
remaining running/feedback/record stages complete without repeating earlier
attempts. Pre-effect counters stay in the live fixture guard outside the pickle.
Tests also inject actual `asyncio.CancelledError` before the runner body, exhaust
fake model allowance before feedback and tamper checkpoint bytes before load.
The cancelled guard cannot continue, and the last successful checkpoint survives.
Cross-owner/process restart recovery remains unqualified.

`validate_stock_artifacts` reads bounded JSON and checkpoint bytes only, never
unpickles worker artifacts. It checks exact request/hash bindings, native class,
stage order, trace history/parent/loop identities, fixed synthetic observations
and unaccepted feedback. Canonical JSON comparison rejects boolean/numeric type
substitutions independently of hashes. Successful diagnostic output remains
`synthetic_only`, `not_admitted` and `production_dispatch=false`.

These references and counters are NOT durable consumption or a new ledger.
Repeated reference creation does not prevent another process from reusing one;
the whole existing reservation remains unchanged. CPU allocation is checked but
not enforced as a CPU cap; tests apply their own 40-second child timeout and reap
it. This does not qualify provider/subscription limits, dollar caps, installed
dependency integrity, hostile-code containment or production process ownership.
The standalone diagnostic adds no launch authority; the retained-owner successor
below extends only internal synthetic dispatch, using the existing accounting store.
Production registration, durable execution ownership, scientific admission,
protected-suite/full-gate qualification and independent release review remain gates.

## Retained-owner stock dispatch successor

`StockFixtureLaunch` is a second exact, closed launch identity accepted by the
existing internal synthetic owner. It inherits the non-scientific NativeLaunch
shape but rejects every study/authority and arbitrary mode. The runtime selector
names an existing bundle containing `venv/bin/python`, `venv/pyvenv.cfg` and
`dependencies.lock.txt`. Code/source/worker/interpreter/config/lock identity is
bound into the canonical approved invocation. This measures a runtime; it does
not install or qualify its dependencies, grant inference or bypass storage rules.
No public research command or production activation is added.

The existing `start_synthetic_owner` reconstructs that exact identity in its
retained owner process. `_Owner.spawn`, its `Popen`, immediate safety lease,
process-group cleanup and existing immutable observations remain the launch path.
The child receives only a fixed bounded reference, neither owner lock nor store.
The supervised workspace requires the existing synthetic marker and exact job
path. Its own environment is cleared before native settings import.

A stock claim carries its full launch-profile hash. Immediately before spawn,
`consume_before_spawn` uses the existing ControlStore write transaction to validate
the live owner/claim, active reservation, unchanged profile, stop/deadline state
and the fixed reserved envelope. One protected `native_invocation` event in
existing `job_events` records five stages/two fake-model/two fake-tool attempts;
commit precedes `Popen`. It is whole-invocation consumption, not measured API
usage or another ledger. No reservation/balance row is rewritten or refunded.

Rollback prevents spawn. A committed consumption followed by cancellation,
process-creation failure or lost availability cannot be reminted. Existing durable
claims prohibit relaunch after owner exit/reopen; start requires prior stock
consumption. Generic journal append cannot write the private event. Legacy
histories without stock markers remain readable; malformed stock events on
legacy claims are rejected. Readers/writers must deploy coherently: older readers
cannot validate the new scoped claim/event; no history migration is performed.
The earlier synthetic-model-allowance prototype has a different fixed profile
and grants no authority for this route; it is not copied as a second ledger.

A successful retained stock child must pass the same strict artifact validator.
The returned bounded receipt bytes are rechecked against the validated hash,
preventing replacement between validation and publication. Every result remains
synthetic/process-only and `not_admitted`, with no scientific run/D1 completion
invented. Internal dispatch now executes this fixture; production registration,
actual provider/subscription/token/USD enforcement, CPU caps, full installed
runtime integrity, arbitrary-descendant containment and full project qualification
remain separate gates. No live inference or other-host work is part of this slice.

## Typed stock-worker boundary successor

[Worker hardening](../../docs/operations/native-worker-hardening.md) records targeted
Python3.11 stock-runtime typing separately from the lighter conformance environment.
Its closed request/audit/context/result checks keep the exact native RDLoop and the
existing three-file worker manifest. Changed bytes require freshly derived profiles;
old approvals/history are not rewritten. Synthetic execution remains unqualified for
live inference, scientific admission or hard budget enforcement.
