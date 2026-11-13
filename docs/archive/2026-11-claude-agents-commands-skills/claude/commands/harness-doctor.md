---
description: Verify the Claude Code harness wiring itself
---

Run `python3 scripts/gate.py doctor`.

Report every check verbatim. If any check fails, diagnose and fix the wiring
(settings.json hook block, missing scripts, statusline, state dir, stub↔canonical
sync). Protected control-plane changes go through a reviewed pull request with CI
green. Re-run doctor until green.
