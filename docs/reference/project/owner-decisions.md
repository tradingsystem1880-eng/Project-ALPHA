---
owner: project layer
sources:
  - docs/reference/model-routing.md
verified: a79d832d
---

# Owner decisions log

The one home for what the owner has said about the direction of ALPHA, in the owner's own words.
Each entry links to the parts it governs. Component files link here instead of repeating it.

## How to use this log

- Read the entries for a part before recommending to keep, change, shelve, delete or cut it.
- When the owner decides something about direction, append a new entry to the newest volume
  ([volume 2](owner-decisions-2.md)): the date, the exact words in quotation marks, the context in
  one line, and what it governs. This file is volume 1 and is full; start a new volume when one
  nears 200 lines.
- Never rewrite or delete an entry. If the owner changes their mind, add a new entry that links to
  the old one and says it replaces it.
- An agent's reading of what the owner meant is marked "Recorded understanding, not yet confirmed
  by the owner" until the owner confirms the wording.
- Decisions about how code is built are in [decision records](../../adr/README.md); one-off
  exceptions are in [`docs/records/`](../../records/README.md). This log starts on 2026-11-13.

## Entries

The first entries were said on 2026-11-13 or 2026-11-14 and written down on 2026-11-14; except
for the RD-Agent entry (dated on the triage sheet), the exact day of each was not recorded.

### 2026-11-14 RD-Agent is a key component

- **Said:** "rd agents is part of how this project works. Rd agents is one of the key components."
- **Context:** an agent had recommended shelving the RD-Agent integration because it was not
  installed and its tests were skipped. The owner corrected it.
- **Governs:** [RD-Agent](components/rd-agent.md); triage cards 7, 8, 9 and C, all now KEEP
  ([triage sheet](../../roadmap/triage-2026-11.md)).
- **Recorded understanding, not yet confirmed by the owner:** RD-Agent (Microsoft's AI research
  agent) is the research loop itself; Qlib is the machine-learning toolkit it uses; Nautilus is
  the backtest engine; ALPHA is the governed shell around them (data, statistical checks,
  evidence, owner approval, screens).

### 2026-11-14 Install and call real Qlib

- **Said:** "ALPHA was set up to install and call the real Qlib package rather than copy the
  whole repository"
- **Governs:** [Qlib](components/qlib.md), and the same approach for [RD-Agent](components/rd-agent.md)
  and [Nautilus](components/nautilus.md).

### 2026-11-14 Private means personal

- **Said:** "When I say private I mean it's just for me, not to be made to sell or be commercial.
  It's only public on git as I have a free account"
