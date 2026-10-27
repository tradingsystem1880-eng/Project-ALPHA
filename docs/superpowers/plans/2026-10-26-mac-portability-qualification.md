# Combined Mac portability qualification

**Delivery state:** Preserved 24f checkpoint reviewed with 48/49 checks passing; aggregate coverage failed. An isolated portable-evidence successor is in progress. No integration or acceptance.

**Full scope:** owned by the [canonical feature readiness checklist](../../context/feature-readiness-checklist-2026-10-27.md); this plan covers only Mac portability qualification and marks no checklist feature done.

```json
{
  "schema_version": 1,
  "title": "Combined Mac portability qualification",
  "context": "Reconcile verified native repair into frozen Qlib/W11/PR92/W05 b0b9c8ea and qualify actual Mac without lowering coverage or enabling native execution.",
  "assumptions": [
    {
      "statement": "All consumer native production/test files match exact f15 source base.",
      "verified_by": ".alpha/state/mac-portability/source-readiness.json"
    }
  ],
  "alternatives_considered": [
    "Treat Linux gate as Mac acceptance: rejected.",
    "Skip all native tests or lower coverage: prohibited."
  ],
  "pre_mortem": [
    "Kernel-dependent tests hide portable authority failures.",
    "Startup exceptions are masked by cleanup.",
    "Copied runtime resolves predecessor sources."
  ],
  "slices": [
    {
      "title": "Verify source and reconcile isolated successor",
      "verify": "Archive/member/base/target hashes plus independent source review",
      "expected": "Qlib/W11/PR92/W05 preserved; native Linux-only protections unchanged",
      "rollback": "Keep source checkpoint; no real-store rollback",
      "status": "done"
    },
    {
      "title": "Investigate original failures and run actual Mac gates",
      "verify": "Targeted public error diagnosis and canonical full gate",
      "expected": "Actual failures classified/fixed with unchanged floor/denominator",
      "rollback": "Retain failed receipts and isolated source",
      "status": "done"
    },
    {
      "title": "Independent exact-tree adversarial review and evidence",
      "verify": "Source/test/receipt review and fresh-reader links",
      "expected": "Honest tested/blocked/accepted distinctions",
      "rollback": "Keep candidate uncommitted and unpublished",
      "status": "done"
    },
    {
      "title": "Quantify portable coverage gaps and freeze successor protocol",
      "verify": "Frozen public module/function audit and synthetic protocol",
      "expected": "Statement gap separated from unmeasured branches and Linux provenance",
      "rollback": "Preserve24f checkpoint and all 49 stage receipts",
      "status": "done"
    },
    {
      "title": "Portable charged-state and artifact integrity tests",
      "verify": "Discriminating positive/invalid/rollback tests on ordinary synthetic stores and canonical seven-bar replay",
      "expected": "No fake process authority, no percentage padding; real defects reported and fixed",
      "rollback": "Keep initial failed receipts and isolated source",
      "status": "done"
    },
    {
      "title": "Independent review and final successor qualification",
      "verify": "Exact-tree canonical gate plus separate remaining components if floor blocks full",
      "expected": "No inherited approval; actual counts, scope and residual limits",
      "rollback": "No publication; retain failed checkpoint",
      "status": "pending"
    }
  ],
  "tier_impact": [],
  "docs_to_update": [
    "CLAUDE.md",
    "docs/BUILD-STATUS.md",
    "docs/context/README.md",
    "docs/context/alpha-quant-platform.md"
  ],
  "out_of_scope": [
    "Real data/providers",
    "Native execution on Mac",
    "Security changes",
    "Private-suite or scientific acceptance",
    "Publication"
  ],
  "files": [
    "apps/alpha-cli/src/alpha_cli/durable_lease.py",
    "apps/alpha-cli/src/alpha_cli/native_supervisor.py",
    "apps/alpha-cli/src/alpha_cli/_native_fixture_store.py",
    "tests/unit/test_native_fixture_portability.py",
    "apps/alpha-cli/src/alpha_cli/ml_cmds.py",
    "apps/alpha-cli/src/alpha_cli/ml_contract.py",
    "tests/unit/test_ml_selection.py",
    "tests/unit/test_native_rule_portable_authority.py",
    "tests/unit/test_native_fixture_portable_readers.py",
    "tests/unit/test_native_rule_portable_artifacts.py",
    "tests/unit/test_native_rule_portable_d0_artifacts.py",
    "tests/unit/test_native_rule_portable_admission.py",
    "apps/alpha-cli/src/alpha_cli/_native_rule_economics.py",
    "apps/alpha-cli/src/alpha_cli/_native_rule_artifacts.py",
    "tests/unit/test_ml_compare.py",
    "tests/unit/test_ml_contract.py",
    "tests/unit/test_ml_refit.py"
  ]
}
```

