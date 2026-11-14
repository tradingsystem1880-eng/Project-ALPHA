# A size limit that only tightens

## What the owner wants

From the clean-up milestone "agent-sized code": "no mess, bloat or slop, and no file an agent
cannot hold in its head", starting with "a test ... that fails when a NEW Python source file
exceeds 1,500 lines or a NEW function exceeds 150 lines, and caps every existing offender at its
current size in a small recorded baseline that may only go down".

In one sentence: no product file or function may grow past the limits, today's oversized ones may
not grow at all, and the list of them can only get shorter.

## What done looks like

- A new oversized file or function fails the checks on its pull request, with a message saying
  what to do.
- Each of today's oversized files and functions is recorded at its exact size; growing fails, and
  shrinking fails until the record is lowered, so the record follows every improvement down.
- The list of today's offenders, with sizes, is in the pull request.

## How they will see it

Nothing visible in the app. On GitHub: the rule in `docs/reference/invariants/engineering.md`
(Code size) and the list in `.claude/code-size-baseline.json`.

## Out of scope

Shrinking any offender (later pull requests of the milestone). Tests are not measured.
