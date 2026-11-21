# Common rules for the builds briefed on 2026-11-21

Read `CLAUDE.md`, root `CONTEXT.md` and the workspace `CONTEXT.md` of each area you touch (matching rows only) before coding.

- The owner is one retail swing trader (long holds, small size, never high-frequency), not a coder, a visual learner. Results are READINGS
  (numbers in context): no pass/fail verdicts, no letter grades, no advice, never a promise of profit. Plain words; standard trading terms.
- No human watches a cloud build: never ask or wait; decide, and write each decision in `report.md` in your task folder.
- You have no access to the owner's data or keys. Synthetic fixtures only. Never add secrets.
- Tests first; show fail-first evidence in the report. Typed tests; floats with `pytest.approx(rel=1e-9, abs=1e-12)`.
- A missing value is never shown or used as a real value (the most common defect found in review): every null carries a reason, never
  makes a condition true, never counts as zero.
- Research reads are cut at the held-back boundary through `alpha_cli.spine.reserve` (`hold`, `hold_many`, `CUTOFF`). The guard
  `tests/unit/test_research_reads_are_cut.py` must pass unweakened. Forward-use code (follow, today, market view) stays on its own named
  paths; `tests/unit/test_follow_separation.py` must pass unweakened.
- Protected paths, not to be edited: `packages/alpha-research/src`, `packages/alpha-validation/src`, `workers/**`, `apps/alpha-mcp/**`,
  `tests/bias_guards`, `tests/oracles`, `tests/unit/test_claude_harness_*.py`, `.semgrep/`, `.github/`, `.claude/`, `.agents/`, top-level
  `scripts/`, `uv.lock`, `CLAUDE.md`, `AGENTS.md`. If the work needs one, stop that part and say so in the report.
- No `noqa`, `type: ignore`, `nosemgrep`, `eslint-disable`, `vars(`, `__doc__`, `inspect`, `.__dict__`. Functions at most 150 lines; new
  modules at most 300 lines. No new dependency. If `tests/unit/test_code_size.py` asks to LOWER a baseline entry, do not pad and do not
  edit `.claude/`: report the numbers.
- Documents: fix the TEXT of the owning page when your change makes it wrong (reference pages at most 200 lines, sections at most 4 KB,
  lines at most 160 characters; tool cards at most 40 lines). Do NOT run `fs.py verify` and do not edit `docs/verified-reasons.txt`: a stale
  document is listed, not blocked. Regenerate `docs/reference/commands.md` (`uv run python scripts/commands_reference.py`), `STATUS.md`
  (`uv run python scripts/status.py`) and the OpenAPI file plus `apps/alpha-web/frontend/src/api/generated.ts` only when they change.
- Set-up, if tools are missing: read, then run `bash scripts/cloud_setup.sh` (or `scripts/setup.sh`).
- Checks before each push: the tests of the area; `uv run lint-imports`; `uv run python scripts/gate.py check --base origin/main`.
- Land as a pull request from a branch named in your brief. Open it as a DRAFT while you build: a draft runs only the quick `static` job
  and its `ci-ok` fails on purpose (that is expected). When the work is complete and your local checks pass, mark it ready
  (`gh pr ready <number>`): that starts the full run. Then wait for the required check `ci-ok` (poll
  `gh api repos/tradingsystem1880-eng/Project-ALPHA/commits/<sha>/check-runs` every 90 s; `gh pr checks` does not work here) and fix what
  CI finds. Commits `type(scope): summary` ending with the exact line `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`; merge
  commits only (never amend, rebase, squash or force-push); commit and push early and often; the pull-request body uses the headings of
  `.github/pull_request_template.md`, ends with `🤖 Generated with [Claude Code](https://claude.com/claude-code)` and names no model.
  Do NOT merge: an independent review lands it. When main moves, merge it in (`git merge origin/main`).
- A deletion-only build: prove each deleted file is unreached before you delete it (grep for imports, for the command words, for
  `python -m` and subprocess calls, in `apps`, `packages`, `workers`, `tests`, `scripts`, `docs`); delete the tests that only test deleted
  code; never delete a named feature (Kronos, the Monte Carlos, patterns, lookalike, Setup Lab, RD-Agent, Qlib/ML, follow, the toolbox,
  propfirm). A deletion makes functions and files shorter or absent: `tests/unit/test_code_size.py` will ask to LOWER or REMOVE baseline
  entries in the protected `.claude/code-size-baseline.json`. Do not edit that file: list the exact entries in your report and leave only
  that one test red; the orchestrator lowers them. Report lines removed and lines added.
