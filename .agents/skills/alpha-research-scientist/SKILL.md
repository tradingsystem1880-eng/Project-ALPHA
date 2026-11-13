---
name: alpha-research-scientist
description: Turn a raw market observation or new trading idea in Project ALPHA into a bounded, falsifiable, source-aware research case before strategy implementation. Use for thesis drafting, literature and data feasibility, protocol design, event-study planning, confounder and overfitting controls, research status, and decision-oriented explanation.
---

# ALPHA Research Scientist

Run the governed research workflow. Never jump from an observation to strategy code or a
backtest. This skill holds no rules of its own; it routes you to the files that do.

1. Start at [`research/CONTEXT.md`](../../../research/CONTEXT.md). Find the case's stage with
   `uv run alpha research status <case> --json` and open that stage's `CONTEXT.md`.
2. Follow the stage: read exactly what its Read first table names, run its commands, leave its
   outputs (under the data directory, never in git), and stop at its checkpoint.
3. The working method (phases, questions, triage limits, what a contract freezes, stop rules,
   reporting and charts) is [the research method](../../../docs/reference/research-method.md);
   the per-step method is the protocol file the stage names in `../alpha-research-protocols/`.
4. Reviewing a research artefact: [adversarial research review](../../../docs/reference/research-review.md)
   (stage 05).
5. Authority: only the owner approves, rejects, decides, revises, authorises D2 or reveals a
   holdout ([research integrity § Owner authority](../../../docs/reference/invariants/research-integrity.md#owner-authority)).
   You never run those commands, even with an `--actor` string. When one is needed, stop with
   `NEEDS OWNER` and the smallest exact decision requested.
