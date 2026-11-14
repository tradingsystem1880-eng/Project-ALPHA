---
owner: research pipeline
sources:
  - apps/alpha-cli/src/alpha_cli/research_cmds.py
  - apps/alpha-cli/src/alpha_cli/_research_cmd_parts.py
  - apps/alpha-cli/src/alpha_cli/research_d2.py
  - apps/alpha-cli/src/alpha_cli/control_store.py
verified: 9c40aa259c97
---

# Stage 04 — confirm: one sealed D2 test

## Purpose

Test the one claim that survived discovery, once, on the sealed confirmation share (D2) that
nobody has looked at. The confirmation contract is derived mechanically from the D1 evidence;
nothing about it is chosen after seeing D2.

## Inputs

- A case in `deep_research` whose admitted D1 evidence clears its primary claim.

## Read first

| Read | Section | When |
|---|---|---|
| [falsification protocol](../../../.agents/skills/alpha-research-protocols/falsification-design.md) | Method | always |
| [evidence synthesis protocol](../../../.agents/skills/alpha-research-protocols/evidence-synthesis.md) | Method | before drafting confirmation |
| [command line research](../../../docs/reference/invariants/cli-research.md) | Contracts and approvals | always |
| [research integrity](../../../docs/reference/invariants/research-integrity.md) | Research before strategy | always: D2 is one-shot, D3 is never read |

## Process

1. Draft the D2 contract: `uv run alpha research draft-confirmation <case> --json`. It derives
   the one-variant primary family, direction and minimum effect from the D1 evidence and fails
   loud on a degenerate discovery interval; the phase becomes `confirmation_review`.
2. Export it for the owner: `uv run alpha research export <case> --json`, then `verify`.
3. Stop. The owner approves or rejects the confirmation contract (checkpoint below).
4. After approval (phase `sealed_confirmation`): `uv run alpha research run confirm <case>
   --json`. D2 is read exactly once; a failed attempt may be retried at most twice under the
   same run id. A changed implementation fingerprint (a change to what the research code does, not a
   comment or formatting edit; ADR-0045) marks D2 contaminated (outcome INVALID).
5. Read `status`: a successful run consumes D2 and moves the case to `research_decision`.

## Outputs

- The confirmation contract and its dossier, the immutable D2 run under `runs/<run_id>/` with
  `d2_analyses.json` and `research_gate_evidence.json` (REGISTERED CONFIRMATORY), and the D2
  history in the control store. All in the data directory, none in git.

## Checkpoint

Before D2 is touched, the owner reads the confirmation dossier: the single claim, its direction
and minimum effect, the frozen multiplicity, and that its D2 boundary is the one sealed at
capture. They approve (`alpha research approve confirmation ...`) or reject it themselves, in
the Workstation or the trusted-local command line. Authorising D2 is an owner act; an agent
never runs it, and never reruns D2 to get a different answer.

Not yet possible offline: this whole stage. It needs D1 evidence from a registered real
dataset (stage 02 and 03) and an owner approval; only the test suite reaches it offline.
