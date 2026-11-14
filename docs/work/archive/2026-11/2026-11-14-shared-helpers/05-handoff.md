## What changed for you

- Copied helper code was measured, not guessed: 32 groups of identical functions across files
  (235 lines) before, 24 groups (129 lines) after. Product code is 142 lines shorter.
- Now one copy each: atomic file writing (moved to the core package, used by the CLI and the web
  app), command-line JSON output and option parsing, D1/D2 evidence file reading and writing, the
  "flat resample scores 0" bootstrap Sharpe, and two study id checks.
- Deleted because only tests called them: a run-id wrapper, an unused evaluation statistic, an
  unused ADR-mention parser and an unused constant in the hand-off tool.
- The hand-off tool now refuses a builder change to the approval digest rules
  (`_structural_digest.py`) unless the plan declares the quant tier, as ADR-0045 recommended.
- An idea you capture or propose in the Workstation is now recorded as created by `workstation`.
  Before, it was recorded as `codex`, which in ALPHA names the AI research-assistant role. Agents
  calling the command line or MCP still record `codex`, which is right for them; the option's
  help now says what `codex` means.
- One message changes: a D1 or D2 evidence file that contains NaN or infinity is still refused,
  now with "<file> must contain finite JSON values".
- **No research or rule approval is invalidated.** No approval-bound file changed. Run ids of new
  runs change, as with any change to command-line code.

Copies left in place, and why:

| Copies | Why they stay |
|---|---|
| Atomic writer in `alpha_data` | the data stream is working in that package; a one-line import change later |
| Atomic writer in `alpha_validation`; validators shared by `alpha_research` market state and `alpha_validation` forecast calibration; `alpha_research` finite-array check | quant tier and research approvals bind these files: an edit means re-approving |
| `_process_group_exists` (suite, lease), `_sha`/`_digest` (two daily rule files), artifact writing in `research_runtime` | one copy sits in an approval-bound file |
| ML contract helpers in `alpha_cli` and the Qlib worker; fixture digests in `alpha_cli` and the RD-Agent worker; two RD-Agent fixture files | workers are isolated projects that import nothing from ALPHA, so each side checks the contract itself |
| JSON projection checks in the web app and the MCP server | neither may import the other |
| About 12 one-line canonical-JSON wrappers and 73 inline calls | four different encodings, each defining a hash, most in bound files; one helper would tie unrelated hash formats together |
| Seven pairs of 3-6 line helpers inside one package or across a layer | too small to earn a cross-module import |

Functions only tests call that stay: four in approval-bound daily rule files (deleting them would
invalidate every daily rule approval), four in `alpha_data` (the data stream's area), and three
that tests use by design (a cache reset hook, the ADR index check, the test-ownership check).

## How to see it

Nothing visible except the Workstation label above. Details:
`docs/work/archive/2026-11/2026-11-14-shared-helpers/`.

## Checks run

- `gate.py check --all`: passed. Whole platform tier: 5,104 passed, 88 skipped. Eval component:
  passed. Import contracts: 13 kept.
- Smoke before 8 passed, 4 skipped. After: one run had a single failure I did not capture, then
  three runs passed 8, skipped 4. Not run: CI (this pull request).

## Who built and who reviewed

- Codex (`gpt-6-astra`, high, hard class, through `scripts/handoff.py`): 20m17s, 3 rounds (2 fix),
  6,502,592 input tokens (6,238,848 cached), 50,528 output, no fallback. Its gate failed on one
  mypy error in a file outside its brief; Claude (Opus 5.5) fixed it, kept two oversized functions
  from growing, and made the harness and document edits.
- Reviewed by Claude Opus (`reviewer`): approve, one low finding (core workspace file did not name
  `atomic.py`), fixed. Codex review (`gpt-6-astra`): no findings.

## The one document updated

`docs/reference/model-routing.md` (guarded paths); also `docs/reference/invariants/engineering.md`,
`docs/reference/invariants/cli-runs.md` and `packages/alpha-core/CONTEXT.md` for facts that moved.

## What I am unsure about

- The one smoke failure I could not name (three clean runs since).
- Whether the owner wants a different label than `workstation` for Workstation captures.

## Protected files touched

`scripts/handoff.py`, `scripts/harness_awareness.py`, `tests/unit/test_claude_harness_handoff.py`,
`tests/unit/test_claude_harness_gate.py`, `.claude/code-size-baseline.json` (one entry lowered).
