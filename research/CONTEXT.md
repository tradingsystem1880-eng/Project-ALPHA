---
owner: research pipeline
sources:
  - apps/alpha-cli/src/alpha_cli/research_cmds.py
  - apps/alpha-cli/src/alpha_cli/control_store.py
  - packages/alpha-core/src/alpha_core/config.py
verified: f89aa1bb78af
---

# Research pipeline — how an idea becomes an owner decision

## Purpose

Every market idea walks six stages before any strategy code exists. Each stage names the commands
to run, what it leaves behind and what the owner looks at before the next one. A case is one
governed Research Case in the control store; its stage is read from `alpha research status`,
never from memory. Building or changing the research code itself is a delivery task
([`workflow/CONTEXT.md`](../workflow/CONTEXT.md)), not a research stage.

| Stage | Takes in | Leaves behind | Owner act before the next stage |
|---|---|---|---|
| [01 idea](stages/01-idea/CONTEXT.md) | the owner's sentence | a case, answered questions, a frozen source pack | answer the material questions |
| [02 data](stages/02-data/CONTEXT.md) | the case and its source pack | an audited `rd_` dataset; the exploration contract | approve or reject that contract |
| [03 screen](stages/03-screen/CONTEXT.md) | an approved exploration contract | the D0 pilot run, then the D1 discovery run | early decision, or wait for D2 |
| [04 confirm](stages/04-confirm/CONTEXT.md) | clearing D1 evidence | a frozen D2 contract, then the one-shot D2 run | approve or reject the D2 contract |
| [05 validate](stages/05-validate/CONTEXT.md) | a finished D0, D1 or D2 | the dossier, evidence hub and adversarial review | none: reads the review |
| [06 decide](stages/06-decide/CONTEXT.md) | the decision view | the owner's outcome and disposition, the gate packet | the decision itself |

Today an idea moves past stage 01 only if it matches a registered operator (a double bottom on synthetic SPY 60-minute
or Tiingo SPY daily bars, or the Bybit BTCUSDT crowding reversal); any other idea stops there ([stage 01, step 4](stages/01-idea/CONTEXT.md#process)).

Which stage am I in? Run `uv run alpha research status <case> --json` and read `phase` and
`next_action`: `captured` or `triage` without a frozen source pack is 01; `triage` with one, or
`exploration_review`, is 02; `pilot` or `deep_research` is 03; `confirmation_review` or
`sealed_confirmation` is 04; `research_decision` is 05, then 06; `closed` is done.

## Read first

| Read | Section | When |
|---|---|---|
| [research integrity](../docs/reference/invariants/research-integrity.md) | Research before strategy | always |
| [research integrity](../docs/reference/invariants/research-integrity.md) | Owner authority | always |
| [research method](../docs/reference/research-method.md) | — | before working any case: phases, questions, stop rules |
| [command line research](../docs/reference/invariants/cli-research.md) | — | a command refuses and you need the rule behind it |
| [command reference](../docs/reference/commands.md) | alpha research | finding a command; full options are `--help` |
| [what this part is for](../docs/reference/project/components/research-cases-and-approval.md) | — | why it exists; before you keep, shelve or remove it |

## Where a case's files live

Nothing a case produces is committed to git. Everything is under the data directory
(`ALPHA_DATA_DIR`, default `data/`, git-ignored; [layout](../docs/ARCHITECTURE.md#runtime-data-directory-layout)):

- `control/workstation.sqlite3` — the case, contracts, sources, attempts and decisions. The only
  mutable authority.
- `research/projects/<case>/` — dossiers written by `alpha research export` (projections, never
  read back as state).
- `runs/<run_id>/` — immutable runs: data audits, D0, D1 and D2 runs.
- `research_executions/<id>/` and `diagnostics/` — discovery-only diagnostics (not case evidence).
  There is no per-case, per-stage folder: files are keyed by case, run or execution id.

## Authority

Only the owner approves, rejects, decides, revises or authorises D2, through the Workstation's
local confirmation dialog or the trusted-local owner commands they run themselves
([ADR-0038](../docs/adr/0038-local-confirmation-and-terminal-archive-charts.md)). An agent drafts,
runs what an approved contract allows and reports; it never runs an owner command, even with an
`--actor` string, and never treats a green check or silence as approval.

## How to change it

- Each stage file has Purpose, Inputs, Read first, Process, Outputs, Checkpoint, at most 80
  lines (`tests/unit/test_filesystem_contract.py`). Every command in it was run with `--help`.
- A rule belongs in a reference file; the stage links it. Front matter `sources` follow
  [documentation § Front matter](../docs/reference/invariants/documentation.md#front-matter).
- Per-step method: the hash-indexed protocols in `.agents/skills/alpha-research-protocols/`.

## Outputs

- Per case: the files above, under the data directory only. For this pipeline: these files; the
  method's home is `docs/reference/research-method.md`.
