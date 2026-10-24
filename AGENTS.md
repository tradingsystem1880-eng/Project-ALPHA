# Project ALPHA agent instructions

Read [CLAUDE.md](CLAUDE.md) before work; it is the authoritative operating manual.
Use current facts/evidence. Read applicable `.claude/rules/` and required skills. Separate domain
authority from engineering checks; second-opinion bridge output is advisory.

Canonical quality gate: `uv run python scripts/gate.py full`. On behavior changes,
update the manual and current-state docs. Preserve user work; report unverified results honestly.
See the [delivery record](docs/superpowers/plans/2026-09-16-agent-neutral-reproducible-research.md) for the completed agent-neutral transition.
