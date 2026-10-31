# Project ALPHA agent instructions

Read [CLAUDE.md](CLAUDE.md), the authoritative manual, before work.
Use current evidence. Read applicable `.claude/rules/` and required skills. Separate domain
authority from engineering checks; second-opinion bridge output is advisory.

Canonical quality gate: `uv run python scripts/gate.py full`. On behavior changes,
update the manual and current-state docs. Preserve user work; report unverified results honestly.
[Transition](docs/superpowers/plans/2026-09-16-agent-neutral-reproducible-research.md).
Before delivery, review/update README and record clear no-change decisions.
