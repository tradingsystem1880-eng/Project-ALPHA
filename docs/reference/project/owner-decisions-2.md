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

### 2026-11-14 Prove all 31 unproven features, one by one

- **Said:** "All 31 unproven features. Prove, built, implement, improve all of them. 1 by 1.
  You have must be agentic and austomusl. If you can improve then or have better suggestions act
  on it. Remember the purpose of this project and what the end goal is. Make profit trading
  financial products. Find alpha and edges l. Build trading models and systsem. Reserash. I wbat
  to domiate in trading and investing."
- **Context:** the status page listed 31 features as built but never run from start to finish
  through the installed program. None is to be shelved by default; each is proven end to end,
  finished or improved, in turn. The assistant may act on improvements without asking.
- **Governs:** every capability in `docs/roadmap/capabilities.toml`; the
  [overview](overview.md).

### 2026-11-14 Any free stock source now; Alpaca account to follow

- **Said:** "Just use any free api. I can make an alpaca account in a few hours whej I have
  time tho"
- **Context:** widens the entry above: a free source that needs no key may be used now. The
  owner was told on 2026-11-14 that Yahoo's terms forbid automated collection.
- **Governs:** the [data layer](components/data-layer.md).

### 2026-11-14 Thin ALPHA dramatically; RD-Agent and Qlib are the proven core

- **Said:** "Yes lighten rules. If aloha is being too constraining and over complicating rd
  agents and qlibs ore design flows. Cut all bloat and mess. Qlib and rd agents are much more
  robust and proven then aloha which is vibe coded. We need robust systsem for this. Keep alpha
  things that make rd agents and qlib better but cut any bloat or over complicating things.
  Rector and thin out project dramatically."
- **Context:** answers the assistant's question whether to lighten the approval rules to: free
  exploration, with the owner's approval required only before a candidate goes to paper or live
  trading. It follows the first real RD-Agent loop, where RD-Agent's idea generation and Qlib
  worked as built and ALPHA's approval machinery blocked a first study. Supersedes
  [prove all 31 features](#2026-11-14-prove-all-31-unproven-features-one-by-one) where they
  conflict: a feature that does not make an RD-Agent and Qlib research loop better, or get a
  result to market, is cut, not proven. Research-integrity guards (point-in-time data, bias
  guards, oracles, determinism) are not part of what is lightened. Main before the cut is
  tagged `pre-thin-2026-11-14`.
- **Governs:** the whole project; the [overview](overview.md).

### 2026-11-14 Keep the user interface

- **Said:** "And of course the ui. Keep the ui." And later the same day: "I want the ui kept.
  I'm not a coder and the only way I understand the project is though the ui. The ui is
  absolutely key"
- **Context:** narrows the thinning above: the Workstation web app stays and is the main way
  the owner sees the project. Whatever is kept or built must be visible there in plain
  English; a screen is re-pointed or replaced, never simply removed.
- **Governs:** the Workstation web app (`apps/alpha-web`).

### 2026-11-14 Never high-frequency trading

- **Said:** "A HUGE RULE. This project will never do high frequency trading. Every. We can't
  win in that regime. We focus on swing trading mostly and some intraday."
- **Context:** a standing rule for every design choice: daily bars first, intraday (minutes to
  hours) second; nothing is built for tick, order-book or latency-sensitive trading.
- **Governs:** the whole project; the [overview](overview.md).
