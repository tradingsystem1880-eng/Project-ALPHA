# Bounded W04 native admission integration

Status: bounded implementation and explicit public validation complete; independent review pending.

```json
{
  "schema_version": 1,
  "title": "Bounded W04 native admission integration",
  "context": "Connect one fixed synthetic LoopBase child to the existing D1 reservation and process owner; preserve scientific authority.",
  "assumptions": [
    {"statement": "ExplorationMandateV1 is a reference projection with no launch authority.", "verified_by": "alpha_study/authority.py and alpha-study rules"},
    {"statement": "The existing exact trusted process owner must own the actual native child.", "verified_by": "ControlStore claim checks and retained-child lifecycle tests"}
  ],
  "alternatives_considered": ["Reject a dummy supervised child, a second ledger, generic command dispatch and additions to existing closed event fields."],
  "pre_mortem": ["Upstream post-effect step_n could become an accidental budget.", "Result JSON could be mistaken for cleanup or scientific evidence.", "An uncommitted claim could permit effects."],
  "slices": [
    {"title": "Measured launch and committed admission", "verify": "Explicit test_native_w04_admission.py admission tests", "expected": "Only approved measured fingerprints and an actual reserved variant produce a live allowance.", "rollback": "Reject this descendant; preserve the source candidate.", "status": "done"},
    {"title": "Actual child and bound continuation", "verify": "Explicit W04 and native loop conformance tests", "expected": "Native checkpoints bind the reservation/spec/owner, with exact feedback and same-owner replay guards.", "rollback": "Disable the closed native_loop fixture; never respawn or refund an existing claim.", "status": "done"},
    {"title": "Failure reconciliation and evidence", "verify": "Explicit public lifecycle/control/execution/lease/foundation regressions and scoped lint/type/import checks", "expected": "Failure/cancel reconcile once; uncertainty retains full charge and capacity.", "rollback": "Retain quarantined records for inspection; do not edit stored claims.", "status": "done"}
  ],
  "tier_impact": ["none"],
  "docs_to_update": ["CLAUDE.md", "docs/BUILD-STATUS.md", "workers/rdagent/README.md"],
  "out_of_scope": ["Production activation", "Scientific artifact admission", "Full budget usage metering", "Cross-owner checkpoint recovery", "Full gates and commits"],
  "files": ["apps/alpha-cli/src/alpha_cli/_native_loop_admission.py", "apps/alpha-cli/src/alpha_cli/native_supervisor.py", "apps/alpha-cli/src/alpha_cli/_native_fixture_store.py", "workers/rdagent", "tests/unit/test_native_w04_admission.py"]
}
```

The candidate descends from staged tree `7559fe34742c3ce4511a7498c6590a2913f71067` at
HEAD `e635e6cb5bc7b9fa688dc524998d7fe1ff8eebdc`. The two source checkouts remain untouched.
No dependency/schema/security-policy changes, real datasets, scientific run, full gate,
commit or publication are authorized. This changes no package DAG or numerical estimator.

## Acceptance map

| W04 concern | Bounded implementation | Limit / W08 work |
|---|---|---|
| Existing admission | Active approved D1 contract, running bound job, atomic full-envelope reservation and exact live owner claim | No new study/trial authority. `ExplorationMandateV1` remains `launch_authority: none` / `verification: not_checked`. |
| Fixed operator | Actual pinned LoopBase/LoopMeta and fixed synthetic Experiment under the retained child PID | The closed study operator registry contains `double_bottom.v1`; this probe does not register or qualify a new scientific operator. |
| Identity | Measured worker, pinned upstream source, isolated lock, interpreter/config and evaluator fingerprints match approved invocation | Identity measurements are not installation qualification, source immutability guarantees or scientific acceptance. |
| Exposure/budget | One reserved variant and positive reserved CPU required before claim; each stage checks reserved loop_steps before effect; native step_n remains a post-effect stop | Full reservation remains charged. Positive CPU reservation is not measured enforcement of its ceiling. No actual token/CPU settlement, refund or generic per-resource enforcement. Fixed operators perform no model/tool calls. |
| Continuation | Signed native checkpoint includes the admission digest; live owner checks path/digest/binding and serializes continuation | Same child only. No durable checkpoint recovery or replay across owners. Checkpoint JSON/pickle carries identity, never ControlStore objects or launch authority. |
| Feedback | Exact four labels and metric names/values/units; parent verifies child artifact after actual group cleanup | Every zero-exit result stays pending_scientific_admission / not_admitted. No completed scientific attempt or immutable scientific run is synthesized. |
| Failure/cancel | Existing lease owns the actual native child; verified failure/cancel links one failed attempt and releases capacity | Reservation remains fully charged; no production recovery claim. |
| Uncertainty | Cleanup, result publication and journal publication defects retain running capacity and full charge/quarantine | Owner death, hostile-code containment, unknown descendants and durable reconciliation remain unqualified. |
| Compatibility | New explicit `native_loop` fixture value; existing lifecycle event fields/schemas unchanged | Historical readers see process-only state. Artifact validation is not a new persisted event contract. |

Rollback means reject the descendant or remove the new fixed launch route before creating new
claims. Existing claims must remain readable and charged; rollback must not delete them, mutate
checkpoints, relaunch a finished/unknown child or fabricate a refund. A clean failed claim and its
attempt/link/status closure are transactional. Result artifact corruption never authorizes
capacity release. Synthetic scratch stores are disposable after the owning test has reaped its
children; no real control store participates.

## Validation evidence

The final explicit public selection passed **400 tests**: native journal independence,
adversarial lifecycle, lifecycle, ControlStore research, durable lease, research execution,
foundation contract, standalone real native loop, and W04 admission. This is a focused public
selection, not the full repository gate. Scoped Ruff and strict mypy checks passed; import-linter
kept all 13 contracts. The FeaturePlan block validates against the repository model.

Four narrow removed-guard mutants failed their intended tests: reserved variant, approved
implementation fingerprints, pre-effect stage allowance and checkpoint admission binding.
Separate red/green tests caught a caller-defined launch object on a legacy fixture and zero CPU
allocation. Earlier fixture-construction and callback compatibility failures remain in receipts.
One full rerun exposed a real test teardown race after controller death; the fixture now waits
for the detached owner's retained lock to close before deleting its scratch workspace. No
production lifecycle behavior was changed to hide that race.

Receipts are retained under `/workspace/alpha-native-w04-admission-receipts`, including exact
commands/exit statuses, module origins, child results/progress, red failures and canonical
candidate evidence. The existing root and worker runtimes are reused through local untracked
`.venv` symlinks; no packages were installed and no lockfiles changed.
