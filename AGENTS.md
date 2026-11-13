# Project ALPHA agent instructions

Read [CLAUDE.md](CLAUDE.md), the authoritative manual, before work.
Use current evidence. Read applicable `.claude/rules/` and required skills. Separate domain
authority from engineering checks; second-opinion bridge output is advisory.

Local check: `uv run python scripts/gate.py check`; CI on the pull request is the merge gate
([development loop](docs/operations/development-loop.md)). On behavior changes, update the manual
and current-state docs. Preserve user work; report unverified results honestly.
