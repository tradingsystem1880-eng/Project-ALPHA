---
owner: research pipeline
sources:
  - apps/alpha-cli/src/alpha_cli/research_cmds.py
  - apps/alpha-cli/src/alpha_cli/research_data_audit.py
  - apps/alpha-cli/src/alpha_cli/data_cmds.py
verified: f89aa1bb78af
---

# Stage 02 — data: case to approved exploration contract

## Purpose

Bind the case to exact, research-only data and freeze the exploration contract the owner will
approve: the claim, the event, the outcome, the data identity, the budget and the analysis plan.
A synthetic-only bundle needs no dataset and goes straight to the draft.

## Inputs

- The case from stage 01 with answered material questions and a frozen source pack.

## Read first

| Read | Section | When |
|---|---|---|
| [data discovery protocol](../../../.agents/skills/alpha-research-protocols/data-discovery.md) | Method | always |
| [data audit protocol](../../../.agents/skills/alpha-research-protocols/data-audit.md) | Method | reading an audit |
| [command line research](../../../docs/reference/invariants/cli-research.md) | Research data and crypto research | registering a dataset |
| [research integrity](../../../docs/reference/invariants/research-integrity.md) | Point-in-time reads | always |
| [local operations runbook](../../../docs/operations/README.md) | — | pulling Tiingo daily bars (needs the owner's key) |

## Process

1. Get bars into the store: `uv run alpha data pull <SYMBOL> --source tiingo --start ... --end
   ...` (every source needs the network; Tiingo needs the owner's key). Then freeze and check
   them: `uv run alpha data snapshot <snapshot-id> <SYMBOL>` and `uv run alpha data verify
   <snapshot-id>`.
2. Register the research copy: `uv run alpha research data register <SYMBOL> --kind snapshot
   --snapshot-id <id> --start <date> --end <date> --bar-minutes 1440 --json` (crypto:
   `research data register-crypto`). Note the `rd_` id; `research data list` shows them all.
3. Audit it against the case: `uv run alpha research data audit <case> <rd_id> --json`. Any
   `blocking_count` above zero stops the stage; say which finding blocks.
4. Recheck `uv run alpha research proposal-options <case> --json`: the chosen bundle must be
   `available` and list your dataset under `compatible_dataset_ids`.
5. Draft the contract: `uv run alpha research draft <case> --source-pack-id <pack>
   --answer-bundle <bundle> [--dataset <rd_id>] --expected-case-revision <case_revision> --json`.
   It must come back `approval_ready: true` with no `blocking_questions`; the phase becomes
   `exploration_review`.
6. Write the contract out for the owner: `uv run alpha research export <case> --json`, and check
   it: `uv run alpha research verify <case> --path <dossier path> --json`.

## Outputs

- A snapshot under `snapshots/`, the `rd_` registration in the control store, an EXPLORATORY
  audit run under `runs/<run_id>/`, the contract and its dossier under
  `research/projects/<case>/`, all in the data directory, none in git.

## Checkpoint

The owner reads the contract dossier (claim, event, outcome, data, budget, stop rules) and
approves or rejects that exact contract in the Workstation, or with `alpha research approve
exploration ...` / `reject` run by themselves. An agent never runs either. Until then
`alpha research run pilot` refuses: "synthetic pilot requires the owner-approved pilot phase".

Not yet possible offline: step 1. No `data pull` source works without the network
([backlog: offline import](../../../docs/roadmap/backlog/offline-data-import.md)). The
walk-through seeded synthetic bars with the test helper instead; their registration reports
provider `yfinance`, so the Tiingo daily bundle stays unavailable and `draft` refuses it. Only
the synthetic SPY 60-minute bundle can be drafted offline.
