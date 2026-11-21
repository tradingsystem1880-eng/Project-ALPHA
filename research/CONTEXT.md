---
owner: research pipeline
sources:
  - apps/alpha-cli/src/alpha_cli/spine/*.py
  - apps/alpha-cli/src/alpha_cli/test_cmds.py
  - apps/alpha-cli/src/alpha_cli/results_cmds.py
  - apps/alpha-cli/src/alpha_cli/research_cmds.py
verified: 35183c457b3d6163
---

# Research: how any idea is tested
## Purpose
Any idea goes through one route: read [the playbook](PLAYBOOK.md), then run `uv run alpha test`. No idea is stopped
for being of an unknown kind, and no research run needs an approval; integrity shows as labels and flags. The only
approval gate is before paper or live trading. Changing the research code is a delivery task ([`workflow/`](../workflow/CONTEXT.md)).

## Read first
| Read | Section | When |
|---|---|---|
| [research playbook](PLAYBOOK.md) | The method | always |
| [research playbook](PLAYBOOK.md) | The numbers rule | always |
| [research playbook](PLAYBOOK.md) | What needs the owner | always |
| [tool cards](tools/README.md) | — | next test by symptom; [library](library/README.md) |
| [data health card](tools/data-health.md) | — | checking stored bars before a test |
| [RD-Agent config example](examples/rdagent.example.toml) | — | starting RD-Agent with `alpha rdagent run` |
| [lessons](lessons/README.md) | — | before proposing a test |
| [research integrity](../docs/reference/invariants/research-integrity.md) | Owner authority | before paper or live trading, or any owner act |
| [what this part is for](../docs/reference/project/components/research-cases-and-approval.md) | — | why it exists; before you keep, shelve or remove it |
| [research method](../docs/reference/research-method.md) | — | working a case in the older staged lane |
| [architecture](../docs/ARCHITECTURE.md) | Runtime data-directory layout | finding where records live |
| [research README](README.md) | Skills by trigger | the owner's words say which skill to use |

## How to change it
- Playbook, tool card and skill rules: [documentation invariants](../docs/reference/invariants/documentation.md#research-playbook-and-tool-cards).

## Outputs
- Per idea: run folders and ledger rows under `ALPHA_DATA_DIR`, and a plain-English report to the owner.
