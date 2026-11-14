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
- RD-Agent reaches every model through ALPHA's local model gateway
  (`workers/rdagent/model_gateway.py`, [ADR-0044](../../../adr/0044-rdagent-model-gateway.md)):
  chat through the signed-in Codex program, embeddings through local Ollama, an owner-keyed paid
  route only if configured. The gateway holds ALPHA's call and dollar budget, refuses or records
  every setting it cannot honour, and logs each call without its text.
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
- Code: [`workers/rdagent/`](../../../../workers/rdagent/README.md) (the model gateway is
  `workers/rdagent/model_gateway.py`); the job supervisor in
  `apps/alpha-cli/src/alpha_cli/native_supervisor.py`. Setup: `scripts/setup_rdagent.sh`.
- Tests: `tests/smoke/test_rdagent_smoke.py`, `tests/unit/test_native_loop_conformance.py`,
  `tests/unit/test_rdagent_foundation_contract.py`; the gateway's
  `tests/unit/test_rdagent_model_gateway.py` and `tests/smoke/test_rdagent_model_gateway_smoke.py`.
- How to change it: [workers/rdagent/CONTEXT.md](../../../../workers/rdagent/CONTEXT.md).
- Plans: the `plans` of each capability above in `docs/roadmap/capabilities.toml`.
- Backlog: [autonomous research and restart](../../../roadmap/backlog/rdagent-autonomous-research.md),
  [gate coverage](../../../roadmap/backlog/gate-coverage-rdagent.md).
- Decision records: [ADR-0044](../../../adr/0044-rdagent-model-gateway.md) (how it reaches its
  models). Related: [ADR-0011](../../../adr/0011-evidence-gated-external-integrations.md),
  [ADR-0035](../../../adr/0035-generic-study-composition-and-external-capability-adapters.md).

## Decisions and open questions

- KEEP, owner, 2026-11-14 ([log](../owner-decisions.md#2026-11-14-rd-agent-is-a-key-component)).
- What is next, in order, with what each needs from the owner:
  [the seven blockers](../../../roadmap/rd-agent-in-alpha.md#what-stands-between-today-and-rd-agent-researching-real-ideas).
- Decided: the Codex route comes first; an API key is the fallback, capped at about 50 US dollars a
  month ([log](../owner-decisions.md#2026-11-14-api-spending-limit-for-rd-agents-models)). Built as
  the model gateway ([ADR-0044](../../../adr/0044-rdagent-model-gateway.md)); measured quality and
  how far a real step got are in the
  [task's verification](../../../work/archive/2026-11/2026-11-14-rdagent-model-gateway/04-verify.md).
- Open, for the owner: whether to accept losing RD-Agent's "temperature" setting on the Codex
  route (the gateway refuses it unless told to accept it; the measurements were made with it
  dropped).
- Decided: the first goal after the clean-up is one real RD-Agent loop, connected to a model through Codex
  ([log](../owner-decisions-2.md#2026-11-14-first-goal-one-real-rd-agent-loop)).
- Decided: long studies use the Dell's disk for now
  ([log](../owner-decisions.md#2026-11-14-use-the-dells-disk-for-studies-for-now)).
- Decided: the autonomous research team is a broader ALPHA capability built around and using
  RD-Agent, started small; it reuses RD-Agent's native abilities and never bypasses ALPHA's controls
  ([log](../owner-decisions.md#2026-11-14-the-autonomous-research-team)).
- Open: no decision record states RD-Agent's role; write one once the owner confirms the summary
  in the [overview](../overview.md#the-research-loop).

## Never

- Never recommend shelving, removing or replacing it without citing this file and the
  [owner decisions log](../owner-decisions.md).
- Never copy, patch or re-implement RD-Agent inside ALPHA; use the pinned upstream version.
- Never let its output count as evidence or approval.
- Never connect it to a model except through the gateway, and never let the gateway switch to the
  paid route by itself.
- The worker rules: [RD-Agent worker](../../invariants/workers.md#rd-agent-worker) and
  [command line native](../../invariants/cli-native.md).
