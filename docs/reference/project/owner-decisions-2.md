---
owner: project layer
sources:
  - docs/reference/project/owner-decisions.md
verified: ccf5b56a
---

# Owner decisions log, volume 2

Continues the [owner decisions log](owner-decisions.md); the rules for entries are there. New
entries are appended at the end of this file.

## Entries

The four entries below are choices the owner made on 2026-11-14 from options an agent offered.
The option text was written by the agent, so it is not quoted as the owner's words.

### 2026-11-14 First goal: one real RD-Agent loop

- **Said (chose an offered option; exact words not recorded):** the first thing to get fully
  working after the clean-up is the RD-Agent loop on a real idea: connect RD-Agent to a model
  through Codex, then propose, build, backtest and judge one idea end to end.
- **Governs:** [RD-Agent](components/rd-agent.md), [Qlib](components/qlib.md),
  [Nautilus](components/nautilus.md); the order of work after the clean-up.

### 2026-11-14 Free real data on the Dell now

- **Said (chose an offered option; exact words not recorded):** the Dell downloads free real
  market data now (Yahoo, Stooq, crypto exchanges). Paid or keyed providers still wait for the
  Mac, and results on free data stay labelled not yet confirmed.
- **Context:** narrows [Dell now, Mac later](owner-decisions.md#2026-11-14-dell-now-mac-later),
  which had the Dell on synthetic data only. It does not replace it: real-data confirmation is
  still the Mac's job.
- **Governs:** the [data layer](components/data-layer.md).

### 2026-11-14 Approvals follow code structure, not exact bytes

- **Said (chose an offered option; exact words not recorded):** a research approval stays valid
  when only comments, formatting or docstrings change, and becomes invalid on any change to
  behaviour. It must be built with tests proving a real logic change still invalidates it.
- **Governs:** [research cases and approval](components/research-cases-and-approval.md),
  [validation and evidence](components/validation-and-evidence.md).

### 2026-11-14 A weekly automatic health check

- **Said (chose an offered option; exact words not recorded):** yes to a weekly automatic check
  that refreshes the status page, lists stale documents, flaky tests and unfinished work, and
  opens small clean-up pull requests. It never merges by itself.
- **Governs:** [delivery and agent tooling](components/delivery-and-agent-tooling.md).
