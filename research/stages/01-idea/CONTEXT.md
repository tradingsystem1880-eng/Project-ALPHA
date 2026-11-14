---
owner: research pipeline
sources:
  - apps/alpha-cli/src/alpha_cli/research_cmds.py
  - apps/alpha-cli/src/alpha_cli/research_intake.py
verified: aa600e57932d
---

# Stage 01 — idea: sentence to research case

## Purpose

Turn the owner's sentence into a governed Research Case: their exact words kept, a tentative
falsifiable claim, the questions that change its meaning, and a frozen pack of sources. No data
is touched and no trading rule is written here.

## Inputs

- The owner's idea, quoted exactly as they gave it.

## Read first

| Read | Section | When |
|---|---|---|
| [research method](../../../docs/reference/research-method.md) | Capture and questions | always |
| [new-idea intake protocol](../../../.agents/skills/alpha-research-protocols/new-idea-intake.md) | Method | always |
| [hypothesis protocol](../../../.agents/skills/alpha-research-protocols/hypothesis-formalisation.md) | Method | drafting answers to the material questions |
| [literature protocol](../../../.agents/skills/alpha-research-protocols/literature-review.md) | Method | adding sources |
| [research integrity](../../../docs/reference/invariants/research-integrity.md) | Research before strategy | always |

## Process

1. Look for an existing case first: `uv run alpha research list --json`.
2. Capture the sentence verbatim: `uv run alpha research capture "<idea>" --name "<short name>"
   --json`. This creates the case and runs bounded triage; note the `project_id` (the case id).
3. Read where it stands: `uv run alpha research status <case> --json` (`phase`, `blocker`,
   `next_action`) and `uv run alpha research proposal-options <case> --json` (the material
   questions, the registered answer bundles and why each is or is not available).
4. If `proposal-options` lists the blocker `RESEARCH_OPERATOR_UNAVAILABLE` (`status` then says
   "No registered research operator matches this observation"), stop and tell the owner: the
   idea needs a reviewed research operator first. That gap is already a backlog item
   ([daily research operators](../../../docs/roadmap/backlog/daily-research-operators.md)); add
   to it rather than writing a new one, and never improvise a script. Steps 5-7 are then
   optional: they keep the case ready for when an operator exists.
5. Put the material questions to the owner (at most three, each with your recommended answer).
6. Record sources: `uv run alpha research sources add <case> --title ... --locator ...
   --provider ... --access-mode metadata_only|open_access|owner_provided`; search local records
   with `uv run alpha research sources search "<words>"`. Network discovery
   (`sources discover`, `sources fetch`) is owner-clickable and needs the network.
7. Freeze the pack: `uv run alpha research sources freeze <case> --source-id <id> ...`.

## Outputs

- The case, its triage contract and its source records and pack, in the control store under
  the data directory ([where files live](../../CONTEXT.md#where-a-cases-files-live)). Nothing
  is written to the repository.
- For the owner: one short note in chat with the tentative claim, the alternatives, the
  questions and the blocker, if any.

## Checkpoint

The owner reads the tentative claim and answers the material questions in their own words. If
`proposal-options` shows no available answer bundle, the owner decides whether to leave the case
waiting in triage or ask for an operator to be built. Answers are the owner's input, not an
approval: nothing in this stage grants any research authority.

Not yet possible: a new daily-bar idea that is not a double bottom stops at step 4. Today the
only registered operators are the synthetic SPY 60-minute double bottom, the Tiingo SPY daily
double bottom and the Bybit BTCUSDT crowding reversal (walk-through, 2026-11-14). A case
blocked in triage also cannot be closed: `decide` closes early only from `exploration_review`
onward (read in `research_cmds.decide`, not run, since it is an owner command).
