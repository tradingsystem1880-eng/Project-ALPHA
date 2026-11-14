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

### 2026-11-14 Accept losing temperature on the Codex route, for now

- **Said:** "Accept temperature on codex route. For now. Will test and compare paid api later"
- **Context:** the Codex route cannot apply RD-Agent's temperature setting (0.5), so the model
  gateway refuses it unless started with `--accept-unhonoured temperature`
  ([ADR-0044](../../adr/0044-rdagent-model-gateway.md)). This is a temporary acceptance: a
  comparison against the paid route is still owed before it is treated as settled.
- **Governs:** [RD-Agent](components/rd-agent.md).

### 2026-11-14 Free stock prices from a free service until the Mac

- **Said:** "Yes just use free stock api like finance or alpaca for now until mac is available"
- **Context:** answers the open question of where free stock prices come from. Carried out with
  Alpaca's free plan; the Yahoo downloader stays unused because Yahoo's terms forbid automated
  collection (that reading is the assistant's, not the owner's words). The owner creates the
  account and enters the key. Results stay labelled not yet confirmed.
- **Governs:** the [data layer](components/data-layer.md).

### 2026-11-14 Close the daily-rule binding gap

- **Said:** "Yes" (to: bind daily-rule approvals to three files the daily rule depends on that
  were not covered: `_control_schema.py`, `_ml_observation_store.py`,
  `_native_daily_rule_history.py`).
- **Governs:** [research cases and approval](components/research-cases-and-approval.md).

### 2026-11-14 The control-store split is the assistant's call

- **Said:** "Do whatever you believe makes sense based of our goals and the purpose the project"
  (to: when to run the control-store split).
- **Context:** the assistant chose to run it now, before any real study is approved, because
  each step invalidates daily-rule approvals once and that costs nothing today.
- **Governs:** [delivery and agent tooling](components/delivery-and-agent-tooling.md).

### 2026-11-14 The daily rule may read multi-month crypto snapshots

- **Said:** "Yes" (to: let the daily rule's price reader read every month in a crypto snapshot
  instead of one month per snapshot).
- **Governs:** the [data layer](components/data-layer.md).
