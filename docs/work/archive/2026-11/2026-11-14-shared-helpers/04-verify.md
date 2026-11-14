# Verify: one copy of each duplicated helper

## Commands run

- Measurement (scratch script, AST of every function body in 514 product files, names and
  docstrings aside): before, 32 groups of identical functions across files, 235 duplicated lines;
  after, 24 groups, 129 lines. Each remaining group is listed with its reason in `05-handoff.md`.
- Test-only public functions (a scratch scan of names referenced by tests and by no product code,
  pyproject, workflow or config): 14 before, 11 after.
- `uv run python scripts/gate.py check --all` on the final tree: all checks passed.
- The whole platform tier (`-m "platform and not network and not slow_oracle and not smoke"`,
  unit and integration): 5,104 passed, 88 skipped.
- `uv run python scripts/gate.py component eval`: lint, format, types and tests passed.
- `uv run lint-imports`: 13 contracts kept.
- Smoke: before (main at `733c4403` plus the size test only) 8 passed, 4 skipped. After, four runs:
  one run had 1 failure that the output I kept does not name (I printed only the last line), and
  the next three runs were each 8 passed, 4 skipped. Treated as a flaky check, not a regression;
  see `## Not run`.

## End-to-end check

Smoke runs the installed `alpha` and `alpha-web` programs; the platform tier covers the CLI
research, web, MCP, paper and suite paths that call the moved helpers.

## Not run

- UNVERIFIED: which smoke test failed once; three later runs passed.
- CI: runs on the pull request.

## Review findings

- Built by Codex (`gpt-6-astra`, high, hard class): 20m17s, 3 rounds (2 fix), 6,502,592 input tokens
  (6,238,848 cached), 50,528 output. Its own gate failed all three rounds on one mypy error in a
  file outside the brief (`local_pdf_cmds.py` imported `research_cmds._emit`); Claude fixed it by
  hand, shortened one help text so two oversized functions did not grow, and made the harness
  edits (guarded files a brief cannot declare).
- `reviewer` (Claude Opus): approve. One low finding, fixed: `packages/alpha-core/CONTEXT.md` did
  not mention `atomic.py`.
- Codex review (`gpt-6-astra`, medium, `handoff.py review`): no findings.
