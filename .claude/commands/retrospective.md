---
description: Write a dated retrospective from the audit journal, session failures and the plan doc - what the harness caught, missed, and which rule to add
argument-hint: <slug> [--since ISO-timestamp] [plan doc path]
---

Write a retrospective for: $ARGUMENTS

Run this after a feature lands, or whenever `gate.py audit` shows ≥ 2 blocks /
overrides / acks for one piece of work. Evidence first, prose second:

1. Gather the record — do not rely on memory of the session:
   - `uv run python scripts/gate.py audit --json --since <ISO>` (blocks,
     overrides, acks, `over_eager_edit`, `stop_budget_exhausted`, codex calls);
   - the session state files under `.claude/state/session-*.json`
     (`failures[]`, `over_eager[]`, `stop_blocks_used`);
   - the plan doc's front block (which slices are `done`, which assumptions
     turned out wrong, which pre-mortem items materialised);
   - `git log --oneline` for the range.
2. Write `docs/operations/retrospectives/YYYY-MM-DD-<slug>.md` with exactly
   these headings (the session brief reads `## Watch-outs` from the newest file):
   - `## What the harness caught` — each block/warn with the audit event and
     whether it was a true positive;
   - `## What the harness missed` — defects, drift or unverified claims found
     later that no hook/test/gate flagged;
   - `## Assumptions and pre-mortem, revisited` — per plan item: held / broke;
   - `## Watch-outs` — ≤ 6 one-line, actionable reminders for the next session;
   - `## Rule to add` — for each miss, the concrete change (a `.claude/rules/*.md`
     line, a test, a hook check) or "none: accepted limitation, because …".
3. Do NOT edit `.claude/rules/**`, hooks or settings from this command; propose
   the change and let the owner (or a separate acked edit) land it.
4. Print the file path and the Watch-outs list.
