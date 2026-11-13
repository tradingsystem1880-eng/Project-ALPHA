# Delivery-task system (durable task ownership and two-model handoff)

**Status:** Scoped
**Rough size:** L

## Problem / why

Each authorized task should keep one target, one responsible owner, the next action, the evidence
needed to finish and the next review point, recover safely from a stopped coordinator, and let
Claude and Codex start from the same evidence. A working pilot exists only outside this
repository, as three sealed local packages: the first pilot (2026-11-10: a `scripts/delivery_task.py`
CLI with task ownership, revision checks, focused-run receipts and model evidence records; 26 tests),
a recovery candidate (2026-11-10: durable execution ownership across coordinator crashes, bounded
per-incident retries; 67 tests) and the newest model-evidence correction (2026-11-11: current Codex
evidence required before any focused run; 77 tests passed, 8-call CLI demonstration). None is
integrated, reviewed afresh by Claude, or run through the canonical gate. A successor design (the
"task operating system" build map, milestones M0–M5) extends the pilot inside the existing Software
Team roles and the file system's orientation and search; its milestone M0 (a verified, permitted Codex execution path) is
blocked.

## What "done" looks like

The newest package is reconciled with the owner-controlled source, reviewed by both models and
passes the unchanged full gate; then the successor milestones land in order, starting with safe
recovery (M1) and honest retries/status (M2), without a second project index or agent swarm.

## Dependencies

M0: a permitted Codex execution path. Owner-controlled integration of the pilot packages;
`scripts/` harness changes are protected.

## Sources

- Local, not in the repository: the newest delivery model-evidence package (2026-11-11), its
  recovery predecessor and the first delivery-task pilot (both 2026-11-10), and the successor
  build map in the portable 2026-11-10 project copy.
- [Software Team map](../../context/software-team.md)
