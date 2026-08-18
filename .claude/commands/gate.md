---
description: Run the full-tier gate (lint, format, imports, mypy, pytest+cov, openapi, wheels, smoke) and stamp on success
---

Run `uv run python scripts/gate.py full` (10-minute budget; it mirrors CI).

Report every step's PASS/FAIL verbatim. On failure: show the failing output
exactly as printed, diagnose, fix, and re-run — never soften, summarize away,
or work around a failing step. On success confirm the stamp is valid with
`uv run python scripts/gate.py check --tier full`.
