---
owner: project layer
sources:
  - workers/literature/CONTEXT.md
  - docs/adr/0024-literature-acquisition-worker-and-claim-model.md
verified: a79d832d
---

# Literature worker

A separate program that finds research papers, fetches them, extracts their text and screens the
claims they make, so a research case can start from published work and link each claim to the
experiment that tests it.

## Why it exists

Good ideas often come from published research. ALPHA needs to find papers, keep the exact
original files, and record which claim led to which experiment, without trusting a paper's
numbers and without exposing the owner's machine to the internet by default
([ADR-0024](../../../adr/0024-literature-acquisition-worker-and-claim-model.md)).

## Its job in the research loop

Step 1 of the [research loop](../overview.md#the-research-loop): it feeds questions and claims
into [research cases](research-cases-and-approval.md). Its output is advisory.

## Intended design

- Its own install and lock; no ALPHA package imports it. It starts with a minimal environment, no
  credentials and resource limits, and no network unless the owner explicitly asks.
- Original PDFs are kept byte for byte under a fixed identity; extracted text is marked untrusted.

## What is real today

See the capabilities below on [STATUS.md](../../../../STATUS.md).

## Where it lives

- **Workspaces:** `workers/literature`
- **Capabilities:** `literature`, `paper-to-experiment`
- Code: [`workers/literature/`](../../../../workers/literature/README.md); the `alpha research sources`
  commands in `apps/alpha-cli/`.
- Tests: `workers/literature/tests/`, and the literature tests under `tests/unit/`.
- How to change it: [workers/literature/CONTEXT.md](../../../../workers/literature/CONTEXT.md).
- Plans: the `plans` of each capability above in `docs/roadmap/capabilities.toml`.
- Decision records: [ADR-0024](../../../adr/0024-literature-acquisition-worker-and-claim-model.md).

## Decisions and open questions

- No owner decision about this part is in the [owner decisions log](../owner-decisions.md) yet.
- Triage cards 6 (link claims to experiments, recommended KEEP) and E (remove the duplicate copy of
  the download code, recommended DELETE) wait for the owner ([triage sheet](../../../roadmap/triage-2026-11.md)).
- Owner to confirm: should the literature worker feed RD-Agent's "propose" step directly (papers as
  a source of hypotheses), or stay a tool you use by hand?

## Never

- Never bypass a paywall, and never use the network without an explicit owner action.
- Never let a paper's claim count as evidence; only ALPHA's own tests do.
- The rules: [literature worker](../../invariants/workers.md#literature-worker).
