---
description: Write a dated retrospective from the audit journal, session failures and the plan doc - what the harness caught, missed, and which rule to add
argument-hint: <slug> [--since ISO-timestamp] [plan doc path]
---

Write a retrospective for: $ARGUMENTS

Run this after a feature lands, or whenever `gate.py audit` shows ≥ 2 blocks /
overrides / acks for one piece of work.

Dispatch the `retrospective` subagent with the arguments above (slug, optional
`--since` timestamp, optional plan doc path); it gathers the evidence and
drafts the body per `.claude/agents/retrospective.md`. Write the result to
`docs/operations/retrospectives/YYYY-MM-DD-<slug>.md`, then print the file
path and the Watch-outs list.
