# Bounded mutation sweep checkpoints

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
