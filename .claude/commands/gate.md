---
description: Run the gate (full tier by default; `fast` = ruff, format, imports, mypy) and stamp on success
argument-hint: [full | fast]
---

Tier is `$ARGUMENTS` if given, else `full`. Run `uv run python scripts/gate.py <tier>`.
`full` mirrors CI (10-minute budget) and is required to commit; `fast` satisfies the Stop guard only.

Report every step's PASS/FAIL verbatim. On failure: show the failing output exactly as printed,
diagnose, fix, and re-run — never soften, summarize away, or work around a failing step. On
success confirm the stamp with `uv run python scripts/gate.py check --tier <tier>`.
