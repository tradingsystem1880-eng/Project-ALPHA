---
description: Ask Codex (second model, web search on) a research question and get cited claims back as data; optional, graceful skip
argument-hint: "<question>"
---

Research question for the second model: $ARGUMENTS

OPTIONAL — a source-hunting aid, never an authority. Nothing here writes to the
research trail, attests, or decides.

1. Dispatch the `codex-liaison` subagent with `research --question "$ARGUMENTS"`.
   It runs `python3 scripts/codex_bridge.py research …` (read-only, ephemeral,
   `web_search="live"`, output-schema, capped, audited) and returns a
   `CodexResearch` JSON: `claims[{claim, source, quote, confidence}]`.
2. If `available` is false: one line — "codex unavailable — <reason>" — and
   stop.
3. Relay the claims labeled **second-model research (Codex, unverified)**.
   Every claim is a source CANDIDATE: verify it against the primary source
   yourself (WebFetch the paper/doc; the `quant-source-verification` skill
   applies) before using it in code, docstrings, or a research note. A claim
   whose quote you cannot find in the source is dropped, not softened.
4. Only when the owner explicitly asks, append verified claims to the research
   trail (`alpha research note add …`); never do so by default.
