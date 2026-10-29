# Frozen rule native authority

Status: available synthetic workflow assembled onto bc5; scoped public regressions and cheap checks passed. Exact source identity, independent final-review disposition and remaining acceptance blockers are in the assembly packet below. Engineering only, no empirical approval.

**Current active work (2026-10-27):** the unpublished Linux cloud foundation successor to the published checkpoint below: navigation/handoff routing and gate/review freshness repair. Stage contract, evidence identities and ordered backlog: [Foundation stage contract and handoff](#foundation-stage-contract-and-handoff-icm-aligned-alpha-adaptation). Status and blockers: [build record](../../BUILD-STATUS.md#2026-10-27-linux-cloud-qualification-checkpoint-published-not-accepted); review-scope repair: [gate preflight plan](2026-10-26-gate-preflight-selection.md#review-scope-alignment-2026-10-27). The Mac successor below is preserved and deferred: its open status and requirements stand, but it is not the current stage or active owner, and its scope is not abandoned.

**Canonical Packet 1 relation (2026-10-27, operational clarification):** the unchanged [Packet 1](../../context/feature-readiness-checklist-2026-10-27.md#packet-1-close-the-successor-exact-tree-gate) describes an interrupted de074 successor and its 48-of-49 result. That description is preserved historical prerequisite evidence: it is not the current c95 result and marks no feature complete. The published c95 checkpoint has public Linux gate and review evidence with private holdout coverage UNVERIFIED; the current foundation successor remains unpublished and unqualified. CHK27-PV01 resolves only through the private map and is not independently repository-accessible evidence. No equivalence between Packet 1 and this successor is asserted.

**Successor (open):** [Combined Mac portability qualification](2026-10-26-mac-portability-qualification.md#handoff-and-next-action), pending slice "Independent review and final successor qualification".

**Preserved published qualification checkpoint (Linux cloud, 2026-10-27, unmerged, not accepted):** branch `claude/cloud-qualification-c95f9d4d-20261027`, commit `2e0832c735d97c7da93cb79c0cce23e533dd7f1a` (tree `c95f9d4d803bef4be552736a79a4855e5bea5bf9`). Stage, repairs and limits: [Cloud qualification stabilization](#cloud-qualification-stabilization-2026-10-27); gate, review, evidence locations and blockers: [build record](../../BUILD-STATUS.md#2026-10-27-linux-cloud-qualification-checkpoint-published-not-accepted). Full scope: [canonical feature checklist](../../context/feature-readiness-checklist-2026-10-27.md); supporting history only: [build readiness handoff](../../context/build-readiness-handoff-2026-10-27.md). This pointer was added after that checkpoint and is not part of its tested tree.

```json
{
  "schema_version": 1,
  "title": "Frozen rule native authority",
  "context": "Engineer two closed versions of one frozen synthetic RuleSpec/control family through real owner confirmation, D0, native execution, canonical costed replay, immutable evidence and existing accounting.",
  "assumptions": [
    {
      "statement": "Existing owner confirmation and immutable contract records supply authority.",
      "verified_by": "owner_auth and ControlStore source inspection"
    }
  ],
  "alternatives_considered": [
    "Retain generic scientific refusal until the closed capability is qualified."
  ],
  "pre_mortem": [
    "A process-only receipt might be confused with market evidence.",
    "Changed package bytes could retain stale worker identity."
  ],
  "slices": [
    {
      "title": "Frozen protocol and confirmed approval",
      "verify": "tests/unit/test_native_rule_authority.py",
      "expected": "Exact inputs and real consumed owner confirmation required.",
      "rollback": "Remove the new protocol branch; retain existing reservations and immutable artifacts.",
      "status": "done"
    },
    {
      "title": "D0 and isolated real operator",
      "verify": "Focused rule/runtime tests",
      "expected": "Synthetic positions mechanically verified, full package bytes pinned.",
      "rollback": "Remove the new protocol branch; retain existing reservations and immutable artifacts.",
      "status": "done"
    },
    {
      "title": "Native execution and terminal accounting",
      "verify": "Explicit public lifecycle regressions",
      "expected": "One existing native owner and one full reservation with immutable baseline/control artifacts.",
      "rollback": "Remove the new protocol branch; retain existing reservations and immutable artifacts.",
      "status": "done"
    },
    {
      "title": "Compatibility and final review",
      "verify": "Scoped typing, lint, imports and independent review",
      "expected": "Existing readers remain exact; failures and tree receipts retained.",
      "rollback": "Remove the new protocol branch; retain existing reservations and immutable artifacts.",
      "status": "in_progress"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    "docs/BUILD-STATUS.md",
    "workers/rdagent/README.md"
  ],
  "out_of_scope": [
    "Empirical acceptance",
    "User-facing route activation",
    "New ledger",
    "Root dependency changes",
    "Commits",
    "Heavy full gate"
  ],
  "files": [
    "apps/alpha-cli/src/alpha_cli/_native_rule_protocol.py",
    "apps/alpha-cli/src/alpha_cli/_native_loop_admission.py",
    "apps/alpha-cli/src/alpha_cli/control_store.py",
    "workers/rdagent/native_fixture.py",
    "apps/alpha-cli/src/alpha_cli/_native_rule_economics.py",
    "apps/alpha-cli/src/alpha_cli/_native_rule_completion.py",
    "apps/alpha-cli/src/alpha_cli/_native_rule_projection.py",
    "workers/rdagent/costed_probe.py",
    "tests/unit/test_native_rule_authority.py"
  ]
}
```

## Planning sources

The authoritative adopted scope was read through the supported Library reader: master
`Project_ALPHA_Quant_Research_Upgrade_Master_Plan.docx`, file
`libfile_52e745af42b48191b032a5eeea0a23d7`, returned version1 (21pages/1306parsed lines);
and consolidated43-page checklist `libfile_181ac6079dcc8191b222b76c1f10bf17` (2648parsed lines).
Checklist version0 was requested; the reader omitted version metadata, so that version is not
independently verified. Both reads reached terminal `has_more=false`. This is text scope inspection,
not visual/PDF parity or proof that features exist. Master §§5,8A,12–14,16 govern this increment;
validation tasks retain the master W labels and broader scope. Source IDs are resolved references,
not invented local document paths. Exact read/transfer limits are in the executor handoff packet.

2026-10-27: the same Library checklist was reconciled to a 55-page revision (expected v1 per its
companion handoff; Library version not verified here). Its repository mirror,
[feature readiness checklist](../../context/feature-readiness-checklist-2026-10-27.md) (source
SHA-256 `ca06656cf4c873188373e9fa819c06d156c7e1224dcf61befeb8c5b636421cb2`), is the canonical
full-scope owner of the W01–W19 denominator and status; the master plan above remains this
increment's governing source. The 43-page read above remains this increment's historical planning input.

## Entry points and authority

This is the current-candidate inspection exception for the native workflow, reachable from
AGENTS → CLAUDE. It does not refresh unrelated context-map rows or supersede missing owner handoffs.
See [ADR-0038 owner confirmation](../../adr/0038-local-confirmation-and-terminal-archive-charts.md),
[capability authority](../../governance/capability-authority-matrix.md),
[artifact contracts](../../operations/research-platform-contracts.md), and the
[worker reproduction instructions](../../../workers/rdagent/README.md).

| Boundary | Current implementation |
|---|---|
| Exact plan, explicit budget, real consumed owner receipt | [alpha_cli._native_rule_protocol](../../../apps/alpha-cli/src/alpha_cli/_native_rule_protocol.py), [_native_rule_authority](../../../apps/alpha-cli/src/alpha_cli/_native_rule_authority.py), existing `owner_auth`/`ControlStore` |
| Source-bound qualified closure and approved native claim | [_native_rule_environment](../../../apps/alpha-cli/src/alpha_cli/_native_rule_environment.py), [_native_loop_admission](../../../apps/alpha-cli/src/alpha_cli/_native_loop_admission.py), [_native_fixture_store](../../../apps/alpha-cli/src/alpha_cli/_native_fixture_store.py) |
| Actual pinned LoopBase/LoopMeta and canonical engine | [workers/rdagent/native_fixture.py](../../../workers/rdagent/native_fixture.py), [rule_probe.py](../../../workers/rdagent/rule_probe.py), [costed_probe.py](../../../workers/rdagent/costed_probe.py) |
| Immutable completion and original accounting | [_native_rule_artifacts](../../../apps/alpha-cli/src/alpha_cli/_native_rule_artifacts.py), [_native_rule_completion](../../../apps/alpha-cli/src/alpha_cli/_native_rule_completion.py), existing ControlStore tables |
| Canonical snapshots, traces and existing chart/comparison readers | [_native_rule_projection](../../../apps/alpha-cli/src/alpha_cli/_native_rule_projection.py); existing snapshot/write_run_sidecars/chart_bundle/compare_runs APIs |
| Strict blocked real discovery projection | [_native_rule_protocol.real_discovery_readiness](../../../apps/alpha-cli/src/alpha_cli/_native_rule_protocol.py) (internal, inert, no acquisition/approval) |
| Public acceptance and recovery tests | [tests/unit/test_native_rule_authority.py](../../../tests/unit/test_native_rule_authority.py) plus original native/authority/artifact regressions |

## Versioned contract delta

`synthetic_frozen_rule_positions` versions 1 and 2 are closed dispatch branches. Unknown versions,
extra fields, changed rules/control/bars/cutoff/units/economics fail before effects. V1 retains the
original five-bar request and cutoff; actual visible outputs are [1,0,1] versus [0,0,0]. V2 is the
separately identified `FrozenRuleCostedReplaySyntheticV1`: one disclosed warmup close6 then six
execution closes [8,12,10,16,8,8], cutoff 2000-01-08 UTC. It never consumes the excluded v1 fifth bar.
The contract freezes next-open fills, USD cash12000, leverage0.1, fee10bps/slippage100bps, sizing,
warmup, required outputs and exploratory synthetic-only outcome policy. No scientific thresholds
or default owner quotas are inferred.

D0 is engineering input/operator conformance, consuming the existing three-variant pilot allowance.
Native baseline/control consumes two declared outcome exposures under one full remaining reservation.
The strict family-wide one-trial guard spans both versions, all project/display names and reapprovals
within one ControlStore. Same-job retry is idempotent; it grants no new quota, repair or refund.
No second ledger/index/coordinator is added. The generic native-owner write guard remains intact.

The costed native running stage calls the existing numerical engine twice for that admitted pair.
Its actual fills are 100@10.10/15.84 and75@8.08/7.92, fees3.79 and final cash12558.21; flat control
cash12000 with no fills. These match independently specified arithmetic. Positive synthetic cash
is not evidence of a market edge. No cost-sensitivity reruns are hidden in the admitted trial.

## Evidence, outcome states and compatibility

The new exact artifact commands are `research_rule_pilot_v1`, `research_rule_native_v1`,
`research_rule_costed_native_v1` and derived `research_rule_projection_v1`. Existing research_pilot
seven-file requirements, default double-bottom validators and W04 process-only readers remain
unchanged. Old scientific protocol validators retain their closed acceptance rules; no fake power/chart/event
statistics are inserted into legacy shapes. Generic v3 integrity readers can inspect additive
artifact sets, but integrity alone confers no scientific admission. Projection raw-result hashes remain separate from actual
approved code/source fingerprints. Canonical sidecars are recomputed and byte-checked on acceptance,
including a test that changes/re-hashes equity and selector metadata. Snapshot rows/hash/cutoff are
verified by the new fixture boundary.

| Outcome | Meaning and evidence |
|---|---|
| Protocol/authority rejection | Unknown/mismatched request or missing/replayed owner confirmation fails before effects |
| Synthetic engineering completion | Actual native running, same-live checkpoint after numerical work, clean trusted outcome, immutable baseline/control, full charges, capacity released |
| Valid zero activity | Predeclared flat control has zero fills and unchanged cash; no event-study mean is invented |
| Failure/cancel | Existing supervisor terminal failure accounting; original public lifecycle regressions apply |
| Unknown cleanup/publication | Capacity and full charges retained; publication-interruption test recovers same successful child without respawn |
| Empirical input blocked | Proposed BTCUSDT2020–22 has no admitted source/hash/cutoff/budget/owner-frozen real study |
| Scientific decision unqualified | Synthetic fixture cannot support or contradict a market hypothesis or calibrated inference |

## Executor receipts and resume

**Current assembly resume:** use [Current integration assembly](#current-integration-assembly) first.
Its full patch is already applied; do not apply it again. The numbered receipts below belong to
the preserved original source. Fresh assembly evidence is in the separate `assembly/` packet.

Portable source evidence is the public test code and these contract/worker instructions. Local
execution receipts are **executor-only**, outside git:
`/workspace/alpha-native-rule-authority-receipts/` (executor-local, not durable; absent from cloud sessions). The final `REPORT.md` and candidate identity JSON
there provide the exact patch/tree hashes and command/exit map. Preserve all numbered red receipts.
Notable checkpoints:18 actual v1 native;19 terminal;25 failed serializer;26 canonical compiled-engine
probe;33 costed native;34 existing projections;36 interruption recovery;40 capacity-masked trial
assertion;44 corrected boundary/tamper suite (24 passed). The independent arithmetic specification
was sent before outputs; its JSON file was persisted after the first failed serializer execution.
Final focused evidence:65 public selection passed612 tests with no skips;70 strengthened projection
parity/authority suite passed27. Worker typing passed6 files with actual upstream annotations;
application/test typing passed15 files plus the strengthened test; Ruff/format passed21 files;
all13 import contracts passed. Canonical Atlas freshness and local path/heading checks are recorded
in final receipts. No aggregate full gate or private suite is implied.
`executions/` contains copied scratch synthetic stores/runs/snapshots/native receipts for local
inspection. They are engineering artifacts and never imported into an owner database.

Scoped checks use the root environment read-only, candidate source PYTHONPATH, disposable
ALPHA_DATA_DIR and sanitized provider credentials. Native checks explicitly set
ALPHA_RDAGENT_SOURCE=/workspace/scratch/rdagent-484776-complete (executor-local, not durable; absent from cloud sessions). The receipt commands are the
reproduction source of truth; no heavy full gate, hidden/holdout data or provider calls are included.
Worker typing resolves actual external upstream annotations with follow-imports=silent; missing
optional upstream dependencies remain outside this narrow profile. Full root/worker locks are
preserved. Runtime profile installation is fresh-only; never modify a preserved environment.

Historical source handoff (not an instruction to reapply in the current assembly): inspect original
REPORT/candidate identities and preserved failures, materialize a separate checkout
on parent integration bc5b58351cc334d36112167c9463a80184411cc6, apply the frozen FULL e635→candidate patch (including preserved lifecycle/admission/study predecessors),
recreate source-bound profiles from current package bytes, then rerun scoped checks. The separate
b749→candidate incremental patch is only for an executor already holding that exact prior staged
tree; applying it alone to bc5 would omit required predecessors. Parent commissions
one fresh comprehensive Astra High review of that exact assembled tree, including navigation from
AGENTS. Requested reviewer model is not proof of actually served model identity. Do not reuse old
CI/full-gate/review stamps as acceptance of this candidate.

## Blockers and rollback

The source lineage remains HEAD e635e6cb5bc7b9fa688dc524998d7fe1ff8eebdc, prior staged tree
b74948d409d22742bb3aecd7358f9178f5a5a86b. No reset, rebase, commit or publication was performed.
Parent integration is separate and pending. Full report/UI acceptance, W19 query restore, W05
combined timezone/request-budget and navigation handoffs are not integrated. Four supplied transfers
had successful local prepare_materialize but current helper materialize failed `download failed`,
exit1 and no file. One attempt each; bounded retry was not used. No denial or uncertain write is
inferred. Scientific source also remains unavailable per parent-reported ZIP/text-export failures.
See executor `workflow-scope-and-handoffs.md` and `handoff-materialization-failure*.json`; do not
reconstruct patches from summaries or retry/bypass those transfers.

Current base chart_bundle does not itself clamp a manifest research cutoff or compare the resolved
snapshot hash; this fixture enforces its own exact synthetic snapshot. CLI report's lightweight
manifest reader is not independently artifact-verified. Existing backend chart/comparison consumption is
qualified here; integrated report/UI and other-owner compatibility are not. Frontend node_modules
and dist are absent, and no supported browser tool is available; rendered V1, browser, accessibility
and performance acceptance remain UNVERIFIED. Numeric chart_bundle checks are not visual acceptance. Existing run_store readers return
research_gate_watermark=None and LEGACY_CONTEXT_UNKNOWN for these projections: the top-level
synthetic watermark is not exposed as the existing report/UI research-gate badge. The public test
asserts this limitation; visible synthetic classification remains blocked on an appropriate report/UI
contract. No fake owner override or standalone launch classification is created. Chart payload parity
covers bars, equity/drawdown, trades and causal trace IDs; benchmark/exposure availability and values
are checked in canonical sidecars because chart_bundle does not return those arrays. No user-facing route
has been enabled. Real data, empirical W08 and production activation remain blocked. An authentic private hidden
engineering suite has not been supplied, so that required obligation remains BLOCKED/UNVERIFIED.
Public holdout_seed activation is not private coverage and is not copied or counted; there is no
waiver or invented substitute. Scientific D2/D3 remains prohibited.

Rollback removes/disables only the new closed version dispatch in a new reviewed patch. Preserve
all immutable contracts, owner receipts, reservations, attempts, run artifacts and failure history;
never refund/reset the trial or mutate previous environments. The older W04 conformance behavior
and original rule-request refusal without typed real authority remain available.

## Detailed native lifecycle invariants

Internal synthetic native lifecycle fixtures use the existing ControlStore/job/reservation records
and a detached CLI-owned process owner. Reconnect observes/cancels that owner; it never relaunches.
Owner loss/uncertain cleanup retains capacity and the full reservation. Process completion remains
pending scientific admission. This is Linux/POSIX process-group conformance only, with no production
dispatch, native activation, resource settlement, or generated-code containment guarantee.
Known fixture escapes retain quarantine even after the original group exits. Cleanup is shared
once across lease and owner; replay never signals a reaped group again. The native fixture safety
loop performs no journal work: it checks the monotonic deadline and a private cancel-only socket.
Journal stalls retain capacity and full charges until cleanup is published. Measured bounded
cleanup on this host establishes neither hard real-time guarantees nor owner-death containment.
Native liveness uses Linux WNOWAIT observation: the direct leader remains waitable through the
last possible group signal. Lost wait ownership or a group visible after final reap quarantines
the result without further signals. Other durable lease callers retain their existing behavior.
The detached entry establishes default SIGCHLD before effects. Internal in-process fixtures
require exclusive trusted reaping and no auto-reaping flags or concurrent disposition changes.
The safety loop also cleans an observed normal exit, so publication delay alone cannot turn it
into a timeout. Normal process completion still confers no scientific acceptance.

`workers/rdagent` is a separate development-only native LoopBase/LoopMeta conformance probe at
the foundation's pinned upstream revision. Fixed synthetic operators exercise actual stage,
feedback, signed checkpoint and same-live-owner continuation contracts. The standalone allowance
is not ControlStore accounting. No production route or ALPHA package imports this worker;
cross-owner recovery, native activation and scientific admission remain unqualified. See its
README for the isolated dependency lock, source verification, explicit public tests and limits.

The bounded W04 fixture adds one closed `native_loop` child to the existing synthetic process
owner. An actual ControlStore reservation and committed owner claim supply its stage allowance;
at least one reserved variant, positive CPU allocation and exact approved worker/lock/environment
fingerprints are required before child effects. Same-child checkpoints bind the job, reservation, invocation and
owner identity. Original W04 process-only lifecycle event fields remain unchanged; the later
closed rule result binding is described below. Exact synthetic labels/results
are checked after actual child cleanup and remain pending scientific admission / not_admitted.
All reservations stay charged; cleanup/publication uncertainty retains capacity. Study mandates
remain reference-only and the closed scientific operator registry is unchanged. This establishes
neither generic study/trial admission, complete resource metering, cross-owner recovery nor
production activation. See the W04 plan for acceptance and rollback limits.


## Current integration assembly

The original frozen e635-based candidate is preserved at tree `d67a13e88ced67e234dd0183ad7fd01ed8c53e74`.
The isolated `/workspace/Project-ALPHA-native-workflow-assembly` (executor-local, not durable; absent from cloud sessions) applies its full prerequisite delta
to integration `bc5b58351cc334d36112167c9463a80184411cc6`. Production files merged cleanly; build
history keeps both branches, and Atlas outputs are regenerated. Assembly verification and independent
review dispositions are recorded in the exact-identity packet; original receipts do not qualify this
new tree. Current assembly receipts and final identity live in `/workspace/alpha-native-rule-authority-receipts/assembly/` (executor-local, not durable; absent from cloud sessions).
Read the assembly REPORT and identity before resuming; do not apply the patch again in that checkout.
Other-owner handoffs remain unavailable and have not been reconstructed or integrated.

## Independent review corrections

The fresh assembly review reproduced two high artifact/result binding defects before correction:
self-rehashed projection semantic fields could change, and a coordinated raw-economics rewrite
could pass artifact consistency checks without touching its database. The initial summary probe
returned unchanged metadata; it did not verify D1 numerical artifacts. Original failed probes
are preserved in the assembly packet. Projection acceptance now derives the entire semantic
manifest/selectors and run identity from the trusted parent/admission/raw result. The trusted
supervisor binds the exact bounded-read receipt bytes in nested `SyntheticNativeRuleObservationV1`;
completion publishes those captured bytes and records a full `native_receipt_ref` in existing
immutable attempt details. `ControlStore.verified_research_attempt` rechecks it. The general
`research_case_summary` remains a metadata/D0-verification reader and does not revalidate D1
artifacts. This is an additive closed rule outcome
payload, not a SQL migration or new ledger. Historical process-only outcomes remain readable;
historical rule outcomes without the binding cannot complete, and old readers/writers cannot
participate in the new rule flow. Mixed-writer activation remains blocked. The issuer also detaches
and freezes the closed nested string binding: neither a caller alias nor the issued view can change
it. Journal serialization makes a separate plain copy; it does not expose mutable owner evidence.

Public test portability now uses explicit source/profile configuration; configured-but-broken
runtimes fail, while absent opt-in is disclosed as skipped. Permanent synthetic receipt copies
require an explicit destination. Test cleanup uses retained authority, including validated Linux
pidfds for deliberately orphaned fixtures, and never signals a reaped saved group. These corrections
have focused red/green evidence; the assembly packet records the final regression and independent
review disposition for its exact tree, without transferring earlier stamps.
No generic UI/report semantic validation, hidden-suite qualification, scientific result or live
activation is implied.


## Recovered assembly verification and next work

The source-tested tree `d9fc9658686eb3247f284d7a0a65943dc88e6c11` passed 616 explicitly selected
public tests with no skips, plus 47 integration-preflight tests and two subtests. Strict typing
covered 27 root/test files and nine worker files; Ruff lint/format covered all 36 changed Python
files. All 13 import contracts, canonical cheap preflight, plan validation and source-bound worker
profile revalidation passed. Receipts `54`–`63` in the assembly directory preserve commands, exits
and timing. A usage interruption occurred after these completed; no uncertain process was rerun.
The exact final packet distinguishes this source-tested tree from the subsequent documentation-only
status refresh and its fresh Atlas/preflight checks. No full-gate stamp exists for this assembly.

The next substantial package is integration of the available native workflow with the actual
query/restore/scientific/report handoffs and verified existing-UI presentation. Source materialization
and ownership handoff must precede edits to those owners' files. The assembly report records exact
Library failures and W05's divergent-base dependency. Do not reconstruct patches. Then verify
immutable parent/baseline/control identity through query/reopen/restore and artifact-backed UI
watermarks, price/trades, equity/benchmark, drawdown, exposure and linked evidence. Preserve unknown
states and separate engineering conformance from an accepted discovery investigation. Real discovery
still needs the owner's frozen study and qualified actual data identity; no acquisition is authorized.
Full/private-suite qualification, mixed-writer deployment, physical isolation and cross-owner
crash-resume remain separate blockers. Qlib tabular adapters remain with their separate owner.

### Final review: exact synthetic snapshot lineage

A further independent probe showed that consistent snapshot/projection rehashing could relabel
the fixed snapshot's source/date without changing the captured receipt or database. The closed
projection boundary now derives its expected complete snapshot through the existing canonical
ParquetStore/create_snapshot path in a disposable directory and requires the exact verified
manifest digest. This binds metadata, provenance, bar bytes and declared symbols/actions; it
never repairs an altered existing snapshot. Fourteen discriminating lineage fixtures and the
actual verified-attempt attack/restore case are retained in the public authority tests.
Same pinned encoder/runtime identity is part of this engineering fixture; changing serialization
requires explicit requalification, not silent rewriting of old evidence. Final post-repair checks
and independent disposition supersede the earlier d9fc source run only where explicitly recorded
in the assembly packet. No generic snapshot-reader, database-schema or production-route change.

### Native source platform boundary

The portability follow-through isolates Linux retained-child observation behind an explicit host
guard. Native imports tolerate Windows' absent `fcntl`; execution, workspace allocation and the
owner entrypoint reject unsupported hosts before effects. Missing or malformed observation
capabilities also deny startup. The generic POSIX lease path and retained-leader cleanup order
remain unchanged; this adds no alternate supervisor.

Verification proceeds through the reproduced Darwin type errors, focused unsupported-host and
Linux lifecycle/adversarial/journal/lease checks, then fresh generated Atlas outputs. Darwin
static typing and a Linux-hosted missing-`fcntl` import simulation do not qualify native execution
on macOS or Windows. Existing Windows POSIX typing failures remain outside this narrow repair.
Independent review and a full gate on the final frozen tree remain separate acceptance steps.

Public tests declare the Linux requirement at actual owner fixture setup. Portable forged-owner,
unsupported-host, trial-exposure and study-contract rejection tests keep generic disposable stores
and explicit no-native-event/no-payload assertions. Generic POSIX leases and isolated LoopBase
conformance retain their existing scope. Failed-start escape cleanup always waits for its retained
process even when no barrier directory was created. These checks do not establish macOS aggregate
coverage or explain unexposed worker failures; the unchanged coverage floor still applies.

## Cloud qualification stabilization, 2026-10-27

Linux cloud session on content derived from candidate tree `077475067b9ead82eba4c4f7333ada06816cb1f6`
(base `bc5b58351cc334d36112167c9463a80184411cc6`). Engineering evidence only; no acceptance is claimed.

**Pinned source route.** The canonical archive URL returned HTTP 403 (session repository-attachment
policy). With owner approval, commit `484776c211e4fbbeef03e0ec00d6bbee7362a4f4` was fetched by anonymous
git read (`git fetch --depth 1 origin <sha>`; no LFS, credentials or push) into a pristine checkout.
`source_pin.verify_source` accepted its 694 `rdagent/` files at `0266b2d6…8707`. Archive bytes and
`ARCHIVE_SHA256` were **not verified**; no archive or full-repository identity is claimed.
The upstream root contains a top-level `test/` package, which `fixture_entry._reject_source_root_shadows`
correctly rejects as a stdlib shadow (it is the only rejected entry). Native tests therefore use a
derived root holding byte-identical `rdagent/` plus `LICENSE` and `pyproject.toml` (696 files equal to
the pinned git blobs; digest re-verified; no bytecode or symlinks). `test/` is upstream unit tests and
is not imported by `rdagent/` or the probe allowlist. No guard or source was changed.

**Profiles.** Built with the README commands (uv 0.11.32): `uv sync --locked --project workers/rdagent`,
then the two fresh-only `uv venv` / `uv pip install --require-hashes --no-deps` / `install_rule_profile.py`
pairs. Lock SHA-256: worker `uv.lock` `ed5adbce…63a5a`, `rule-requirements.lock` `ee43c576…29fcc`,
`economics-requirements.lock` `57ce3fda…0b32be`, root `uv.lock` `f88c1b2f…4bcd` (unchanged).
`.gitignore` covers only `.venv/`, so the clone-local `.git/info/exclude` lists
`/workers/rdagent/.venv-rule-qualified/` and `/workers/rdagent/.venv-economics-qualified/`. These keep
generated environments out of the gate tree hash, ruff and semgrep; they are not test or coverage
exclusions. With `ALPHA_RDAGENT_SOURCE` set to the derived root, the native suites passed 111/111
(previously skipped publicly).

**Repairs in this stabilization.** The owner child and the payload/native worker now receive only
`TMPDIR` equal to the validated workspace parent (no other inherited environment), so
`_fixture_root` and the admitted worker's workspace check agree under a non-default temp root
(regressions: `test_owner_child_inherits_the_workspace_temp_directory`,
`test_real_native_worker_runs_under_a_non_default_temp_root`; fail-closed cases:
`test_owner_refuses_a_workspace_outside_or_aliasing_its_temp_root`,
`test_admitted_worker_rejects_a_workspace_outside_its_temp_root`). The worker README now describes
the pristine-plus-derived source setup and the pin semantics. Probe results replace the constant
`upstream_commit`/`archive_sha256` fields with `source_pin` (`expected`, `verified`, `not_verified`) so
an unobserved archive checksum is never presented as measured. The suspended-owner test now freezes
the owner only at a verified stopped, lock-free point; a separate regression pins the lock-held case as
fail-closed with no takeover and a normal owner close after resume.

**Open findings (not blockers).** AF_UNIX: the owner control socket lives under the workspace
(`/alpha-native-fixture-XXXXXXXX/control/native-<job uuid>.stop`, 87 bytes after `TMPDIR`), so a
`TMPDIR` longer than about 21 bytes exceeds the 108-byte socket path and fails closed before claim. `_cleanup_once` uses a fixed 0.2 s
post-SIGKILL window; under oversubscription cleanup can be unverified (fail-closed quarantine), a
plausible but unconfirmed cause of earlier load-only `test_lease_and_owner_share_one_cleanup_across_failure_paths`
failures. `test_native_fixture_lifecycle._until_started` has a fixed 6 s budget for two cold
interpreter starts (~1.7–1.9 s each idle). The lease thread can classify an exit observed in the same
tick as a deadline as `timeout`; `_terminate_retaining_leader` always waits the full grace;
heartbeats append a journal row every 50 ms while holding the writer lock; `baseline/control.json`
are read unbounded after a separate symlink check; uncertain or foreign-epoch jobs have no protected
exit; `publish_rule_run` writes files inside the open SQLite transaction. Worker: `verify_source`
relies on the caller's `sys.pycache_prefix`; the audit hook omits `os.exec*`/`posix_spawn`/`fork`;
the economics and positions profiles pin different `pytz`/`tqdm` versions.

## Cloud foundation successor: native and lease runtime findings, 2026-10-28

Unpublished successor; not full-gated or formally reviewed yet. Gate run 7 on content tree
`f4f955d4` failed backend pytest ("2 failed, 6654 passed, 10 skipped, 2 subtests passed";
coverage 93.18%). That tree is kept as the failed checkpoint.

**Costed native owner budget.** `test_one_actual_native_rule_execution[True]` closed with
`reason=timeout`, `returncode=-15`, `elapsed_seconds` about 20.2, and failed reproducibly.

The owner's deadline starts at `_Owner.__init__` and covers launch preparation. Inside it,
the costed path ran three full re-hashes of the 1.06 GB economics `site-packages` before spawn,
about 4s each:
- two inside one `claim`: line 278 via `implementation_fingerprints`, and line 320 for
  `rule_profile`;
- one at the pre-spawn `command()` check.

The worker (about 7.6–8.3s) then exited at about +20.2–20.5s. Post-exit verification is not
deadline-gated.

The 20s value is chosen by the tests; no production caller exists and the product bound is
`<= 60`. The repair makes `claim` admit `rule_profile` as exactly the `environment` value it
has just verified against the approved fingerprint, instead of re-hashing:
- one measurement per claim;
- every pre-clock, pre-spawn, worker and completion check unchanged;
- no cache, and no change to the deadline or thresholds.

It also closes a binding gap: previously a self-consistent venv swap between the two claim
measurements could admit an unapproved profile identity.

Behaviour change: a runtime change after the claim now fails at `command()` as
`owner_error`/`no_payload_spawn_attempted` with the claim committed, rather than inside the claim.

Regressions:
- the claim admits the approved value with one measurement; red against the old code;
- three changes-after-claim fail closed before trusted completion.

Bounded real runs at `seconds=20` all completed with `exit`/`pending_scientific_admission`:
5 clean (`elapsed_seconds` 20.73–22.95) and 3 under owned hashing load (21.18–21.92). The
worker-exit margin is only about 1–3s.

**Lease silent-child test.** The fixed 0.25s child lifetime made `heartbeats >= 2` depend on
renewal latency. A single renewal stall of about 0.25s reproduces "1 >= 2". The test now holds
a silent child until release, re-reads the final heartbeat before the post-stop reconcile, and
cleans up only its owned child. A lease that never renews still fails (0 >= 2).

**Runtime contract: orphan reaping.** In this container PID 1 (`/process_api
--firecracker-init`) reaps orphaned zombies about 1.93s after a group SIGKILL (20 of 20).
`terminate_and_reap` and lease cancellation verify group exit within 0.2s, so tests with
orphaned descendants pass only under the gate's Linux pytest owner. `scripts/run_owned_test.py`
is a `PR_SET_CHILD_SUBREAPER`; under it 2 tests passed 3 of 3, and as plain `pytest` they
failed 3 of 3. Run Linux pytest through the gate or that owner. Plain pytest results for these
tests are not evidence.

**Open (pre-existing, not fixed):**
- the `rule-profile.json` double-read race (`_native_rule_environment.py:45`/`:85`;
  `rule_probe.py:17`/`:28`);
- venv `.pth`/site code runs before the worker's checks under `-I`;
- the claim holds its write transaction while hashing;
- completion's duplicate measurement;
- `cpu_milliseconds` not enforced.

**Costed success-fixture budget and cleanup (same successor).** Even after the claim repair, the
test's literal `seconds=20` and outer `process.wait(timeout=30)` lacked headroom under the
canonical gate wrapper at `-n 4`. One run failed at the outer 30s wait, and the leaked owner `Popen`
then raised `ResourceWarning` inside an unrelated test in the same worker.

The test now uses `NATIVE_SUCCESS_FIXTURE_SECONDS = 45`, within the product's `0 < seconds <= 60`
contract and the pilot's 300s wall budget, and an outer wait of that plus 45s. On an outer-wait
failure it sends the datagram stop request to only its owned owner, waits 15s, then terminates or
kills that `Popen`. It never signals numeric pids or groups. If no outcome was recorded, it attaches
a "payload group may remain" note naming the recorded leader pid, and the original failure is
re-raised.

Production deadline start and semantics are unchanged. Deadline and fail-closed behaviour stay
pinned by tests that set their own deadlines. The lost timing canary for the duplicate hash is
covered deterministically by the claim regressions.

Canonical wrapper `-n 4`, 4 runs (2 focused sets, 2 native-module runs): all passed. Costed owner
`elapsed_seconds` 20.62–22.37 (`exit`), including the roughly 4s post-exit verification;
positions 6.94–7.70.

## Foundation stage contract and handoff (ICM-aligned, ALPHA adaptation)

**Source and labels.** The structure follows the Interpretable Context Methodology: arXiv
[2603.16021v2](https://arxiv.org/pdf/2603.16021v2) by Jake Van Clief and David McDermott, and the
companion repository [RinDig/Interpretable-Context-Methodology](https://github.com/RinDig/Interpretable-Context-Methodology)
at `02ba5d85c7871b75c7c702a2d8da6524723d53d4`. The scope notes are as summarized by the owner and
were not re-derived here:
- **Paper:** sequential stages with human review; no performance benchmark; staleness propagation
  left as future work.
- **ALPHA adaptation (labelled):** automated independent review, and stale-input rejection at
  consumption.
- **Not adopted:** the companion convention that a non-empty output directory means complete. Here
  completion binds artifact identity, checks and review state.

Each fact has one home:
- routing: `CLAUDE.md` and this plan's front matter;
- stage contract: this section;
- constraints: `.claude/rules/` and ADRs;
- artifacts: `.alpha/state/` receipts and checkpoints.

**Stage: cloud foundation successor.**
- **Inputs:**
  - this plan: front "Current active work", "Cloud foundation successor: native and lease runtime
    findings, 2026-10-28", and this section;
  - [build record](../../BUILD-STATUS.md) "2026-10-28 Native costed claim and lease fixture repairs";
  - [gate preflight plan](2026-10-26-gate-preflight-selection.md#review-scope-alignment-2026-10-27);
  - [harness](../../operations/claude-code-harness.md);
  - README "Linux cloud development setup" and `workers/rdagent/README.md` "Reproduce";
  - `scripts/gate.py`, `scripts/gate_components.py`, `scripts/git_guard.py`, `scripts/cloud_setup.sh`.
- **Outputs:**
  - the candidate worktree;
  - `.alpha/state/gate-stamp.json` plus six `component-*.json` receipts;
  - `.alpha/state/review-verdict.json`;
  - pre-run checkpoints `.alpha/state/gate-checkpoints/pre-run-<manifest hash>/`;
  - dated checkpoints `.alpha/state/portable-evidence/<name>/`.
- **Evidence identity:**
  - `compute_tree_hash`;
  - the stamp's `comparison` binding (reference, resolved base, merge base, selection mode);
  - each receipt's `definition_hash`;
  - the review's `reviewed_tree_hash` and `bound_review_diff_hash`;
  - each checkpoint's `MANIFEST.tsv` (path, bytes, SHA-256).
- **Status values**, each read from an existing mechanism:
  - **passed:** `uv run python scripts/gate.py check --tier full` exits 0 (`full_stamp_usable`). This
    covers public checks only.
  - **failed:** a receipt has `status: failed`, or the gate exits non-zero.
  - **blocked:** a required input or verdict is absent or BLOCK, such as the holdout suite or a
    BLOCK review.
  - **stale:** `check` reports a tree, base, definition or review-scope mismatch.
  - **Stage complete:** requires passed, plus an APPROVE review bound to the same tree, plus an owner
    decision.

**Resume and stale-input rejection.** On re-entry:
1. Run `gate.py orient` and `gate.py check --tier full`.
2. Compare the current `compute_tree_hash` with the checkpoint's recorded tree.

A match with a usable stamp resumes. Anything else is stale and is rerun, never inherited.
`git_guard` rejects stale or unbound evidence at commit. Every `run_full`, `run_component` and
`run_gate` entry first copies the allowlisted stamp, receipts, review/quant attestations and
coverage files into a hash-named, verified, mode-read-only checkpoint. If that copy cannot be
verified, the run stops before any overwrite. These checkpoints are not immutable against the
root user. `gate.py attest` overwrites review/quant attestations without this preservation. A failed
attempt keeps its `.incomplete-*` staging copy in `gate-checkpoints/`; these copies and the
checkpoints are retained without a retention bound and are not cleaned up. Staleness is not
propagated between stages automatically.

**Storage classes.**
- **Durable:** git-tracked files on a pushed branch.
- **Ignored local:** clone-only, lost when the container is reclaimed:
  - `.alpha/state/**` (receipts, checkpoints, `runtime/fontconfig/`);
  - `workers/rdagent/.venv-*-qualified/`;
  - the derived RD-Agent root.
- **Transient:** `/tmp`, session scratch, and the `/workspace/...` executor paths above, which are
  executor-local and not durable.
- **Reproduction:** `ALPHA_CLOUD_FOUNDATION=1 bash scripts/cloud_setup.sh` (README). It validates
  every environment against its recorded rule profile with `measure_rule_environment` (owner approval binds later, at claim) and never rebuilds a validated one.
  An interrupted build is detected by its `.incomplete` marker and kept; README "Linux cloud
  development setup" gives the explicit retirement step.

**Checkpoints (distinct; no self-hash).**
- **Gate8 (dated):** `.alpha/state/portable-evidence/cloud-foundation-fd960490-gate8-20261028/`,
  `MANIFEST.tsv` SHA-256 `d48814f9213fc1f33c911ab329d6b5c06e672adbd9491dbe5f3013a51886c84d`.
  - Content tree `fd960490c663a451699ee4918fd329b2c728ca22`, `compute_tree_hash`
    `e2188ecb9669feed6881894a19f8068280f04002eb538bbaf5b64d2e56152cd8`, against
    `origin/main` = merge base `99f2d472`.
  - Public full gate passed (six components, one stable tree).
  - Independent review: BLOCK (holdout absent). Not accepted. Its `reviewed_diff_hash`
    `e3b0c442…b855` is correct: that field is the risk-tier scoped diff hash, and no risk-tier path
    changed. The verdict records were never attested; an author transcription of the later batch
    verdict was abridged and is superseded by the verbatim hand-back.
- **New batch:** this section, the opt-in bootstrap and pre-run preservation are a later,
  **unqualified** tree. Its identity is recorded with its own gate and review, not here.

**Ownership.**
- `/home/user/project-alpha` (branch `claude/cloud-foundation-successor-f4f955d4`, unpushed) is
  authoritative for the successor.
- The original checkout holds the failed gate7 checkpoint (`f4f955d4`) and the c95 evidence.

Cleanup and refactor are not complete (backlog items 1 and 4).

**Ordered foundation backlog.**
1. **Workspace and file ownership.** Stated above. Moving or retiring duplicate checkouts and old
   evidence is an owner decision; nothing is deleted.
2. **Scoped context, handoff and evidence separation.** This section. Missing: one fresh-context
   navigator retrieval recorded as acceptance.
3. **Enforceable Software Team controls.** Implemented:
   - stamp and review binding;
   - consumption checks;
   - pre-run preservation.

   Missing: the holdout suite, an owner decision, and an early clear failure when descendant tests
   run outside `scripts/run_owned_test.py`.
4. **Targeted bloat/refactor.** Only the reviewer's low `changed_paths` wrapper is in scope. Broad
   bloat remains an explicit open item.
5. **Reproducible cloud bootstrap.** Opt-in `cloud_setup.sh` steps, with idempotent re-entry
   demonstrated; build, validation, dirty-source and interrupted-build paths are covered by stubbed
   tests. Missing:
   - a fresh-container run that creates the venvs;
   - acquiring the pinned source without an existing pristine checkout (no alternate fetch route
     is provided).

## Gate10/gate11 repairs and retained diagnostics, 2026-10-28

**Gate10 (c88 candidate `15fa86f9`).** It failed the lifecycle start precondition
(`test_controller_death_preserves_same_owner_for_cancel`, "synthetic payload did not start"). Its
owner log was not retained, so **the gate10 cause stays undetermined**.
- A single retry, gate11, failed three browser cases.
- Neither run produced a stamp.
- The independent review withdrew its APPROVE. The attestation was retired unchanged into ignored
  evidence.

**Successor repairs.** Each has a discriminating regression and the same independent reviewer.

- **Lazy CLI group dispatch** (`alpha_cli/main.py`). One registry feeds the full `app` and the
  console entry, which loads only the invoked group.
  - `alpha data symbols --json`: idle cost went from 4.19 s / 4.70 CPU-s to 1.22 s / 1.47 CPU-s,
    with identical output.
  - The three gate11 browser cases now pass singly.
  - A 15 s picker wait inside a passing assertion remains unexplained and is disclosed.
- **Deferred native-loop imports on the synthetic start path.**
  - The first fix made `NativeLaunch` lazy in `native_supervisor.py` (supervisor import: 2.39 s to
    0.65 s). Its regression covered only that import, so **it missed the real heavy edge**.
  - `_native_fixture_store` imported `CostedRuleStudy` at module level. That reached
    `alpha_research` and `scipy` on every status read and claim, including inside the owner's 5 s
    preparation deadline.
  - That import now sits in the rule-only claim branch. A status- and claim-path regression was red
    before this change and green after.
  - Status path in a fresh interpreter: 0.49 s. The removed edge costs 1.44 s.
- **Lifecycle readiness.** The fixed 6 s `_until_started` bound was an incidental fixture bound, not
  a start-up contract; the only time contract is the owner `seconds` deadline, which is unchanged.
  It was replaced with event-based readiness:
  - ready means the payload marker AND the claim;
  - named prompt failures, in check order: terminal or quarantined, then launcher exit, then owner
    gone before claim (a non-blocking lock probe, released at once);
  - a 60 s hang guard, which is not a requirement;
  - an opt-in, conservative birth-based owner-deadline check for the three callers whose post-ready
    checks need a live owner;
  - cheap polling, with a store read only every 0.5 s or once the marker exists.

  Real-process negatives cover:
  - terminal no-start;
  - launcher exit;
  - owner death before claim, through a real AF_UNIX path-length bind failure;
  - a slow pre-owner launcher.

  Quarantine before readiness has no dedicated test.
- **Diagnostic-only failure retention** in the controller-death test. It records status, the owner
  log and file times, and capture never masks the original assertion.

**Cold-start reproduction (pre-claim-import fix, retained evidence).** The gate10 failure recurred on a
freshly started container.
- The owner was alive with an empty log and claimed only after the 6 s window.
- It then honoured the stop: `cancelled`, `no_payload_spawn_attempted`, 2.50 s of 5 s used.
- Phases:
  - controller import: 1.06 s;
  - controller status read: 2.26 s;
  - owner start to control socket: 1.11 s;
  - claim: more than 1.6 s.
- The independent review attributes this largely to the claim-path import, now removed. The
  historical gate10 cause stays unproven.

**TMPDIR regression budget.**
- `test_owner_child_inherits_the_workspace_temp_directory` is the TMPDIR-inheritance regression
  above. It has no start-up bound. It used the 2 s default of `start_synthetic_owner` with the
  `success` fixture, and at `-n 4` it timed out four times (receipts sealed in
  `lifecycle-readiness-claim-import-20261028`):
  - once during launch preparation, with no payload spawned, at 2.2417 s;
  - three times after the payload spawned, killed with returncode -15 at 2.218–2.245 s.
- With independent-review endorsement, it now passes `seconds=5`. That is the existing fixture
  convention for a normal outcome after cold starts.
- Unchanged:
  - the default of 2.0;
  - production enforcement;
  - its two sibling 2 s tests;
  - every strict expiry test (`seconds=0.001`, the insufficient-deadline test, and the adversarial
    preparation-expiry cases).

**Open findings.**
- The asymmetry is not established. The siblings with the same 2 s budget were not observed
  failing. With n = 4, chance cannot be separated from a TMPDIR-specific cost.
- Cold-I/O margin after the claim-import fix has not been independently measured.
  - The controller-death test records `start_ready_seconds` and
    `start_deadline_remaining_lower_bound` on every run.
  - Qualification reports the minimum and the sample count from the owned compatibility run and the
    final full gate.
  - A lower bound below 1.0 s blocks.

**Status before gate12.** Targeted failures and helper checks pass: 16. One finite native
compatibility confirmation: 254 passed, 0 skipped.

**Gate12 (approved candidate `2a67bad6`, failed, not published).** One full gate failed in backend
pytest: 4 failed, 1 error, 6703 passed, all on one xdist worker. The independent review found no
evidence of a production regression; the owner's in-deadline path only lost work. Its
classification:
- Three sibling tests ran 2 s `success`/`failure` owners that ended in `timeout`:
  - normal-exit and cancel-pending hit preparation expiry (`no_payload_spawn_attempted`, 2.22 s and
    2.10 s);
  - `failure-2` recorded `timeout` instead of `exit`; its elapsed time and phase were not logged.
- The earlier "only the TMPDIR test" asymmetry therefore did not hold. Two seconds was a success
  precondition in each, not a start-up requirement.
- The delayed-start test asserted `>= 1.0` on the conservative birth-based bound, which also
  counts pre-deadline start-up. It read 0.939.
- The controller-death test errored at setup on a `ResourceWarning` for an unwaited owner `Popen`.
  This is consistent with cancel-pending, which had no `finally`, but not proven: the creating
  test and the worker identity were not logged. The leak did not cause the three timeouts, which
  are separate fail-closed outcomes.

**Test-only repairs after gate12.**
- The three success-precondition tests pass `seconds=5`, the existing cold-start convention, with
  the same not-a-requirement comment.
- Cancel-pending reaps its owner in `finally`. A regression injects a readiness failure after the
  owner binds its stop endpoint and requires the owner to be waited. It is red on the old test and
  green on the new one.
- The delayed-start test asserts readiness after more than 7 s, which suffices because spawn
  refuses dispatch once the owner deadline has passed. It records the bound without asserting on
  it.
- Unchanged: the default of 2.0, `("wait", 0.3)`, every strict expiry, no-start, crash and
  quarantine test, production, and the controller-death `>= 1.0 s` readiness precondition.
- Cleanup on every failure path. Cancel-pending requests owner cleanup on every failure path.
  Its owner `Popen` is waited whenever the stop request is delivered or the owner has already
  exited.
- Undeliverable stop. If stop delivery stays uncertain for 3 s, the shared `_stop_test_owner` waits
  only on that exact owned `Popen`, with no signal and no takeover. The bound is the claimed fixture
  `seconds` (finite, 0–60 s under the synthetic contract, otherwise 10) plus the existing 8 s
  cleanup allowance.
- Still live after the bound. A still-live owner then fails loudly with "live owner stop is
  uncertain" and is never reported cleaned. Its `Popen` may remain unwaited, and a later GC
  `ResourceWarning` can error an unrelated test. This applies equally to the pre-existing siblings.
- Tests for the bounded wait. Deterministic tests cover an undeliverable stop that is reaped after
  the owner's own deadline (red against the earlier helper) and a still-live owner that fails
  loudly without a signal.
- Checks: the focused cleanup and expiry negative set passed 25/25. One native compatibility set
  passed 425/425 with 0 skipped, before the bounded wait. Afterwards the two bounded-wait tests and
  the original cleanup regression passed 3/3.

**Gate13 (owner-approved `11b8540e`, failed, not published).**
- Results: backend, frontend, literature and qlib passed. The controller-death startup-margin receipt
  was unique: ready 1.485 s, lower bound 3.770 s. Atlas `tests` failed 1/102:
  `test_groups_call_their_cmds_module`.
- Cause: a genuine regression from the lazy CLI dispatch. The atlas `cli_tree` extractor read
  group→module edges only from static `from alpha_cli.X import …` plus `add_typer(alias, name=…)`,
  and `main.py` now registers groups through the `GROUPS` literal.
- Effect on the generated graph: it had lost all 24 CLI→module `calls` edges. The earlier Atlas
  "fresh" result compared against that already degraded output.
- A second silent case: the CLI-awareness drift test's `add_typer` regex matched 0 names (24 at the
  base), so it passed vacuously.

**Atlas repair.**
- The extractor also reads the `GROUPS` literal, with line provenance. It raises on any GROUPS shape
  it cannot read, so it can no longer yield zero edges silently.
- Two new atlas tests check the exact 24 registry pairs and the malformed-registry failure. Both
  were red before the fix.
- The drift test reads `alpha_cli.main.GROUPS` and requires all 24 names.
- Regenerated graph: the 24 `calls` pairs are identical to the base.
- `depends_on` disclosure. The 26 `main → *_cmds` edges are absent, because those imports are now
  runtime registry imports, not static ones; they appear only as registry data and the restored
  `calls` edges. The `_native_fixture_store → _native_rule_environment` edge is absent, because the
  reviewed claim repair removed that import. Import-linter contracts are unaffected (intra-package).
- Checks: atlas suite 104/104; drift, docs and lazy-CLI tests 54/54.

**Status.** No full gate on the repaired tree. Review is BLOCK: the private holdout suite is absent,
and the approved exception covers only `2f9d0c3d`, not this tree.
