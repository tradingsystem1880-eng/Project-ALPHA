---
owner: project layer
sources:
  - apps/alpha-mcp/CONTEXT.md
  - docs/reference/invariants/cli-assistant.md
  - docs/roadmap/capabilities.toml
verified: f89aa1bb78af
---

# AI assistants

Two ways AI is used inside the product (as opposed to building it): an assistant that can explain
a recorded run and suggest tests, and a tool server (MCP, the Model Context Protocol) that lets an
AI client such as Claude or Codex call a bounded set of `alpha` commands.

## Why it exists

The owner works with AI agents. They need a safe way to read ALPHA's results and run allowed
commands, and the owner benefits from plain explanations of evidence, without any of it turning
into a decision ([ADR-0022](../../../adr/0022-codex-collaboration-surface.md)).

## Its job in the research loop

Advisory only. It can help at any step of the [research loop](../overview.md#the-research-loop)
by explaining or suggesting; it never proposes experiments for RD-Agent, admits evidence or
approves anything.

## Intended design

- The tool server calls the [command line](command-line.md) as a separate process.
- Assistant and investigation output is labelled advisory and kept apart from evidence.

## What is real today

See the capabilities below on [STATUS.md](../../../../STATUS.md).

## Where it lives

- **Workspaces:** `apps/alpha-mcp`
- **Capabilities:** `ai-investigations`, `ai-tools-connection`
- Code: `apps/alpha-mcp/src/`; the `alpha assistant` and `alpha research investigations` commands
  in `apps/alpha-cli/`.
- How to change it: [apps/alpha-mcp/CONTEXT.md](../../../../apps/alpha-mcp/CONTEXT.md).
- Runbook: [Codex investigations](../../../operations/codex-investigations.md).
- Decision records: [ADR-0022](../../../adr/0022-codex-collaboration-surface.md),
  [ADR-0015](../../../adr/0015-evidence-ledger-not-agent-memory.md).

## Decisions and open questions

- No owner decision about this part is in the [owner decisions log](../owner-decisions.md) yet.

## Never

- Never let the tool server approve or decide research, use the one-shot confirmation, reveal the
  holdout or place orders.
- The rules: [MCP invariants](../../invariants/mcp.md) and
  [command line assistant](../../invariants/cli-assistant.md).
