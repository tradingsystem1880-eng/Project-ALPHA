# Verify: the web API models as a package

## Commands run

- Before (main at `89c7706c`): `uv run python scripts/generate_web_openapi.py --check` passed; the
  freshly generated document and the committed `apps/alpha-web/frontend/openapi.json` both hash to
  sha256 `0fd82f04da49c2adf0ec207244c6b44b15023c1e324c7dae702ccde6e1c80726`.
- After (this branch, including the `StrictModel` change): the check passes without regenerating,
  and the freshly generated document hashes to the same `0fd82f04...0726`. `generated.ts` is
  untouched (its freshness is checked against `openapi.json` in CI's frontend job).
- AST comparison: all 350 top-level definitions of the old file appear in the package with
  byte-identical source text; none missing, none added. Every former name is importable from
  `alpha_web.api.models` except the standard-library and pydantic names the old module imported
  (nothing imports those from it).
- `uv run python scripts/check_openapi_operations.py`: passed. `uv run lint-imports`: 13 kept.
  `uv run mypy apps/alpha-web/src`: no issues.
- `uv run python scripts/gate.py check --all`: all checks passed.
- Web, MCP, C04 and risk tests across `tests/unit` and `tests/integration` (`-k "web or mcp or c04
  or v3 or risk or openapi or ml"`): 1,203 passed, 1 skipped.
- Smoke before: 8 passed, 4 skipped. After: 8 passed, 4 skipped (full output kept; no failure).

## End-to-end check

Smoke starts the installed `alpha-web` program; the web integration tests drive every API route
through FastAPI's test client against the package.

## Not run

- Browser journeys and the frontend job: CI (the API document is unchanged, so no frontend change).
- The C04 fixture was not re-captured; its committed provenance records the earlier capture
  against the single-file `models.py` (still accurate as history; no test reads those hashes).

## Review findings

- Built by Codex (`gpt-6-astra`, high, brief raised to hard): 7m36s, 1 round, no fix round,
  915,561 input tokens (869,632 cached), 8,884 output. Claude added the `StrictModel` change, the
  baseline, rule and index edits.
- `reviewer` (Claude Opus): approve; verified all seven claims independently (including a wheel
  build that contains the package). Two low findings: the capture script should also hash
  `models/_base.py` (fixed); the committed fixture provenance names the old file (disclosed above,
  not re-captured).
- Codex review (`gpt-6-astra`): no findings, but it saw only part of the 3,400-line diff
  (truncated), so the Opus review is the full one.