Source and receipts: `.alpha/state/mac-portability/`. Frozen predecessor b0b9c8ea; delivery base bc5b5835. Native incremental source f15c9063 → 35e762d5. No dependency, schema, coverage or authority-policy change.


## Actual Mac findings and bounded repairs

The first full gate passed the first 11 backend steps, then reported **2 failed,
6,281 passed, 149 skipped, 2 subtests passed** and **91.600783%** coverage
(51,443/56,160 statements), below the unchanged 93% floor. Its immutable receipt is
`.alpha/state/mac-portability/canonical-full-attempt1.json` and its public log is
`canonical-full-attempt1.log` in that same directory. Aggregate qualification failed.

Both new failures were capability GETs encountering an absent isolated worker in a
fresh checkout. The scoped CLI fix positively detects an absent worker entrypoint
and returns the existing missing-dependency contract with null Qlib version, empty
observed versions and an explicit not-inspected reason. Installed-worker probe
failures and malformed existing entrypoint paths remain errors. No GET installs dependencies, no root Qlib import is added,
and the web/UI schemas remain unchanged. Public regressions include both route aliases,
missing/partial environments and an installed worker's deliberate probe error.
The first regression failure remains in `missing-worker-red.log`.

A separate bounded actual-Darwin diagnostic traced all 21 previously unresolved
original-tree cases to the Linux-only guard, including the three formerly hidden
worker exceptions. Twelve cascaded through marker/barrier waits, four preempted
injected-fault assertions, three exposed worker errors and two child/cleanup paths.
Three initial reporting-induced setup errors were retained and only those cases
rerun with compatible JUnit reporting. Original sources/index were unchanged.
See `original-failure-diagnosis/diagnosis-summary.md` beneath the evidence directory.
This establishes immediate causes, not downstream native runtime correctness.

Independent review identified genuine portable approval-integrity coverage gaps.
Bounded disposable-store tests exercise the existing confirmation/approval authority;
they do not construct native owner capabilities, spoof Linux or run native processes.
The tested stores have zero jobs/reservations; no claim about preserving nonzero native
charges or live recovery follows from these approval-reader tests.
Kernel-dependent ownership, waitid/pidfd, cancellation, escape and reaping guarantees
still require Linux. No floor, denominator, skip policy or native authority was changed.
Reaching 93% would require at least 786 additional existing statements beyond attempt1;
these bounded tests are not a promise of aggregate acceptance.

## Code, tests and identity navigation

The [CLI readiness change](../../../apps/alpha-cli/src/alpha_cli/ml_cmds.py) uses the
[existing model contract](../../../apps/alpha-cli/src/alpha_cli/ml_contract.py).
[Readiness regressions](../../../tests/unit/test_ml_selection.py) cover absent,
malformed and failed workers plus both existing web aliases.
[Portable authority tests](../../../tests/unit/test_native_rule_portable_authority.py)
exercise the [approval reader](../../../apps/alpha-cli/src/alpha_cli/_native_rule_authority.py).
The [native platform tests](../../../tests/unit/test_native_fixture_portability.py)
retain unsupported-host rejection and explicit kernel prerequisites.

