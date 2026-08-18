---
description: Execute the current plan doc slice-by-slice with TDD
argument-hint: [plan doc path, defaults to the newest in docs/superpowers/plans/]
---

Implement the approved plan: $ARGUMENTS

If no plan path was given, use the newest file in `docs/superpowers/plans/`.
Confirm which plan you are executing before touching code.

Per slice, in order:
1. Write the slice's failing test first (from the plan's test plan); run it and
   show it failing for the expected reason.
2. Write the minimal code to go green; run the test.
3. Run `uv run python scripts/gate.py fast`; fix anything it reports.
4. Commit the slice with a conventional message referencing the plan doc.
5. Report honest status: slice done / blocked / deviated (and why) before
   moving on. Update the plan doc's status as you go.

Never batch multiple slices into one commit, never skip a failing test, and
never claim a slice done without the gate output proving it.
