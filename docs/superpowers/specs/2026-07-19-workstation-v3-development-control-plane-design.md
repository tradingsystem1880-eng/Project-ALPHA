# Design — Workstation v3 development control plane

**Status:** Implemented; offline release gate passed
**Date:** 2026-07-19
**Implementation reviewed:** 2026-07-19
**Authority:** `CLAUDE.md`, ADR-0002, ADR-0006, ADR-0014

## Goal and boundary

Replace the command-form-only Strategy Lab and heuristic pipeline with a durable, auditable
development lifecycle. `alpha_cli` owns all state and orchestration. `alpha_web` and `alpha_mcp`
use typed CLI projections/actions and never query the control database or compose engines.

Mutable control state is stored in a CLI-owned SQLite database under `data_dir/control/`, outside
all deterministic `RUN_DIRS`. Immutable run artifacts remain the source of analytical evidence.

## Public domain records

- `StrategyProject`: hypothesis, falsification criterion, owner state, sealed holdout, current
  strategy version, and promotion state.
- `StrategyVersion`: immutable content hash of normalized strategy definition, parameter space,
  and source/registry fingerprint.
- `ExperimentSpec`: immutable content hash of strategy version, snapshot/universe, split policy,
  costs, seed, and stage configuration.
- `StageRunLink`: project/version/stage/experiment-to-run lineage stored outside run manifests.
- `AttemptRecord`: every queued, completed, failed, pruned, and rejected configuration.
- `HoldoutEvent`: sealed/revealed/contaminated audit with observation time and reason.
- `JobEvent`: UUID job lifecycle, heartbeat, cancellation, logs, and result link.

All immutable records reject conflicting rewrites. Mutations use SQLite transactions. Database
migrations are explicit and tested; research run directories are never used as mutable state.

## Lifecycle

The eleven owner-facing workflow steps below map to **12 core stage IDs** because parameter
optimization and broader robustness are separately governed. The exact core IDs are `hypothesis`,
`data`, `strategy`, `baseline`, `oos`, `robustness`, `optimization`, `portfolio`, `candidate`,
`holdout`, `paper`, and `decision`. Independent `kronos` and `ml` research tracks bring the exposed
control-plane total to **14 stage IDs**; they do not silently advance the core lifecycle.

1. Hypothesis and falsification criterion.
2. Frozen universe/snapshot/costs and sealed final holdout.
3. Immutable strategy version and declared parameter search space.
4. Baseline discovery run.
5. Inner OOS/walk-forward evaluation.
6. Parameter and robustness research.
7. Portfolio/cross-asset analysis.
8. Frozen candidate.
9. One-shot final holdout reveal.
10. Sandbox paper preflight/session.
11. Accept/reject/revise decision packet.

Stage states are `not_started`, `ready`, `queued`, `running`, `pass`, `warning`, `fail`, and `stale`.
A changed strategy or experiment fingerprint makes dependent stage links stale. Optimization and
model selection cannot read the sealed final holdout. Any change after reveal creates a new version
and permanently contaminates that holdout for the lineage.

Rule-strategy walk-forward is described honestly as OOS evaluation with warmup windows, not model
refitting. ML experiments must refit within every training fold.

## Workflow actions

The CLI exposes additive project and suite command groups used by the workstation:

- create/read/list projects and immutable versions/specs;
- link or explicitly adopt a canonical run;
- plan/run/status for baseline, inner OOS, null sensitivity, deterministic grid optimization,
  fixed stress, portfolio/cross-asset, Kronos run/eval, Qlib run, holdout reveal, and paper preflight;
- record all attempts and freeze a decision packet.

The UI previews the fully resolved immutable specification and workload before launch. Holdout reveal,
paper launch, and promotion require an explicit owner action and are not available to an unattended
agent tool.

## Null semantics

The three return-null families are separate evidence, not votes:

