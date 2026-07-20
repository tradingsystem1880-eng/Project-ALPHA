# ADR-0014: Keep development lifecycle state in a CLI-owned control plane

**Status:** Accepted
**Date:** 2026-07-19
**Deciders:** Owner-approved Workstation v3 plan and AI build agents

## Context

Run manifests are immutable analytical evidence, while projects, stages, attempts, jobs, and
holdout status are mutable operational state. Inferring lineage from the newest run or embedding
project timestamps/status into manifests breaks both semantics.

## Decision

`alpha_cli` owns a local SQLite control database outside `RUN_DIRS`. It stores mutable projects,
append-only project-scope/stage/attempt/holdout/job events, and immutable content-addressed strategy
versions and experiment specs. Project-scope events preserve version/experiment selection history
for point-in-time AgentBrief reads. Run lineage is an external atomic link; completed manifests are
untouched.

The web and MCP surfaces use public CLI projections/actions and never query SQLite directly.
Holdout reveal, contamination, candidate freeze, paper launch, and promotion have explicit audited
transitions. All attempted configurations, including failures and rejections, are retained.

Terminal analytical states are suite-owned: a generic caller cannot mark a run-backed stage pass,
warning, or fail. Before aggregate completion the control plane verifies the exact expected run
kind, manifest v3 artifact hashes, evidence set, and prerequisites. Holdout reveal rebuilds those
canonical prerequisites and requires a dated sealed boundary. Suite job kinds are reserved from the
generic API. One capacity-one job class covers direct REST/MCP Qlib/Kronos actions and the Qlib/
Kronos suites; the active-state check and insert occur under the same SQLite write transaction.
Persisted cancellation/reconciliation grants no raw PID authority.

Every direct heavyweight child launched by the Workstation or MCP runs in an isolated process
group. `DurableJobLease` renews its journal independently of stdout every five seconds (and rejects
intervals above ten), polls the audited cancellation flag, and fails the journal if renewal or
cancellation polling fails. Cancellation or lease failure sends TERM to the owned process group,
waits a bounded grace period, escalates to KILL, and reaps the direct child. The owner stops and
joins the lease before publishing any later terminal state, so a cancelled or failed lease cannot
be overwritten by success. Liveness is measured for the full process group rather than only its
leader; every post-spawn initialization boundary either starts its owner/heartbeat or verifies the
group stopped before terminalizing. An unverified cleanup remains nonterminal and retains capacity.
Suite execution supplies the equivalent five-second heartbeat, cancellation polling, process-group
termination, and reap around each subprocess step.

Restart reconciliation remains deliberately logical. It may fail a stale queued/running journal
after interruption is confirmed, but it does not signal a stored PID or prove that an
operating-system orphan is dead. If the surface owner itself crashes, an orphan may survive and the
operator must confirm/reap it before reconciling and relaunching; multi-process crash recovery and
cross-crash physical capacity enforcement require a later ADR.

## Implementation anchors

- `apps/alpha-cli/src/alpha_cli/control_store.py:ControlStore` owns migrations, transactions,
  stage/run verification, holdout audit, jobs, cancellation requests, and decisions.
- `apps/alpha-cli/src/alpha_cli/job_capacity.py` is the lightweight shared classifier for every
  heavyweight launch surface; `project job-capacity` exposes exact unpaginated occupancy.
- `apps/alpha-cli/src/alpha_cli/durable_lease.py:DurableJobLease` owns independent direct-child
  renewal, cancellation polling, TERM/KILL escalation, and reap semantics.
- `apps/alpha-cli/src/alpha_cli/_suite.py:build_suite_plan` and `execute_suite` own allowlisted workload
  resolution, execution, heartbeat/cancellation polling, and child-process-group cleanup;
  `suite_cmds.py` exposes the CLI projection.
- `apps/alpha-web/src/alpha_web/api/development.py` and
  `apps/alpha-mcp/src/alpha_mcp/_control.py` are thin bounded subprocess surfaces.
- Regression evidence: `tests/unit/test_control_store.py`, `tests/unit/test_decision_packet.py`,
  `tests/unit/test_durable_job_lease.py`, `tests/unit/test_suite_planner.py`,
  `tests/unit/test_suite_executor.py`, `tests/unit/test_web_invoke.py`,
  `tests/unit/test_web_ml.py`, `tests/unit/test_mcp_invoke.py`,
  `tests/integration/test_control_cli.py`, `tests/integration/test_suite_cli.py`,
  `tests/integration/test_web_api_jobs.py`,
  `tests/integration/test_web_api_job_cancellation.py`, and
  `tests/integration/test_mcp_server.py`.

## Options considered

- Put project metadata in manifests: rejected because mutable, wall-clock state would alter evidence.
- Keep frontend-local JSON state: rejected because agents/CLI cannot share or audit it reliably.
- CLI-owned SQLite: chosen for transactions, restart-visible journals, zero new runtime dependency,
  and thin surfaces.

## Consequences

- Easier: durable lineage, bounded cancellation, holdout governance, multi-surface parity.
- Harder: database migrations, explicit projections, and operator confirmation after an owner crash.
- Revisit: multi-host/multi-user operation would require a new control-plane ADR.
