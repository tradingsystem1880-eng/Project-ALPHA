# Archived feature plans

This folder holds feature plans whose work is finished: plans with
`**Delivery state:** Completed` or `**Delivery state:** Superseded by <path>`. Each plan lives in
the month folder taken from its filename date, for example `2026-10/2026-10-26-qlib-tabular-wave1.md`.
Archived plans are historical records: their text and JSON front blocks are kept as written, so
paths inside an archived front block may still name the plan's original flat location.

The flat folder [`docs/superpowers/plans/`](../) holds only live work: plans that are
`Implemented – qualification pending`, `In progress`, `Blocked` or `Planned`, plus the pinned
exceptions below, so a finished plan left there would misreport what is open. The [roadmap index](../../../roadmap/README.md) lists the live plans and the archive counts
per month.

## Lifecycle

1. A wanted feature without a plan is a backlog item in [`docs/roadmap/backlog/`](../../../roadmap/backlog/).
2. When it is planned, `/plan-feature` writes `docs/superpowers/plans/YYYY-MM-DD-<slug>.md` with a
   `FeaturePlan` JSON block and a `**Delivery state:**` line directly under the title.
3. When the work is merged (or the plan is superseded), set the state line to `Completed — <evidence>`
   or `Superseded by <relative path>`, then `git mv` the plan into `archive/YYYY-MM/`, fix links to it,
   and regenerate the roadmap index (`uv run python scripts/roadmap_index.py`).

## Pinned exceptions (finished, but kept in the flat folder)

These plans are referenced by path from files that must not be edited here, so moving them would
break a link or captured evidence. They keep their true state line; `tests/unit/test_plan_schema.py`
allows exactly this list.

| Plan | State | Why it stays in the flat folder |
| --- | --- | --- |
| [2026-09-11-edge-first-phase-c-screening-lane.md](../2026-09-11-edge-first-phase-c-screening-lane.md) | Superseded | Named in `packages/alpha-research/src/alpha_research/panel.py` docstrings. Every byte of the `alpha_research` tree feeds the research `code` identity hash (`research_cmds._implementation_hashes`) that owner-approved research contracts are checked against, so the path cannot be rewritten there. |
| [2026-09-16-agent-neutral-reproducible-research.md](../2026-09-16-agent-neutral-reproducible-research.md) | Completed | Linked from `AGENTS.md`, which is at its byte cap. |
| [2026-09-17-cancellation-and-research-walkthrough.md](../2026-09-17-cancellation-and-research-walkthrough.md) | Completed | Named in `alpha_research/panel.py`, for the same identity-hash reason. |
| [2026-09-30-edge-workspace.md](../2026-09-30-edge-workspace.md) | Completed | Linked from `CLAUDE.md`, which is at its byte cap. |
| [2026-09-30-research-workflow-completion.md](../2026-09-30-research-workflow-completion.md) | Completed | Path is embedded in captured evaluation evidence (`tools/alpha-eval/results/workflow-v2-20260930/verification/implementation-review.json`). |
| [2026-10-26-native-rule-authority.md](../2026-10-26-native-rule-authority.md) | Completed | Linked from `CLAUDE.md`, which is at its byte cap. |
| [2026-10-31-clean-rdagent-bootstrap.md](../2026-10-31-clean-rdagent-bootstrap.md) | Completed | Linked from the root `README.md`. |

Two further plans are referenced the same way but are live, so they would stay in the flat folder
anyway: `2026-10-31-packet3-daily-rule.md` (linked from `CLAUDE.md` and `README.md`) and
`2026-11-08-c04-risk-anchor-disclosure.md` (path embedded in
`apps/alpha-web/frontend/e2e/fixtures/riskMetricBasis.provenance.json` and written by
`scripts/capture_c04_risk_basis_fixture.py`). When either completes it must stay in the flat folder
and join the table above.
