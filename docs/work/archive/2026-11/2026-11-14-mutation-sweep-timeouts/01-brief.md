# Make the weekly mutation sweep measure, not hang

## What the owner wants

The weekly mutation sweep (dispatched in full as run 43483950887 on `m4/ci-lean`, commit
`cb01d446`) passed 259 of 261 jobs. One fragment of `alpha_research/rendering.py` (283 mutants)
ran out of its 5,400-second budget with about half its mutants timing out, so the aggregate failed.
The job log said only "exit code 1"; the reason was inside the uploaded artifact. The preflight
log also showed tests failing inside the staged copy (a missing document and a missing script).

In one sentence: find out why those mutants time out, make the timeouts cheap or fewer without
hiding any, make a failing fragment say why in the job log, and answer whether the staged copy
silently drops tests that could kill mutants.

## What done looks like

- The root cause is measured, with numbers, on the module that failed.
- The fix keeps every mutant measured: no module excluded, no threshold lowered, no edit to the
  hash-bound `packages/alpha-research/src` bytes.
- A failing fragment prints its error and a bounded tail of its own logs before exiting non-zero.
- Tests that failed only because the staged copy lacked files now run there; any test still
  excluded is printed in the job log.
- One module can be run on GitHub's runners on its own, and that run proves the fix.

## How they will see it

The weekly sweep's job logs, and its numbers: fewer timeouts, honest survivors in their place.

## Out of scope

Product source of every package; mutation thresholds and baselines; the CLI `_suite.py` and
`research_cmds.py` (another stream).
