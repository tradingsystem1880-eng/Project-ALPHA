## What changed for you

- The 3,407-line file holding every web API model is now a folder of 18 files (21 to 574 lines),
  one per area of the API: runs and charts, rules, scans and strategies, data sources, system,
  crypto data, projects and jobs, paper, workspaces, risk, research cases, research hub, research
  gates, figures, semantic reads, errors, plus a small shared base.
- Nothing changes in the app. The API contract file generated from the code is byte-for-byte the
  same before and after (sha256 `0fd82f04da49c2adf0ec207244c6b44b15023c1e324c7dae702ccde6e1c80726`
  both times), and every one of the 350 model definitions is the same text, only moved.
- The base model class existed three times with identical bodies; there is now one.
- The size list loses `models.py`: 9 oversized files remain.
- **No research or rule approval is invalidated.** No approval binds web code.

## How to see it

Nothing visible: internal. The folder is `apps/alpha-web/src/alpha_web/api/models/`; its
`__init__.py` says which file holds which area.

## Checks run

- OpenAPI freshness check: passes without regenerating; same hash before and after.
- AST comparison: 350 of 350 definitions identical.
- `gate.py check --all`: passed. Web, MCP and risk tests: 1,203 passed, 1 skipped.
- Smoke before and after: 8 passed, 4 skipped each time; no failure this time.
- Not run here: browser journeys (CI).

## Who built and who reviewed

- Codex (`gpt-6-astra`, effort high, hard class, through `scripts/handoff.py`): 7m36s, one round,
  no fix round, 915,561 input tokens (869,632 cached), 8,884 output. No fallback.
- Claude (Opus 5.5): the one-`StrictModel` change, baseline, rule and index edits, and one review fix.
- Reviewed by Claude Opus (`reviewer`): approve; two low findings, one fixed (the fixture capture
  script now also hashes the base module), one disclosed (below). Codex review: no findings, on a
  truncated view of the diff.

## The one document updated

`docs/reference/invariants/web-api.md` (where models live). The finished refactor file
`docs/roadmap/refactors/web-api-models-split.md` is removed; the roadmap index is regenerated.

## What I am unsure about

- The committed C04 fixture provenance (`riskMetricBasis.provenance.json`) still records a hash of
  the old single `models.py`. It describes the capture as it happened; I did not re-capture it.

## Protected files touched

`.claude/code-size-baseline.json` (the `models.py` entry removed).
