# Brief: a replay bench to compare models for RD-Agent's jobs

Branch: `feat/m73-model-replay-bench`. Rules: `docs/work/_common-rules-2026-11-21.md`. Workspace: `apps/alpha-cli/CONTEXT.md`
(RD-Agent rows), `workers/rdagent/CONTEXT.md` (read only: do not edit `workers/**`).

## Why

RD-Agent (the research loop) calls a hosted model through a local gateway. The owner approved a replay bench (2026-11-21): send the SAME
stored prompts to several candidate models and compare the outputs with ALPHA's own deterministic checks, before any live change of
model. The owner pays per call: hard caps exist (60 calls per run, 10 USD per run, 50 USD per month) and are never raised. No paid Claude
API is used. Never reduce RD-Agent's prompts, reflections, feedback, memory or context: this build adds a measurement only.

## Build

1. **Record prompts (opt-in).** Find how `alpha rdagent run` starts the gateway (`rdagent_cmds.py`, `rdagent_run_config.py`, the model
   gateway module) and whether a `--log-content` option exists there. Add `log_content = true|false` (default false) to the run config:
   when true, each model call is stored OUTSIDE git under the gateway data folder: stage label (proposal, code, feedback, …), the full
   request, the response, model id, provider, token counts, cost, latency. Stage labels must be TRUE to the stage (a design note says a
   label defect exists: calls mislabelled by stage; find and fix it, with a test). Record the provider that served each call.
2. **The bench.** `alpha rdagent bench plan|run|report`:
   - `plan --prompts <folder> --models a,b,c --samples 2 [--stages proposal,feedback]` prints the number of calls and the cost estimate
     from recorded token counts and the configured prices, and refuses a plan over the caps. It writes nothing and calls nothing.
   - `run` sends each stored prompt to each candidate, `--samples` times, through the SAME gateway and caps, with pinned providers; it
     stores every output; it can resume; it never touches the live loop's memory or ledger (the bench is not a research trial).
   - `report` scores outputs with deterministic checks that already exist in the project (find them; do not write a model-based judge):
     R1 refusal rate (the idea falls in a closed family or repeats a dropped idea: the family and judge rules), R3 buildability (does the
     fixed coder path accept the output: parse and schema checks only when no coder call is budgeted), R4 the prefix (no-future-data)
     check on produced factor code where code exists, cost and latency per call. Paired design: the same prompt across models gives a
     within-prompt difference; print per-model readings with the count of prompts and a plain sentence on what 30 pairs can and cannot
     show. Readings, not verdicts: no "winner" label.
3. **A fake model client** for tests and for cloud builds: deterministic outputs from a fixture, no network. All tests use it.
4. Docs: a tool card (at most 40 lines) and a section in the RD-Agent invariants page; `alpha next` names the bench in one line.

## Tests

Recording off by default and byte-identical behaviour when off; recorded files never under the repository; stage labels true; the plan's
cost arithmetic and the cap refusal; resume; paired scoring on fixtures; no write to the trial ledger or the loop memory (list files
before and after).

## Done

Draft pull request, `ci-ok` green, `report.md` in this folder: what was built, the label defect and its fix, the exact commands for the
owner's machine to (a) record prompts on the next nightly runs and (b) run the bench with real models, and what is unverified.
