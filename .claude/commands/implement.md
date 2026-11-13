---
description: Own the approved plan through focused TDD, independent review and authorized delivery
argument-hint: [plan doc path, defaults to the newest in docs/work/]
---

Implement the approved plan: $ARGUMENTS

Use the task's approved plan. If no path was given, identify the plan that matches
the task from `docs/work/`; recency alone does not establish scope.
State which plan you are executing before touching code. Existing authorization
covers routine implementation and necessary fixes; ask only for missing scope or authority.

Goal contract for this session (state it up front, verify it at the end):
"every slice `done` AND `gate.py check` green AND a draft pull request open
with CI green AND independent review complete". Do not claim completion until
each part is re-checked, not remembered from the transcript.

0. Run `uv run python scripts/gate.py plan-check <plan doc>`. If it fails,
   STOP: the plan lacks assumptions / alternatives / pre-mortem / slice verify
   fields — go back to `/plan-feature`. Never start without a passing check.

Per slice, in order:
1. Write the slice's failing test first (from the plan's test plan); run it and
   show it failing for the expected reason (`FAILED … AssertionError`, not an
   import error).
2. Write the minimal code to go green; run the slice's `verify` command and
   compare against its `expected`.
3. Self-review pass (Karpathy §2/§3 — answer each in one line):
   - Would a senior engineer call this overcomplicated? What could be deleted?
   - Does every changed line trace to this slice? Anything "improved" nearby?
   - Which assumption from the plan did this slice rely on, and is it still
     verified?
   - What would `independent-reviewer` / `red-team-code` flag (a failing
     input, a look-ahead, a NaN, a seed)? Add that test now if it is cheap.
4. Run focused checks that cover the slice, including platform tests when relevant,
   then `uv run python scripts/gate.py check`. Commit each verified slice; small
   commits are fine. Follow the canonical feature skill.
5. Update the slice's status (`pending` → `in_progress` → `done`) against its
   stated acceptance criteria. Report blocked/deviated work honestly and continue
   independent work. A locally verified slice is not aggregate acceptance.

Own the task through QA, necessary fixes, independent review findings and documentation
upkeep. In the same candidate, update the one document that owns the fact (see the table in CONTEXT.md); never copy a fact into a second file;
use the routing files and generated indexes rather than another module inventory.
Keep the plan's `**Delivery state:**` line true; archive it when Completed
(`docs/reference/invariants/documentation.md`).
Do not hand implementation defects back to the user as planning questions.

Push the branch and open a **draft** pull request; CI is the merge gate. Before
marking it ready, obtain the independent `/review-gate` APPROVE for risk-tier and
protected paths and `/verify-quant` for quant paths, and post their reports on the
pull request. The reviewer receives the diff, not the author's reasoning. Fix BLOCK
findings and re-review; never self-approve. Preserve failed-run evidence before
retries ([development loop](../../docs/operations/development-loop.md)).

Continue through delivery within existing authorization. If publication or a
private-suite exception is missing, prepare the exact qualified payload, report the
specific blocker and retain ownership of the remaining action. Do not infer authority.

Review `git diff --stat` against the plan's declared `files[]`. Explain any scope
adjustment; preserve unrelated owner edits.

Never skip a required failing test or claim acceptance from focused feedback. A check you could
not run is reported as `UNVERIFIED:` — never "should work".
