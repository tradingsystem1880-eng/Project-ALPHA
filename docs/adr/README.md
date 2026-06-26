# Architecture Decision Records

This folder records the **load-bearing decisions** behind Project ALPHA's architecture — the ones with real alternatives that were considered and rejected. The stable map (DAG, layers, data flow) lives in [`../ARCHITECTURE.md`](../ARCHITECTURE.md); each record below captures the *why* and the trade-offs for one decision, anchored to the code that implements it.

## Index

| Number | Title | Status | Date |
|---|---|---|---|
| [0001](0001-strict-layered-dag.md) | Strict layered DAG enforced by import-linter | Accepted | 2026-06-26 |
| [0002](0002-cli-sole-composer-subprocess-surfaces.md) | `alpha_cli` is the sole composer; surfaces subprocess the CLI | Accepted | 2026-06-26 |
| [0003](0003-t+1-fill-encoding.md) | t+1 fills via a dual-event feed encoding | Accepted | 2026-06-26 |
| [0004](0004-two-clock-corporate-actions.md) | Two-clock corporate actions (knowledge time vs ex-date) | Accepted | 2026-06-26 |
| [0005](0005-point-in-time-firewall.md) | A single point-in-time `as_of` firewall | Accepted | 2026-06-26 |
| [0006](0006-two-tier-null-model.md) | Two-tier null model (returns-level + full-engine) | Accepted | 2026-06-26 |
| [0007](0007-deterministic-run-id-and-seeds.md) | Content-addressed run id + independent child seeds | Accepted | 2026-06-26 |

## Conventions

- **Numbering:** zero-padded, sequential, never reused. A superseded ADR keeps its number and links forward to the one that replaces it.
- **Status:** one of `Proposed` · `Accepted` · `Superseded`. All current records are `Accepted` — they document decisions already live in `main`.
- **Template:** Status/Date/Deciders header → `Context` → `Decision` → `Options Considered` (each option scored on a `| Dimension | Assessment |` table over Complexity / Cost / Correctness-risk / Fit) → `Trade-off Analysis` → `Consequences` (easier / harder / revisit). Every record cites exact `file:symbol` anchors so it can be checked against the code.
- **Deciders:** the AI agents that build and operate the platform (per [`CLAUDE.md`](../../CLAUDE.md)); there is no separate human sign-off step.

## Candidate future ADRs

Decisions that are real but currently documented inline in [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §5 and [`CLAUDE.md`](../../CLAUDE.md) rather than as standalone records — promote to an ADR here if deeper rationale is later wanted:

- **Polars as the default dataframe** (pandas/`quantstats_lumi` confined to the tear-sheet rendering edge).
- **Fat-tailed null generators** (`student_t` / `garch`) as selectable alternatives to the block-bootstrap null.
