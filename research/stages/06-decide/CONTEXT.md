---
owner: research pipeline
sources:
  - apps/alpha-cli/src/alpha_cli/research_cmds.py
  - apps/alpha-cli/src/alpha_cli/research_gate_packet.py
  - apps/alpha-cli/src/alpha_cli/control_store.py
verified: aa600e57932d
---

# Stage 06 — decide: the owner's outcome and disposition

## Purpose

Record what the research found and what happens next, in the owner's words, and close the case
with a terminal gate packet. The outcome says what the evidence shows; the disposition says
what the owner wants to do about it. Only the owner does either.

## Inputs

- The decision view and the stage 05 review of a case in `research_decision` (or an open case
  the owner chooses to close early).

## Read first

| Read | Section | When |
|---|---|---|
| [command line research](../../../docs/reference/invariants/cli-research.md) | Owner decisions | always |
| [promotion protocol](../../../.agents/skills/alpha-research-protocols/strategy-promotion-review.md) | Method | the owner weighs `advance_to_strategy` |
| [research method](../../../docs/reference/research-method.md) | Stop and synthesise | always: the outcome and disposition words |
| [research integrity](../../../docs/reference/invariants/research-integrity.md) | Owner authority | always |

## Process

1. Show the owner `uv run alpha research decision-view <case>` and the stage 05 summary.
   Recommend an outcome (SUPPORTED, CONTRADICTED, INCONCLUSIVE or INVALID) and, separately, a
   disposition (`advance_to_strategy`, `revise`, `park` or `reject`), with the reason.
2. Say which combinations the program will refuse: after D2 the outcome must equal the D2
   classification; `advance_to_strategy` needs SUPPORTED and promotion readiness `ready`; an
   early close is INCONCLUSIVE or INVALID only.
3. Stop. The owner records it: `alpha research decide <case> --outcome ... --disposition ...
   --actor ... --reason ...`, in the Workstation or run by themselves.
4. After the decision: `uv run alpha research report <case> --json` returns the terminal
   ResearchGatePacket; `export` and `verify` write and check the final dossier.
5. `revise` reopens a pre-D2 child case (`alpha research revise`, also owner-only) and goes back
   to stage 02. `advance_to_strategy` hands over to the strategy lifecycle; it does not mean
   validated, paper-ready or profitable.

## Outputs

- The decision, the closed case and its terminal ResearchGatePacket in the control store, the
  final dossier under `research/projects/<case>/`. All in the data directory, none in git.

## Checkpoint

The owner is the checkpoint: they read the decision view and make the call. An agent may
recommend but never runs `decide`, `revise`, `approve`, `reject`, `reveal-holdout` or an
override, and never reads approval into a silence, a past approval or a green check.

Not yet possible offline: a real decision on a real case. The walk-through stopped at stage 02;
the test suite proves the decision paths with approvals recorded inside the test.