[Final source identity](../../../.alpha/state/mac-portability/final-source.json)
lists every changed path/hash. [Final verification evidence](../../../.alpha/state/mac-portability/final-evidence.json)
is written after the frozen-tree checks finish; it records aggregate failure separately
from passing source review and individual components. These local ignored receipts
are preserved for handoff, not committed test or scientific evidence.

The second canonical attempt on de074d9 had **6,298 passed, 149 skipped, 2 subtests
passed, zero test failures**, but still failed coverage: **51,478/56,170 = 91.6468%**,
below 93%. This remains an actual failed aggregate receipt, not an approved platform
exception. Navigation-only edits follow that checkpoint; final verification is bound
to the updated source identity rather than inheriting its stamp.

## Handoff and next action

The final evidence records source identity, per-step results, review and unresolved gates;
failed attempts remain alongside it. Until that receipt exists, the final check is pending.
The full gate must actually pass before aggregate approval can be claimed. Source
qualification and scientific acceptance remain distinct: query/report/navigation
handoffs are still unavailable here, authentic private-suite coverage is unestablished,
and W11 governed Qlib admission/statistical qualification remain blocked. Preserve
b0b9c8ea, a284def9, 8df4b895 and original native producer receipts. Any next integration
must use verified source bytes and a fresh exact-tree gate; source backout never rolls
back a real database. No real database was used.


## Portable-evidence successor (2026-10-26)

Parent-directed coverage audit is preserved in
[the module/function inventory](../../../.alpha/state/mac-portability/coverage-scope-audit/audit.json).
The 24f checkpoint has all 49 canonical commands accounted for: 48 passed, with statement
coverage 51478/56170=91.6467865% below 93%. Branch coverage was not measured. The unchanged
denominator needs 761 additional covered statements. This is not proved to be an exclusively
Linux-dependent deficit: selected portable reader/accounting/validator/artifact functions have
192 missing statements, before overlap and scenario design. Counts are ceilings, not gains.

The [pre-execution bounded protocol](../../../.alpha/state/portable-evidence/portable-successor-protocol.json)
freezes ordinary synthetic charged-store fixtures, explicit untrusted lifecycle serialization
inputs, and the existing two-role seven-bar canonical numerical fixture. There are no learned
fits, native process launches, scientific replicates, provider calls or native admission claims.
[Reader/accounting tests](../../../tests/unit/test_native_fixture_portable_readers.py) and
[numerical/artifact tests](../../../tests/unit/test_native_rule_portable_artifacts.py) must preserve
state on rejection and distinguish parsing from trusted issuance. Counterfeit NativeLaunch,
owner or observation objects, platform spoofing and disabled immutable protections are excluded.

Current successor receipts live in `.alpha/state/portable-evidence/`; copied historical receipts
in `.alpha/state/mac-portability/` retain their original checkpoint identity and paths. The new
candidate must receive independent review and its own exact-tree gate. No 24f success stamp is
carried forward, and no broader migration, protected-data or statistical-source work is added
merely to raise a percentage. Linux-only ownership/cancellation/reaping remains a separate path.

### Portable checks and validation repairs

The combined focused suite passes 105 tests (32 reader/accounting, 21 D0, 52 numerical/artifact).
Three suites exercise charged-state readers/rollback,
[D0 publication contracts](../../../tests/unit/test_native_rule_portable_d0_artifacts.py),
and the numerical/projection tests linked above. They use the frozen protocol and existing
canonical engine only. Rehashed artifact mutations deliberately pass generic file hashes and
then fail mechanical identity validation. Untrusted native-shaped serialization inputs are
never consumed by admission/completion APIs; their tests assert unchanged SQL and zero
jobs, reservations and attempts. They establish file-contract behavior, not execution provenance.

Discriminating failures exposed Python boolean/float equality accepting integer counts or
fill IDs, an absent control trace raising KeyError, and malformed intermediate curve rows
being accepted or raising untyped exceptions. The validator now checks exact integers and
finite row shape before accounting comparisons. Independent review additionally identified
oversized integer equity overflowing float conversion; its regression and repair are preserved.
The initial eight-case curve receipt includes seven structural/finiteness failures and one
existing DataError whose message differed from the test expectation; it is not eight new bugs.
Initial setup, lint and typing failures remain in the receipt directory as well.

