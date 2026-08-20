---
description: Execute the current plan doc slice-by-slice with TDD, a self-review pass per slice, and honest status
argument-hint: [plan doc path, defaults to the newest in docs/superpowers/plans/]
---

Implement the approved plan: $ARGUMENTS

If no plan path was given, use the newest file in `docs/superpowers/plans/`.
Confirm which plan you are executing before touching code.

Goal contract for this session (state it up front, verify it at the end):
"every slice `done` AND `gate.py full` stamp valid AND the Stop obligations
list is empty". Do not claim completion until each part is re-checked on the
tree, not remembered from the transcript.

0. Run `uv run python scripts/gate.py plan-check <plan doc>`. If it fails,
   STOP: the plan lacks assumptions / alternatives / pre-mortem / slice verify
   fields — go back to `/plan-feature`. Never start without a passing check.

Per slice, in order:
1. Write the slice's failing test first (from the plan's test plan); run it and
   show it failing for the expected reason (`FAILED … AssertionError`, not an
   import error).
2. Write the minimal code to go green; run the slice's `verify` command and
   compare against its `expected`.
3. Self-review pass before the gate (Karpathy §2/§3 — answer each in one line):
   - Would a senior engineer call this overcomplicated? What could be deleted?
   - Does every changed line trace to this slice? Anything "improved" nearby?
   - Which assumption from the plan did this slice rely on, and is it still
     verified?
   - What would `independent-reviewer` / `red-team-code` flag (a failing
     input, a look-ahead, a NaN, a seed)? Add that test now if it is cheap.
4. Run `uv run python scripts/gate.py fast`; fix anything it reports.
5. Commit the slice with a conventional message referencing the plan doc.
6. Report honest status: slice done / blocked / deviated (and why) before
   moving on. Update the slice's `status` in the plan's front block
   (`pending` → `in_progress` → `done`) as you go.

If the Stop brief shows a `SCOPE WARNING` (an edit outside the plan's declared
`files[]`), either add the path to the plan with a reason or revert it — never
leave it unexplained.

Never batch multiple slices into one commit, never skip a failing test, and
never claim a slice done without the gate output proving it. A check you could
not run is reported as `UNVERIFIED:` — never "should work".