- stationary bootstrap is the headline Tier-1 family and is paired with the existing full-engine
  Tier-2 gate;
- Student-t and GARCH are labeled Tier-1 sensitivity analyses pending calibration;
- fixed stress, risk-of-ruin, prop-firm Monte Carlo, and Kronos samples remain separate workflows.

Stable semantic seed namespaces ensure inserting or reordering a family does not perturb an
existing result.

## Acceptance

- Atomic/concurrent project mutations and schema migrations are tested.
- Duplicate immutable IDs verify identical content and reject conflicts.
- Holdout access, contamination, stale propagation, and negative-attempt accounting are tested.
- Direct and suite jobs heartbeat independently of output, honor audited cancellation, terminate and
  reap their owned child process groups, and cannot overwrite lease failure/cancellation with success.
- Stale journals reconcile only after confirmed interruption and grant no stored PID authority.
- Existing CLI commands and all v1/v2 run readers remain compatible.

## Current implementation note — 2026-07-19

The control plane is implemented in `alpha_cli.control_store.ControlStore`, with CLI projections in
`project_cmds.py`, allowlisted suite planning/execution in `_suite.py` / `suite_cmds.py`, and thin
REST/MCP subprocess surfaces. Generic callers cannot write a terminal analytical stage. A suite can
complete a governed stage only after the control store verifies the expected immutable run type,
manifest v3 artifact hashes, exact evidence set, and prerequisite lineage. Holdout reveal rebuilds
and revalidates canonical prerequisite evidence and requires a dated sealed boundary; a subsequent
version/configuration change contaminates the revealed lineage. Reserved suite job kinds cannot be
created through the generic job API. Direct Workstation, MCP, Qlib, Kronos, and suite launches all
reserve the same capacity-one heavyweight class inside the job-creation write transaction, so
cross-surface and concurrent calls cannot bypass it.

Durable jobs persist heartbeats, log/result links, and idempotent cancellation requests. Direct
Workstation/MCP Qlib and Kronos children run in isolated process groups with a
`DurableJobLease`: renewal and cancellation polling happen every five seconds independently of
stdout, the supported interval is capped at ten seconds, and poll/renewal failure is terminal.
Cancellation or lease failure sends TERM, waits a bounded grace period, escalates to KILL, and
reaps the direct child. Group-based liveness keeps renewing when the direct leader exits before a
descendant, including when that descendant retains stdout/stderr. Constructor, selector, heartbeat-
thread, and output-pump failure paths verify cleanup before terminal publication; if cleanup cannot
be verified, the journal stays nonterminal and retains the heavyweight slot. The owner stops and
joins the lease before it can publish a later terminal state. Suite workers provide the equivalent
five-second heartbeat/cancellation polling and process-group cleanup around every step. The
Development Center rehydrates queued/running journals after reload and makes loading, empty,
failure, retry, and cancellation states visible.

Reconciliation is bounded by stale-heartbeat policy and grants no raw PID authority. It records a
logical failed transition only after interruption is confirmed; it cannot prove that a child
survived or died when its owning surface crashed. An operator must confirm/reap any orphan before
reconciling and relaunching. Automated orphan recovery and cross-crash physical capacity guarantees
remain out of scope for this single-user control plane.

Primary checks live in `tests/unit/test_control_store.py`, `tests/unit/test_decision_packet.py`,
`tests/unit/test_suite_planner.py`, `tests/unit/test_suite_executor.py`,
`tests/unit/test_durable_job_lease.py`, `tests/unit/test_web_invoke.py`,
`tests/unit/test_web_ml.py`, `tests/unit/test_mcp_invoke.py`,
`tests/integration/test_control_cli.py`, `tests/integration/test_suite_cli.py`,
`tests/integration/test_web_api_suite.py`, and
`tests/integration/test_web_api_job_cancellation.py`. The offline release evidence is recorded in
the audit closeout; this note does not convert the local SQLite design into multi-host authority.
