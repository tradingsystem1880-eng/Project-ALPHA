# D1 durable job recovery repair

Historical packet for the e635-based PR93 candidate. Its original focused results below do not
attest a later reconciliation. Current implementation and fresh verification are tracked in the
[PR95 reconciliation](2026-10-29-pr93-recovery-reconciliation.md); aggregate acceptance remains pending.

```json
{
  "schema_version": 1,
  "title": "D1 durable job recovery repair",
  "context": "On the e635-based PR 89 candidate, a reproduced P2 showed that D1 artifact recovery searched only the newest 500 global jobs. This packet fixes that lookup without changing D1 authority, artifact validation, host-liveness policy, or publication behavior.",
  "assumptions": [
    {
      "statement": "The integration candidate is based on e635e6cb5bc7b9fa688dc524998d7fe1ff8eebdc, which adds the inert RD-Agent foundation manifest.",
      "verified_by": "git rev-parse HEAD and git show --no-patch --format=fuller HEAD"
    },
    {
      "statement": "D1 recovery may admit only the exact project, contract, stage, attempt, verified run, and evidence identity; stale owner liveness remains unresolved without trusted host binding.",
      "verified_by": "apps/alpha-cli/src/alpha_cli/research_cmds.py and the D1/D2 lifecycle tests"
    }
  ],
  "alternatives_considered": [
    "Raise the global job page limit: rejected because unrelated job growth can still hide the journal and increases every recovery scan.",
    "Add a new schema/index for request fields: deferred because a project-scoped query plus exact in-transaction request matching fixes the bounded lookup with no migration."
  ],
  "pre_mortem": [
    "Wrong-project, contract, stage, or attempt journals could be mistaken for the interrupted D1 run; reject all such mismatches and test synthetic decoys.",
    "A large global backlog could hide the target job; select failed research journals by project and read their event window from the same SQLite snapshot.",
    "Recovery could duplicate publication or overstate evidence; retain immutable artifact, D1 watermark, contract, and exact-replay checks.",
    "A stale heartbeat could be mistaken for owner death; retain capacity until a separate trusted host-binding policy exists."
  ],
  "slices": [
    {
      "title": "Project-scoped exact D1 recovery lookup",
      "verify": "Run the terminal-job recovery integration test with 505 newer unrelated jobs plus identity and cross-project decoys.",
      "expected": "Only the exact failed D1 journal and same-snapshot event window are considered; the original immutable run is admitted once and exact replay does not rerun the worker.",
      "rollback": "Revert the lookup and regression-test diff while retaining prior candidate evidence and immutable artifacts.",
      "files": ["apps/alpha-cli/src/alpha_cli/control_store.py", "apps/alpha-cli/src/alpha_cli/research_cmds.py", "tests/integration/test_research_cli.py"],
      "status": "done"
    },
    {
      "title": "Focused candidate preflight",
      "verify": "Run focused D1/D2/cancellation tests, Ruff, strict mypy, plan-check, Atlas freshness, and independent review; leave the full gate for an assigned exclusive slot.",
      "expected": "The corrected e635-based candidate has reproducible focused receipts and a fresh review; canonical full-gate acceptance remains pending.",
      "rollback": "Keep the isolated candidate and evidence; do not publish or modify other worktrees if any check fails.",
      "files": [".claude/rules/alpha-cli.md", "docs/BUILD-STATUS.md", "docs/atlas/**", "docs/superpowers/plans/2026-10-24-d1-job-recovery.md"],
      "status": "done"
    }
  ],
  "tier_impact": ["risk"],
  "docs_to_update": [".claude/rules/alpha-cli.md", "docs/BUILD-STATUS.md", "docs/superpowers/plans/2026-10-24-d1-job-recovery.md"],
  "out_of_scope": ["Automatic stale D1/D2 owner recovery without a trusted host identity.", "RD-Agent installation or activation.", "Full-gate qualification, publication, merge, or deployment."],
  "files": ["apps/alpha-cli/src/alpha_cli/control_store.py", "apps/alpha-cli/src/alpha_cli/research_cmds.py", "tests/integration/test_research_cli.py"]
}
```

## Scope

Repair the reproduced D1 artifact-recovery window using existing `jobs`, `job_events`, research
execution events, attempts, and immutable run manifests. Record the content-derived D1 run identity
in the job journal before analysis. A stale heartbeat does not release a D1 or D2 capacity slot because
the repository has no trustworthy owner-host identity and `ALPHA_DATA_DIR` is configurable; a PID
miss on the current host cannot establish that a remote owner stopped. Automatic reconciliation for
the shared `research:event-study` D1/D2 job kind therefore remains disabled pending a separate
owner-host binding decision. After a
D1 job is already terminal, verify any present run directory and admit the completed attempt through
the existing immutable-run and D1 evidence validators. A present but incomplete or corrupt
directory fails closed. Active cancellation becomes a durable job request and retains the
active-job binding until the worker observes it at a checkpoint.

## Boundaries and dependencies

- No new schema, dependency, route, worker process, provider, credential, or scientific owner.
- D1 remains discovery-only; manifests and attempt admission retain their existing D1 checks.
- D1 and D2 jobs without trusted owner-host identity remain unresolved and retain capacity; no
  local-only data-path assumption is made.
- No private or holdout fixtures, native RD-Agent runtime, full gate, publication, or merge.
- This does not qualify native runtime behavior or establish exactly-once execution.

## Focused acceptance

- Stale D1 and D2 heartbeats with no proven owner-host match retain the job and capacity without
  probing a local PID; generic `project job-status` cannot terminalize these research journals.
- A verified published run is admitted once with the original attempt number and exact run ID;
  repeated recovery returns the same attempt.
- Recovery reads failed D1 journals for the exact project, contract, stage, and attempt from one
  SQLite snapshot; unrelated jobs cannot hide the match, and cross-project or mismatched identity
  journals are ignored.
- Artifact hash mismatch blocks recovery without a new runner call or attempt.
- Cancellation requests do not clear a live owner; the next checkpoint records terminal state.
- Unbound D1 execution and D0 launches with unfinalized reservations cannot be cancelled. A
  genuinely queued non-D1 checkpoint and a terminal failed pilot with no unfinalized reservation
  may return to idle only if the execution state still matches the state read by the CLI.
- Existing concurrent heavyweight admission and ordinary failed-run retry behavior still pass.

## Rollback

Revert the isolated patch and retain all job events, attempt records, and immutable run artifacts.
Do not delete or rewrite historical evidence. Without a trustworthy owner-host decision, keep a
stale D1 capacity slot unresolved for owner inspection rather than launch another run.
