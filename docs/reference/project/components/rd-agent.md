---
owner: project layer
sources:
  - workers/rdagent/CONTEXT.md
  - workers/rdagent/README.md
verified: a79d832d
---

# RD-Agent

RD-Agent is Microsoft's open-source AI research agent. In ALPHA it is the research loop: it
proposes an idea, turns it into an experiment, runs it, judges the result, remembers it and
repeats. It is a core engine; the owner has said so in plain words.

## Why it exists

ALPHA's purpose is to test many market ideas carefully. Doing that by hand is slow, and building
a research agent from scratch would duplicate a mature open-source one. So ALPHA uses RD-Agent to
drive the loop, and keeps for itself everything that must be exact and owner-controlled.
The owner: "Rd agents is one of the key components"
([owner decisions](../owner-decisions.md#2026-11-14-rd-agent-is-a-key-component)).

## Its job in the research loop

Steps 3 to 6 of the [research loop](../overview.md#the-research-loop): propose a hypothesis, have
the experiment built (a [Qlib](qlib.md) model or a [trading rule](strategies-and-signals.md)),
have it backtested by [Nautilus](nautilus.md), take the verdict of the
[statistical checks](validation-and-evidence.md) as feedback, and go round again. It never decides
what counts as evidence; [the owner does](research-cases-and-approval.md).

## Intended design

- One fixed, unmodified upstream version (commit `484776c`), checked file by file before use; never
  copied into ALPHA and never edited.
- It runs as a separate worker program with its own install, started and supervised by the
  [command line](command-line.md). No ALPHA package imports it.
- RD-Agent supplies the loop engine, its records (hypothesis, experiment, trace, feedback) and its
  checkpoints. ALPHA supplies the budget, the data, the backtests, the statistics, the approvals,
  cancellation and recovery. There is no second scheduler or trial ledger.
- An AI model proposes the hypotheses. The owner prefers strong models through the ChatGPT
  subscription, with a cheap model on an API key as the fallback, without losing quality
  ([owner decisions](../owner-decisions.md#2026-11-14-rd-agents-ai-models)).
- Later: RD-Agent drives the Qlib worker, and composes studies across all research families.
- The plain-English walk-through is [RD-Agent in ALPHA](../../../roadmap/rd-agent-in-alpha.md).

## What is real today

See the capabilities below on [STATUS.md](../../../../STATUS.md), and
[what is real today](../../../roadmap/rd-agent-in-alpha.md#what-is-real-today) and
[what is still made-up](../../../roadmap/rd-agent-in-alpha.md#what-is-still-made-up).
Being uninstalled somewhere, or having skipped tests, means work is left, not that it should go.

## Where it lives

- **Workspaces:** `workers/rdagent`
- **Capabilities:** `ai-stock-research`, `native-job-result`, `daily-rule-study`, `ai-research-team`
- Code: [`workers/rdagent/`](../../../../workers/rdagent/README.md); the job supervisor in
  `apps/alpha-cli/src/alpha_cli/native_supervisor.py`. Setup: `scripts/setup_rdagent.sh`.
- Tests: `tests/smoke/test_rdagent_smoke.py`, `tests/unit/test_native_loop_conformance.py`,
  `tests/unit/test_rdagent_foundation_contract.py`.
- How to change it: [workers/rdagent/CONTEXT.md](../../../../workers/rdagent/CONTEXT.md).
- Plans: the `plans` of each capability above in `docs/roadmap/capabilities.toml`.
- Backlog: [autonomous research and restart](../../../roadmap/backlog/rdagent-autonomous-research.md),
  [gate coverage](../../../roadmap/backlog/gate-coverage-rdagent.md).
- Decision records: none of its own yet. Related: [ADR-0011](../../../adr/0011-evidence-gated-external-integrations.md),
  [ADR-0035](../../../adr/0035-generic-study-composition-and-external-capability-adapters.md).

## Decisions and open questions

- KEEP, owner, 2026-11-14 ([log](../owner-decisions.md#2026-11-14-rd-agent-is-a-key-component)).
- What is next, in order, with what each needs from the owner:
  [the seven blockers](../../../roadmap/rd-agent-in-alpha.md#what-stands-between-today-and-rd-agent-researching-real-ideas).
- Owner to confirm: RD-Agent calls AI models through an API. If the ChatGPT subscription cannot be
  used that way, what monthly spending limit should the API key have?
- Owner to confirm: which machine and disk should hold long studies? The Dell has about 48 GB free
  and a study needs at least 100 GB.
- Owner to confirm: is the "autonomous AI research team" plan (triage card 15) part of RD-Agent's
  future, or a separate idea?
- Open: no decision record states RD-Agent's role; write one once the owner confirms the summary
  in the [overview](../overview.md#the-research-loop).

## Never

- Never recommend shelving, removing or replacing it without citing this file and the
  [owner decisions log](../owner-decisions.md).
- Never copy, patch or re-implement RD-Agent inside ALPHA; use the pinned upstream version.
- Never let its output count as evidence or approval.
- The worker rules: [RD-Agent worker](../../invariants/workers.md#rd-agent-worker) and
  [command line native](../../invariants/cli-native.md).