- **Governs:** the whole project ([overview](overview.md#what-alpha-is-for)); licence choices for
  upstream code and data stay personal and non-commercial.

### 2026-11-14 Precision and live capital

- **Said:** "this project and quant finance and financial market trading is very precise and
  doesn't allow room for error. These strategies, research, trading models etc will eventually
  have live capital deployed."
- **Governs:** every part; in particular [validation and evidence](components/validation-and-evidence.md)
  and [paper and live trading](components/paper-and-live.md).

### 2026-11-14 Dell now, Mac later

- **Said:** "For now dell is main dev box and we focus on getting the project moving forward and
  production ready. Later stage we will use Mac to confirm live data"
- **Governs:** the [phases](overview.md#phases); [paper and live trading](components/paper-and-live.md);
  the [data layer](components/data-layer.md).

### 2026-11-14 Codex builds, Claude plans

- **Said:** "codex is generally better for implementing code while claude is better at planning
  and decision making"
- **Governs:** [delivery and agent tooling](components/delivery-and-agent-tooling.md); who does
  what is kept in [model routing](../model-routing.md), which records it with other words.

### 2026-11-14 RD-Agent's AI models

- **Said, in summary (exact words not recorded):** prefers the ChatGPT subscription with strong
  models; the fallback is an API key with a cheap model; "As long as it doesn't drop quality or
  capability".
- **Governs:** [RD-Agent](components/rd-agent.md), its model connection.

### 2026-11-14 QuantPad no longer used

- **Said, in summary (exact words not recorded):** the owner no longer uses QuantPad.
- **Governs:** the QuantPad archive in the [data layer](components/data-layer.md) (triage card D).

### 2026-11-14 Steady progress, never a mess

- **Said:** "This project is constantly a mess and I never know what's happening… We hardly ever
  make solid healthy progress"; the project should be "vibe coded well and never get to a point of
  mess".
- **Governs:** [delivery and agent tooling](components/delivery-and-agent-tooling.md), this file
  system, and how every agent reports work.

### 2026-11-14 The architecture in one line

- **Said:** "RD-Agent runs the research loop; Qlib supplies research tools and models; Nautilus
  runs execution-aware backtests; ALPHA connects and governs them." And: "ALPHA is more than a
  shell: it owns budgets, data rules, experiment records, validation and approvals. Not every
  experiment needs Qlib. Also, this describes the intended architecture: the complete
  model-connected, real-data loop is not yet qualified."
- **Context:** the owner's answer when asked to confirm the recorded understanding in
  [RD-Agent is a key component](#2026-11-14-rd-agent-is-a-key-component). It replaces that
  understanding; do not call ALPHA a "shell".
- **Governs:** the [overview](overview.md#the-research-loop) and every component page.

### 2026-11-14 API spending limit for RD-Agent's models

- **Said:** "Around 50 usd a month for api credits. That's only if we can't get codex to work in
  the rd agents info structure."
- **Governs:** [RD-Agent](components/rd-agent.md), its model connection: the Codex route comes
  first; an API key is the fallback, capped at about 50 US dollars a month.

### 2026-11-14 What Kronos is for

- **Said:** "Kronos is a flexible research and exploration tool within ALPHA. It powers one of our
  Monte Carlo methods by generating possible market paths that strategies can be tested against."
  And: "It may become useful for signals or risk research, but I don't want to restrict it to
  either role before we've experimented." And: "its forecasts and scenarios still need validation
  before we rely on them for decisions."
- **Governs:** [forecasting](components/forecasting.md) and the Monte Carlo method in
  [validation and evidence](components/validation-and-evidence.md).

### 2026-11-14 Literature strengthens RD-Agent's proposal step

- **Said:** "Use RD-Agent's native paper ingestion, hypothesis generation and experiment
  capabilities wherever they meet our needs. Keep or build a literature worker only where it
  provides meaningful additions, such as discovering relevant research, preserving source
  citations and limitations, and identifying conflicting evidence. Those findings should
  strengthen RD-Agent's proposal step, not create a duplicate research system."
- **Context:** the owner added that the hand-off between the two is not yet shown working end to
  end, and that RD-Agent's finance loop was not found to search for papers by itself.
- **Governs:** [literature worker](components/literature-worker.md), [RD-Agent](components/rd-agent.md).

### 2026-11-14 The autonomous research team

- **Said:** "RD-Agent is the research engine; the autonomous team is the broader capability around
  and using it; ALPHA coordinates and governs both." And: "We should start with a small team and a
  working end-to-end research process, then add specialist roles when they demonstrably improve
  the work. Reuse RD-Agent's native capabilities instead of rebuilding them, and avoid multiple
  overlapping agents doing the same job." And: the team "cannot bypass those controls or place
  trades."
- **Context:** the owner noted it is still a plan with some advisory work, not operational today.
- **Governs:** [RD-Agent](components/rd-agent.md) (capability `ai-research-team`, triage card 15).

### 2026-11-14 Live trading is deferred

- **Said:** "for live trading, that will currently be deferred until we have the entire system
  working and built out and functional." And: "Until all of that can be proven, no use for live
  trading as of now." And: "just defer live trading for now."
- **Context:** the proof the owner named is finding alpha and edge and building profitable models
  and trading systems; the focus until then is the research pipeline, data and learning.
- **Governs:** [paper and live trading](components/paper-and-live.md); the
  [phases](overview.md#phases). Broker, instruments and risk limits are not to be asked for yet.

### 2026-11-14 Use the Dell's disk for studies for now

- **Said:** "Can we just use the disk space available on the dell for now. I will worry about it
  when it gets low on free disk space"
- **Governs:** [RD-Agent](components/rd-agent.md) studies and the storage reserve in the
  [data layer](components/data-layer.md) ([ADR-0043](../../adr/README.md)).

### 2026-11-14 Agents merge and decide routine matters

- **Said:** "I don't know how to merge. Claude should have access to my GitHub and be able to do
  everything for me" And, on the triage sheet: "Build whatever you believe is the right decision"
- **Context:** under that delegation the agent kept the groundwork for RD-Agent driving Qlib
  (triage card A: shelved, not deleted), removed the unused QuantPad code (card D) and treated
  card G as replaced by [Codex builds, Claude plans](#2026-11-14-codex-builds-claude-plans).
  Research approvals, branch protection and credentials stay with the owner.
- **Governs:** [delivery and agent tooling](components/delivery-and-agent-tooling.md), the
  [triage sheet](../../roadmap/triage-2026-11.md), [Qlib](components/qlib.md).

### 2026-11-14 What the file system is for

- **Said:** "if the file system was set up correctly you would have been able to understand
  exactly the thought, reasoning, expected plan, location etc for rd agents. That's the purpose of
  the file system."
- **Governs:** this project layer and every `CONTEXT.md`: a reader starting at `CLAUDE.md` must be
  able to learn what a part is for, why, the plan, where it lives and what must not be done.

