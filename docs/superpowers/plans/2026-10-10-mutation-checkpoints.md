# Bounded mutation sweep checkpoints

**Current status — 2026-10-17:** [PR #54](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/54) and its bounded fixture follow-up [PR #57](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/57) are accepted, each with seven successful required checks. Sweep 38233472012-1 on 430ddeb remains historical infrastructure-complete accounting, not current-main adequacy evidence. Later public staging/test changes in PRs #62–#64 mean current adequacy is UNMEASURED; no new sweep or floor-pass claim is made here.

Earlier dated status and incident entries are preserved as historical records.

```json
{
  "schema_version": 1,
  "title": "Durable bounded mutation sweep",
  "context": "Serial nightly cancellation requires durable exhaustive hosted measurements; owner selected weekly cadence and authorized focused publication, hosted verification and policy-compliant merge on 2026-10-10.",
  "assumptions": [
    {
      "statement": "Weekly cadence is owner-selected in current staged checkout",
      "verified_by": "Direct owner instruction: preserve owner-selected weekly cadence; current shared checkout staged weekly scheduling decision."
    }
  ],
  "alternatives_considered": [
    "Fixed multi-module shards rejected because worst-case sequential phases exceed six hours",
    "Increasing serial timeout rejected"
  ],
  "pre_mortem": [
    "A cancelled worker leaves unfinished checkpoint: aggregate rejects it",
    "Upload fails: missing exact module result fails aggregate"
  ],
  "slices": [
    {
      "title": "Isolate staging and clean process groups",
      "verify": "pytest tests/unit/test_claude_harness_gate.py -k QuantRigorTooling",
      "expected": "Local unavailable and score semantics preserved",
      "rollback": "Revert only new harness edits",
      "status": "done"
    },
    {
      "title": "Checkpoint and validate exhaustive identity-bound results",
      "verify": "pytest tests/unit/test_mutation_sweep.py tests/unit/test_mutation_report.py",
      "expected": "Partial and stale results rejected; score failures report-only",
      "rollback": "Revert sweep script and new tests",
      "status": "done"
    },
    {
      "title": "Wire workflow artifacts, document and verify final tree",
      "verify": "uv run python scripts/gate.py full",
      "expected": "Fresh full verification or explicit blocker; hosted completion separately unverified",
      "rollback": "Revert only new weekly workflow edits",
      "status": "done"
    },
    {
      "title": "Publish focused PR, prove hosted completeness and merge under normal policy",
      "verify": "Required CI plus complete mutation sweep, normal merge and exact merged-SHA post-merge CI",
      "expected": "Verified exact commit, expected module artifacts and honest score/infrastructure distinction",
      "rollback": "Revert focused PR through normal protections",
      "status": "in_progress"
    }
  ],
  "tier_impact": [
    "protected"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    "docs/BUILD-STATUS.md",
    "docs/operations/claude-code-harness.md"
  ],
  "out_of_scope": [
    "Baseline edits",
    "Hidden source access",
    "Unrelated cleanup changes",
    "Unrelated deployment",
    "Paid upgrades",
    "Gate bypasses",
    "Cadence changes"
  ]
}
```

Preserve the owner-selected weekly cadence and existing staged cleanup changes. Complete generated
mutant inventories now partition into balanced isolated jobs of at most 96 mutants after measured
singleton and four-way deadlines failed; eight concurrent jobs at most, two mutmut
children per job. Preserve all module/test selection and mutation floors.

Slices: (1) isolated harness staging and checked export; verify existing quant tooling tests;
(2) identity-bound inventory, atomic checkpoints, process-group deadlines and exact aggregate;
verify focused sweep tests; (3) always-upload workflow and honest docs; verify workflow contracts,
lint/types, then canonical `uv run python scripts/gate.py full`.

No package DAG, research authority, baseline, hidden-test source, or score semantics changes.
Hosted completion remains unverified until the authorized hosted checks and full mutation sweep finish. Merge also requires fresh independent review and all seven protected branch checks.

## Scoped owner decision — 2026-10-10

Asked: "Do you approve a one-time exception only for this mutation-check fix, leaving
private coverage marked UNVERIFIED? Codex would still require public checks, hosted CI,
the complete hosted mutation sweep and fresh independent review before merging. This
wouldn't waive failed tests, grant private-source access or apply to future work."
The owner answered "yes". This applies only to changes under this plan. Metadata confirms
`tests/holdout/` is absent in both checkouts. Its rejected execution was not retried and
no private source was read. Record that coverage UNVERIFIED; absence alone is nonblocking
for this fix. The receipt is in `.claude/agents/independent-reviewer.md`; all public gates,
fresh review, hosted completeness and normal Git/branch protections remain required.

## Hosted constant-module repair — 2026-10-10

Initial candidate `2c90f008` passed all seven required hosted CI checks (harness required one
retry after an ephemeral copied `.git/objects/maintenance.lock` disappeared). Complete run
`38048650465-1` preserved its failed `figures/version.py` checkpoint: mutmut 3 produced no
executable mutants for this constant-only module and exited during test association. Its
official README recommends mutmut 2 for module-level code. A bounded local reproduction
with pinned 2.5.1 generated and executed four mutations; all four were killed. The narrow
fallback preserves tests/exclusions, timeouts, process cleanup and scoring. Its strict export
rejects empty, wrong-module, unknown and unfinished records. Inventory freezes the backend.
Fresh final full/review and complete hosted validation are required for the repaired tree;
the prior run does not prove it. No source-module, baseline or private-suite changes.

## Hosted deadline repair — 2026-10-10 (in progress)

Candidate `1605b5b` passed all six local full components, 213 public focused tests, fresh independent
review and all seven required hosted CI checks. Its hosted constant-only module measured four
actual mutants successfully. Run `38052927037-1` then hit the unchanged 5400-second mutation limit
on data (224/239 measured), boundary (1083/1810) and crypto crowding (971/1333); retained valid error
checkpoints and logs confirm process-group cleanup. These unfinished results cannot authorize merge.
The owner explicitly authorized complete deterministic mutant-level partitioning on this evidence.

Pinned 3.8.0 uses its same source generator and canonical identities, with sorted round-robin
fragments (at most four per functional module, at most 205 jobs). Every fresh stage checks the full
regenerated inventory before measuring exact assigned identities. Aggregate rejects incomplete,
overlapping, stale or inconsistent results and recomputes original module scores from full coverage.
The constant-only pinned legacy backend remains isolated and exhaustive. Setup/test-statistics costs
repeat up to four times per module, while eight-job/two-worker concurrency and all deadlines remain.
No test selection, baseline, mutation operator, timeout/no-tests verdict or score standard changes.
Verify focused adapter/aggregate tests, actual failed-module reproduction, final canonical full,
fresh independent review, then new exact-head hosted CI and complete sweep before normal merge.

The no-association case requires a dedicated certificate from successful fresh full collection,
bound to source/tool/inventory/effective configuration and staged imports. It preserves real mutant
identities, assigns only conservative no-tests verdicts and never catches generic upstream failures.
Verify actual pinned-tool collection and negative proof regressions before final acceptance.

Actual final-code diagnostics completed locally: data accounted for all 239 canonical mutants
in four disjoint fragments (176 killed, five survived, 58 timeout; 0.7364 score fails its unchanged
0.8182 floor). Complete collection certified the 30 generated `_atomic` mutants as conservative
no-tests, zero kills and score failure at the unchanged 0.90 floor, with 527 real test records.
The first two data fragments used the initial exact-name CLI adapter; the last two and `_atomic`
used the final pinned adapter. These are diagnostic receipts, never full hosted acceptance.
The old hosted head also retained gate-packet timeout progress 2250/3019. New exact-head hosted
completion, final canonical full and fresh bound review remain acceptance requirements.


## 2026-10-11 — bounded WAL negotiation during hosted mutation collection

Final fragment head `31e64420` generated the complete hosted inventory (52 modules, 205 jobs,
21,555 functional mutants), independently validated against commit/run identity and source hashes.
One `_arrays` fragment failed unmutated collection at the existing public concurrent v1 migration
test with `DataError("cannot initialize control store")`; other fragments passed. The initial
assertion omitted the chained cause. A real temporary-database contention reproduction captured
`SQLITE_BUSY` (code 5) at `PRAGMA journal_mode = WAL`, wrapped by the same error.

The bounded follow-up retries only exact `SQLITE_BUSY` outside a transaction, within the existing
configured busy-timeout budget for WAL negotiation (normally five seconds). Each attempt receives
only the remaining budget, and the original timeout is restored. This is not a bound on all of
`_open`; migrations retain their separate existing waits. Non-BUSY errors and exhausted budgets
still fail loudly. Migration ordering, backups, protected schema and owner authority are unchanged.
The existing migration assertions/timeouts/test selection remain; failure-only diagnostics retain
chained traceback, statement and SQLite code. A real contention regression failed before and passed
after the fix; budget exhaustion, read-only failure and timeout restoration also passed.

Fresh public full verification, independent review and new exact-head complete hosted acceptance
remain pending for this follow-up. No partial/stale hosted verdict, score floor or private-suite
exception is reused or broadened. SQLite reference: https://www.sqlite.org/c3ref/busy_handler.html.


### 2026-10-11: measured fragment sizing follow-up

At `da463cee`, hosted sweep `38136100567` failed rendering fragment 46 at the unchanged
5400-second mutation budget: 441 of 444 assigned mutants reached terminal status. The checkpoint
remained an error and strict aggregation did not accept its three unfinished mutants. The run was
explicitly cancelled after retaining its failure and all 69 started checkpoint/log artifacts;
60 fragments completed, eight were interrupted and 136 never started. None is reused for acceptance.

Cross-group sizing considered every started fragment, including event's 5198.5-second completed
phase and conservative elapsed/progress estimates for interrupted leadlag jobs. Balanced sorted
round-robin partitions now cap each fragment at 96 mutants. The same complete 52-module inventory
produces 250 jobs, below the unchanged 256-job hard limit. Exhaustive keys, module/test scopes,
associated tests, worker/concurrency limits, timeouts, floors and report-only score semantics remain
unchanged. More setup and test-statistics runs are the explicit cost. Timing projections are estimates;
never-started groups and a fresh complete hosted sweep remain unverified.

Focused red regressions reproduced the old partition failure before implementation. Fresh focused
checks, canonical full verification, independent review and exact-head hosted CI/complete sweep
are required before this follow-up can be accepted or merged. Private suites remain unverified under
the existing scoped owner exception; standing policy is unchanged.


### 2026-10-12: deterministic signed PIP oracle follow-up

Sweep `38151251890` at `3c3a7760` completed 249 of 250 fragments successfully. PIP-miner
fragment 4 (index 147) failed during clean test statistics; its error checkpoint retained all
94 assigned mutants as unmeasured. Aggregate job `114573250539` correctly rejected the
unfinished record. This was an oracle failure, not a phase deadline: the differential
reference used unmirrored negative-total returns despite the documented symmetric ranking,
and a module-global RNG made inputs depend on selected test order. Seed 11 at normal-draw
offset 4250 reproduces the logged mismatch to float64 precision; the hosted order was not logged.

The bounded test-only repair gives each PIP oracle/unit test its own seeded RNG and checks
positive, negative and zero totals explicitly, retaining the counterexample and running-peak
negative control. Production maths, tolerances, test scope, all mutant identities and score
floors are unchanged. Repeated/reversed execution, applicable static checks, fresh canonical
full, independent review and new exact-head hosted CI/exhaustive acceptance remain required.
Private coverage remains UNVERIFIED under the existing scoped decision. PR #54's description
remains untouched; failed/partial historical verdicts are never reused for acceptance.


### 2026-10-12: post-merge harness-template isolation follow-up

PR #54 merged as `5b0b422d` after exact-head CI and exhaustive sweep `38233472012`
passed. Independent aggregation verified all 52 modules, 250 checkpoints, 252 unique
artifacts and 21,555 functional plus four legacy constant mutants; twelve score misses
remain report-only under unchanged floors. The merged Git tree equals the accepted tree.
PR #54's description remained byte-for-byte unchanged.

Post-merge CI `38272832758` reported 5,321 tests passed and coverage 93.13%, but one
harness fixture setup failed: copying the session template raced Git's removal of
`.git/objects/maintenance.lock`. The bounded follow-up disables automatic maintenance
only in the throwaway template before its initial writes; copied fixture repositories
inherit the setting. Copy failures remain visible, and production/Git user configuration,
mutation source, scope, inventory and baselines remain unchanged. A forced-maintenance
TRACE2 regression fails before the fix and passes after it; its positive control launches
actual foreground maintenance and packing with local suppression removed.

Focused public checks pass; fresh canonical full, independent review and hosted checks
remain required. Private coverage remains UNVERIFIED. This standalone fixture delta has
no risk-tier, quant or protected-path trigger, so the specialized private-suite review rule
does not apply. No exception is inferred or broadened; no private execution has been retried.


### 2026-10-13: final combined verification target

The corrected fixture tree `bf0fd3bb` received ordinary independent approval, but its
canonical full stopped on a one-wheel chart assertion. The failed full and subsequent
readonly diagnostics remain historical evidence; isolated passes were not accepted as
closure. The chart owner proved queued resize range restoration overwrote a later
trusted wheel, then prepared the minimal call-order correction and actual-component
settled-span regression in the [wheel plan](2026-10-12-chart-resize-wheel-order.md).

The final isolated target combines those two source/test files with the unchanged
Git-fixture repair, its ordinary scope correction, hash-verified generated SPA assets
and regenerated Atlas fingerprints. The original chart assertions, gestures, timeouts
and PNG baselines remain unchanged. The chart owner's complete fixed-browser terminal
result precedes one fresh combined canonical full, independent review and exact-head
hosted CI; normal merge and post-merge checks remain required. Private coverage is
UNVERIFIED, with no specialised trigger or inferred exception for these ordinary paths.
Protected mutation staging and the accepted exhaustive inventory remain separate.