[Successor source manifest](../../../.alpha/state/portable-evidence/final-source.json) and
[successor verification record](../../../.alpha/state/portable-evidence/final-evidence.json)
bind final results and remaining coverage by module to this successor. These receipts are
created during final verification; until they exist, that verification is pending. The original
21-failure diagnosis and 149-skip taxonomy remain in predecessor evidence: immediate Linux
guard failures were diagnosed, not downstream Linux behavior repaired on Mac. No new skips,
coverage configuration changes, native execution or scientific acceptance are introduced.

Next action is exact-tree verification and review of the remaining coverage inventory. A failed
93% floor remains a failed aggregate; unrelated tests or fabricated native owners are not a
remedy. Any remaining portable behavior must be distinguished from paths needing authentic
Linux process ownership and separately approved source/runtime prerequisites.

### Admission-boundary follow-up

The preserved portable checkpoint `72809652a723b1597efd96873780bcfc152cc619` passed
6,403 tests with 149 skips and two subtests, but failed coverage at 51,679/56,172
(92.0014%); 561 further covered statements are required at that denominator. Its public
[comparison inventory](../../../.alpha/state/portable-evidence/coverage-comparison.json)
records 201 more covered statements and two added production statements, with no exclusions.
Branches remain unmeasured. The intermediate checkpoint's remaining components were not
rerun while this bounded follow-up was being prepared.

A final portable admission slice exercises public spec construction, stale job/request
bindings and changed replay identity before reservation effects, using ordinary approved
synthetic stores. It preserves full charges and has no native process/owner/profile capability.
[Admission tests](../../../tests/unit/test_native_rule_portable_admission.py) and their
pre-run rationale/receipts (13 focused tests passed, plus Ruff/format/mypy) live under `.alpha/state/portable-evidence/admission-followup/`.
The final [source manifest](../../../.alpha/state/portable-evidence/admission-followup/final-source.json)
and [verification record](../../../.alpha/state/portable-evidence/admission-followup/final-evidence.json)
are this packet's completion authority for engineering checks; until present they remain pending.
No result from either predecessor is transferred to the final source.

### Costed-result reader-schema repair (2026-10-27, local, unqualified)

`validate_costed_result` accepted role payloads that the projection reader then rejected with an
untyped pydantic error (non-datetime curve times, non-object or incomplete trades, malformed
traces). It now parses each role as `BacktestResult` and raises `DataError`; values, timestamps
and extra keys that the reader accepts are unchanged. Costed native publication validates
economics before its first artifact write, so a rejected receipt now leaves no `runs/` or
`snapshots/` entries. In `fd67548`, an accounting-rejected receipt left the three position files
without a manifest; a reader-schema-invalid receipt passed validation, so `publish_projections`
also created `snapshots/synthetic-rule-*` before raising the untyped error (derived from code
order). With only the schema fix applied, both cases left the three position files without a
manifest (measured). Focused public synthetic receipts live under
`.alpha/state/portable-evidence/repair-20261027/`. These edits are unstaged on top of `fd67548`,
need the exact-tree gate and independent review, and confer no acceptance.

### Portable guard coverage (2026-10-27, local, unqualified)

Tests only since the costed-result repair above; no further production change. Public synthetic
tests now exercise candidate guards that the aggregate coverage receipt reported unexecuted:
native D1 reservation slot, three-launch cap with unlinked attempts, exact fingerprint set,
active-contract spec build, integer exposure budgets, fixed-rule single trial and revision-lineage
charging; schema-3 `point_in_time` rejection; schema-3 Qlib comparison provenance, symlinked
comparison artifacts and the `ml compare` command; and explicit-UTC refit cutoffs. Supervisor,
fixture-store claim/status and retained-child paths still need a Linux host; native launch and
rule-environment measurement need the pinned RD-Agent source and qualified worker environments.
This adds no qualification.
