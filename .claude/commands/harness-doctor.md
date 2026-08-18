---
description: Verify the Claude Code harness wiring itself
---

Run `python3 scripts/gate.py doctor`.

Report every check verbatim. If any check fails, diagnose and fix the wiring
(settings.json hook block, missing scripts, statusline, state dir, stub↔canonical
sync) — remember `.claude/settings.json` and `.claude/skills/**` are protected
control plane, so arm `uv run python scripts/gate.py ack --reason "..."` before
editing them. Re-run doctor until green.
