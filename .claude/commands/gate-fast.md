---
description: Run the fast-tier gate (ruff, format, import contracts, mypy) and stamp on success
---

Run `uv run python scripts/gate.py fast`.

Report every step's PASS/FAIL verbatim; fix failures and re-run. The fast stamp
satisfies the Stop guard; commits still require the full tier (`/gate`).
