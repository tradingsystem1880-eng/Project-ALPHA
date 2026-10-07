# Project ALPHA agent instructions

Read [CLAUDE.md](CLAUDE.md) before repository work; it is the authoritative operating manual.
Use current facts and evidence. Read applicable `.claude/rules/` and required skills. Keep domain
authority separate from engineering checks; second-opinion bridge output is advisory.

Canonical quality gate: `uv run python scripts/gate.py full`. Update the manual and current-state
documentation when operating behavior changes. Preserve user work and report unverified results
honestly. See [the active plan](docs/superpowers/plans/2026-09-16-agent-neutral-reproducible-research.md)
for the delivered agent-neutral transition.
