---
owner: project layer
sources:
  - docs/roadmap/triage-2026-11.md
  - docs/reference/model-routing.md
verified: f89aa1bb78af
---

# Owner decisions log

The one home for what the owner has said about the direction of ALPHA, in the owner's own words.
Each entry links to the parts it governs. Component files link here instead of repeating it.

## How to use this log

- Read the entries for a part before recommending to keep, change, shelve, delete or cut it.
- When the owner decides something about direction, append a new entry at the end: the date, the
  exact words in quotation marks, the context in one line, and what it governs.
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
