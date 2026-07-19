# ADR-0012: Operational paper sessions remain separate from deterministic research runs

**Status:** Accepted
**Date:** 2026-07-19
**Deciders:** AI build agents (per `CLAUDE.md`)

## Context

ALPHA research runs are content-addressed evidence. Their `run_id` derives from canonical inputs,
their manifests are byte-stable, and no wall clock, PID, heartbeat, or mutable process state may
enter the identity. A live-data paper session has the opposite operational needs: a unique launch
identity, process lifecycle, wall-clock heartbeat, terminal error, and append-only order/fill
events. Treating both as one artifact type would either corrupt research determinism or make paper
monitoring unusable.

The distinction is semantic as well as technical. A sandbox session is an operational observation,
not a validated out-of-sample result, even when it uses the same strategy class and a verified
snapshot for warmup.

## Decision

Keep the two planes separate:

| Plane | Identity | Location | Time semantics | Authority |
|---|---|---|---|---|
| Research | content-derived `run_id` | `data_dir/<RUN_DIRS kind>/<run_id>/` | deterministic inputs; no wall clock in identity/manifest | validation and reproducible evidence |
| Paper operations | random UUID `session_id` | `data_dir/paper/<session_id>/` | start/end time, PID, heartbeat, event sequence | monitoring only; never validation evidence |

Paper session state is published as `session.json` plus atomic
`events/<zero-padded-sequence>.json` records. Only lifecycle, order, fill, rejection, position, and
reconciliation-warning events are persisted; ticks and bars are not journaled. The journal is
bounded by event meaning rather than market-data volume.

An `ExecutionEventSink` protocol lives in `alpha_core` so strategy classes can emit operational
events without importing the CLI store. The sink is optional and supplied only in paper mode. It
is outside `RunSpec`, run-id inputs, and deterministic manifests. Historical snapshot priming uses
the same strategy class without emitting orders or operational events.

Paper APIs and CLI commands are separate from run-store APIs and commands. A Workstation job may
carry an additive `session_id` so its known child process can be cancelled through the existing job
control. A stale heartbeat is reported as stale; it never authorizes killing an arbitrary PID.

Paper state must never be copied into `RUN_DIRS`, presented as a gauntlet result, or used to change
a deterministic run's hash. Promotion of observations into a future research dataset would require
a separate immutable-ingestion specification and provenance contract.

**Code anchors:** `apps/alpha-cli/src/alpha_cli/paper_store.py` (operational store),
`apps/alpha-cli/src/alpha_cli/_paper.py` (node lifecycle),
`packages/alpha-core/src/alpha_core/protocols.py` (`ExecutionEventSink`),
`apps/alpha-cli/src/alpha_cli/run_store.py` (`RUN_DIRS` research boundary), and
`apps/alpha-web/src/alpha_web/_invoke.py` (known-child job lifecycle).

## Options Considered

### Option A: separate operational session journal (chosen)

| Dimension | Assessment |
|---|---|
| Complexity | Low-to-moderate; one small store and explicit API family |
| Cost | Small bounded JSON journal; no tick/bar firehose |
| Correctness-risk | Low; mutable clocks cannot contaminate research hashes |
| Fit | Excellent for single-user local monitoring |

### Option B: store paper sessions as normal runs

| Dimension | Assessment |
|---|---|
| Complexity | Superficially low, but forces incompatible schemas together |
| Cost | Ongoing special cases in every run reader, manifest, and validation surface |
| Correctness-risk | High; wall-clock/process fields undermine byte stability and evidence semantics |
| Fit | Poor |

### Option C: keep paper lifecycle only in process memory

| Dimension | Assessment |
|---|---|
| Complexity | Lowest |
| Cost | Lost audit trail and monitor state on restart/crash |
| Correctness-risk | Medium; failures and reconciliation warnings disappear |
| Fit | Poor for durable supervision |

## Trade-off Analysis

The separate store creates a second read model, but it prevents a far more dangerous second meaning
for a research manifest. Atomic small JSON records are sufficient for the selected event volume and
avoid a database dependency. UUID identity honestly represents an operational launch rather than
pretending a network session is reproducible.

## Consequences

- **Easier:** crash diagnosis, cursor-incremental event reads, stale-heartbeat reporting, and preserving research
  byte compatibility.
- **Harder:** paper sessions cannot reuse generic run-store readers or claim validation status.
- **Revisit when:** event volume requires compaction, multiple hosts must coordinate sessions, or a
  separately governed immutable operational-data ingestion path is approved.
