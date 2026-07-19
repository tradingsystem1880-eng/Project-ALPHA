# Design — Workstation v3 development control plane

**Status:** Approved for implementation  
**Date:** 2026-07-19  
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
- Durable jobs reconcile after restart and only known live child process groups may be cancelled.
- Existing CLI commands and all v1/v2 run readers remain compatible.

