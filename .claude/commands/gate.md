---
description: Run the fast local check (lint, imports, types, mapped tests); CI on the pull request is the merge gate
argument-hint: [--all] [--base REF]
---

Run `uv run python scripts/gate.py check $ARGUMENTS` (`--all` runs the whole fast test tier).
To reproduce one CI job, run `uv run python scripts/gate.py component NAME` instead.

Report every step's PASS/FAIL verbatim. On failure: show the failing output exactly as printed,
diagnose, fix, and re-run — never soften, summarize away, or work around a failing step. A green
local check is feedback, not acceptance: CI on the pull request decides.
