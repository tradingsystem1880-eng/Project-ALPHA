---
owner: research pipeline
sources:
  - apps/alpha-cli/src/alpha_cli/research_cmds.py
  - apps/alpha-cli/src/alpha_cli/_research_cmd_parts.py
  - apps/alpha-cli/src/alpha_cli/research_runtime.py
  - apps/alpha-cli/src/alpha_cli/research_d1.py
  - apps/alpha-cli/src/alpha_cli/research_analysis_plan.py
verified: 9c40aa259c97
---

# Stage 03 — screen: D0 pilot, then D1 discovery

## Purpose

Prove the frozen evaluator on synthetic data (D0, no market claim), then run the approved
analysis plan on the discovery share of the registered data (D1, exploratory). Nothing outside
the approved contract runs, and every attempt is kept.

## Inputs

- A case in phase `pilot` (the owner approved its exploration contract in stage 02).

## Read first

| Read | Section | When |
|---|---|---|
| [research method](../../../docs/reference/research-method.md) | Research inside the frozen family | always |
| [exploratory analysis protocol](../../../.agents/skills/alpha-research-protocols/exploratory-analysis.md) | Method | reading D1 output |
| [event-study protocol](../../../.agents/skills/alpha-research-protocols/event-study-design.md) | Method | reading D1 output |
| [command line research](../../../docs/reference/invariants/cli-research.md) | Launch budgets and recovery | a run fails, pauses or is interrupted |
| [research integrity](../../../docs/reference/invariants/research-integrity.md) | Statistical evidence | always |

## Process

1. Check the case: `uv run alpha research status <case> --json` must show phase `pilot` and
   `execution_state` `idle`, with launches remaining.
2. Run the pilot: `uv run alpha research run pilot <case> --json`. It runs only the registered
   double-bottom D0 operator, at most three launches per contract, and a crash uses a launch.
3. Read the result: `status` again. A completed D0 moves to `deep_research` when the contract has
   an analysis plan; otherwise straight to `research_decision` (go to stage 05).
4. Run discovery: `uv run alpha research run deep <case> --json`. It needs a registered dataset
   in the contract and reads only the D1 share; output is watermarked EXPLORATORY.
5. Control a running job only with `uv run alpha research pause <case> --reason ...`,
   `resume <case>` or `cancel <case> --reason ...`. Never rerun with changed settings: a changed
   threshold, outcome, detector, universe or split is a new contract (owner `revise`).
6. Outside the governed case, a discovery-only measurement can be made with
   `uv run alpha research diagnostic run-plan <plan.json>` (fixed momentum or frozen rule
   baseline, see the [bounded workflow](../../../docs/operations/bounded-research-workflow.md)).
   Its receipt is never case evidence and never changes a phase.

## Outputs

- Immutable D0 and D1 runs under `runs/<run_id>/` (D1 writes `d1_analyses.json` and
  `research_gate_evidence.json`), attempts and launch records in the control store; diagnostic
  receipts under `research_executions/<id>/`. All in the data directory, none in git.

## Checkpoint

The owner reads `alpha research evidence-hub <case>` and `decision-view <case>` (stage 05 shows
how). They either close early (only INCONCLUSIVE or INVALID while D2 stays sealed, stage 06) or
let D1 evidence go to confirmation (stage 04). No agent result advances the case by itself.

Not yet possible offline: everything after step 1. The walk-through case stopped at
`exploration_review` because the owner's approval is not automated, and D1 would also need a
Tiingo-qualified dataset (stage 02). D0, D1, D2 and the decision are exercised offline only by
the test suite (`tests/integration/test_research_program_acceptance.py`, 3 passed, 2026-11-14),
which records approvals inside the test. The run-plan diagnostic did run offline on synthetic
bars (`completed_evidence`; the default 504-bar training window needs more than 400 bars).
