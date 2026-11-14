## What changed for you

- A new check stops any product source file from growing past 1,500 lines and any function past
  150 lines. Tests are not measured.
- Today's 10 oversized files and 98 oversized functions are written down at their exact size.
  They may not grow. When one shrinks the record must be lowered to match, and when it drops under
  the limit its line must be removed, so the list can only get shorter. Adding a line or raising a
  number is refused by comparison with main.
- Nothing changes in the app. No research approval is touched.

Oversized files today:

| File | Lines |
|---|---|
| `apps/alpha-cli/src/alpha_cli/control_store.py` | 14,025 |
| `apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py` | 4,707 |
| `apps/alpha-cli/src/alpha_cli/research_cmds.py` | 4,250 |
| `apps/alpha-web/src/alpha_web/api/models.py` | 3,407 |
| `apps/alpha-cli/src/alpha_cli/figures/_builders.py` | 2,664 |
| `apps/alpha-cli/src/alpha_cli/_suite.py` | 2,275 |
| `apps/alpha-web/src/alpha_web/_ml.py` | 1,763 |
| `workers/qlib/src/alpha_qlib_worker/real.py` | 1,578 |
| `scripts/handoff.py` | 1,576 |
| `apps/alpha-cli/src/alpha_cli/research_gate_packet.py` | 1,568 |

Longest functions (all 98 are in `.claude/code-size-baseline.json`): `_suite.py::build_suite_plan`
889 lines, Qlib `real.py::_fold_model` 394, `tabular_adapters.py::fit_tabular` 329,
`research_intake.py::draft_exploration_contract` 325, `_artifacts.py::write_execution_trace` 325.
77 of the 98 are in `apps/alpha-cli`, 18 of them in `control_store.py`.

## How to see it

Nothing visible: internal. The rule is in `docs/reference/invariants/engineering.md` (Code size);
the list is `.claude/code-size-baseline.json`.

## Checks run

- The new test: 17 passed; deliberately broken baselines fail with messages naming the fix.
- `uv run python scripts/gate.py check --all`: all checks passed.
- Smoke before and after: 8 passed, 4 skipped (local RD-Agent runtime only) both times.
- Not run here: CI (this pull request).

## Who built and who reviewed

- Test built by Codex (`gpt-6.1-sol`, effort medium, small class, from a brief through
  `scripts/handoff.py`): 2m58s, no fix round, 133,544 input tokens (118,400 cached), 2,965 output.
  No fallback. Baseline (generated with Claude's own script from the same rules) and documents by
  Claude (Opus 5.5); Claude also changed the test after review.
- Reviewed by Claude Opus (`reviewer`): approve, three low findings, all fixed. Codex
  (`gpt-6-astra`): three medium findings over three rounds (baseline could be raised by editing it;
  a git error passed as "no baseline yet"; NaN sizes), all fixed; fourth round clean. Details in
  `docs/work/archive/2026-11/2026-11-14-code-size-limits/04-verify.md`.

## The one document updated

`docs/reference/invariants/engineering.md` (Code size); the check's row in `docs/reference/checks.md`.

## What I am unsure about

- Renaming an oversized function counts as a new offender, so a rename must come with a split.
  That is deliberate.
- The comparison with main needs `origin/main` in the checkout (CI fetches full history); locally
  a missing ref fails with "run `git fetch origin`".
- Which approvals this invalidates: none. No product or approval-bound file changed.

## Protected files touched

- `.claude/code-size-baseline.json` (new; kept beside the other ratchet baselines, so a Codex
  builder cannot change it without declaring the protected tier).
