---
description: Ask Codex (web search on) a research question through scripts/codex_bridge.py; returns cited claims as unverified data
argument-hint: "\"<question>\""
---

Run `python3 scripts/codex_bridge.py research --question "$ARGUMENTS"`. If `"available"` is
false, reply "codex unavailable — <reason>" and stop. Otherwise relay the claims labelled
**second-model research (Codex, unverified)**. Each claim is a source candidate: read the primary
source yourself (`.agents/skills/quant-source-verification/SKILL.md`) and drop any claim whose
quote you cannot find. Nothing is written to a research trail unless the owner asks.
