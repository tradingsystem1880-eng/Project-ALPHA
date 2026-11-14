---
owner: research pipeline
sources:
  - apps/alpha-cli/src/alpha_cli/research_cmds.py
  - apps/alpha-cli/src/alpha_cli/research_gate_packet.py
  - apps/alpha-cli/src/alpha_cli/research_readiness.py
  - apps/alpha-cli/src/alpha_cli/research_dossier.py
verified: bdd1a2a989f8
---

# Stage 05 — validate: check the evidence before the owner decides

## Purpose

Assemble what the case has actually recorded, check it independently and say plainly what it
does and does not show. Every projection here is computed from the control store and immutable
runs; untested sections say NOT_TESTED and are never filled in by hand.

## Inputs

- A case in `research_decision` (after D2, or after D0/D1 for an early close), or any open case
  the owner wants reviewed.

## Read first

| Read | Section | When |
|---|---|---|
| [adversarial research review](../../../docs/reference/research-review.md) | Review order | always |
| [robustness protocol](../../../.agents/skills/alpha-research-protocols/robustness-review.md) | Method | always |
| [research critic protocol](../../../.agents/skills/alpha-research-protocols/research-critic.md) | Method | disagreeing with a recorded finding |
| [research method](../../../docs/reference/research-method.md) | Stop and synthesise | writing the owner's summary |
| [research integrity](../../../docs/reference/invariants/research-integrity.md) | Statistical evidence | always |

## Process

1. Read the projections: `uv run alpha research report <case> --json` (progress report, or the
   terminal ResearchGatePacket once closed), `uv run alpha research evidence-hub <case> --json`
   (eleven sections) and `uv run alpha research decision-view <case> --json` (checklist,
   scorecard, packet, history).
2. Write and check the dossier: `uv run alpha research export <case> --json`, then
   `uv run alpha research verify <case> --path <dossier path> --json` (byte-verified).
3. Review it adversarially, from the records only, with the finding format and READY / NOT READY
   handoff of the [review guide](../../../docs/reference/research-review.md#finding-format). Give
   a reviewer the dossier and run ids, never your own reasoning.
4. A review in the typed `SpecialistReview` shape can be checked against its evidence:
   `uv run alpha research diagnostic check-review <review.json>` (binding, not truth).
5. Comments go in as notes (`uv run alpha research note add <case> --kind ... --body ...`); a
   note is never evidence and never changes a finding.

## Outputs

- The dossier under `research/projects/<case>/` in the data directory, the review findings in
  chat or as notes, and a three-layer summary for the owner. Nothing is committed to git.

## Checkpoint

The owner reads the 90-second answer, the open review findings and every NOT_TESTED line. A
`NOT READY` review or an open critical or high finding means the case is not ready for a
positive decision; the owner may still close it as INCONCLUSIVE, INVALID or park it.

Not yet possible offline: a terminal ResearchGatePacket. `report` and `decision-view` run on an
open case (walk-through: `gate_packet` null, every dimension NOT_TESTED) and `export`/`verify`
work, but the packet exists only after the owner's decision in stage 06.
