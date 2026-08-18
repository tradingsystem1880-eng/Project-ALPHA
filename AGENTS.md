# Project ALPHA agent instructions

Read [`CLAUDE.md`](CLAUDE.md) before changing this repository. It is the single authoritative
operating manual for architecture, invariants, commands, package ownership, and current phase
state.

Do not duplicate those instructions here. If behavior changes, update `CLAUDE.md` and the relevant
current-state documentation in the same change.

Canonical agent-agnostic quality gate: `uv run python scripts/gate.py full` (mirrors CI, stamps the
tree). Claude Code sessions run under a mechanical hook harness — see `docs/operations/claude-code-harness.md`.
