---
owner: status page and roadmap
sources:
  - docs/context/feature-readiness-checklist-2026-10-27.md
  - scripts/capabilities.py
  - scripts/status.py
verified: f89aa1bb78af
---

# Glossary

This page explains the short codes and technical words you may see on an ALPHA status page.
Each entry gives the plain meaning in a line or two. Meanings come from the project's own
documents, not from general usage.

## Plain names rule

Owner-facing text uses the plain name first, with the code in brackets. Example: "Risk numbers
that state what they are based on (C04)". Work package list:
[feature readiness checklist](../context/feature-readiness-checklist-2026-10-27.md).

## Work packages

The roadmap has 19 work packages, W01 to W19. None is declared fully accepted yet. Older numbering
differs: the August 2026 research-first workstation spec's W1–W10 are walkthrough steps (its W10 is
regime testing), not these work packages.

- **W01** — Reconcile baseline and prerequisite acceptance: agree what is truly done at the start.
- **W02** — Bind execution and handoff evidence: tie every run, receipt and recovery to one exact attempt.
- **W03** — Accept architecture and native runtime seams: confirm the system's parts fit together.
- **W04** — Version shared contracts and admission: keep the shared data formats versioned and checked.
- **W05** — Qualify data and point in time boundaries: prove data is real and never leaks the future.
- **W06** — Extend study budgets and irreversible exposure: count every try, and remember what was seen.
- **W07** — Add semantic review and methodology routing: add meaning-aware review and method choice.
- **W08** — Prove one complete native investigation: finish one frozen daily rule with one control.
- **W09** — Route current Qlib through the same case: run the existing Qlib models inside that case.
- **W10** — Add reusable controls and diagnosis: reusable placebo, ablation and rival-explanation tests.
- **W11** — Qualify retraining and sizing risk experiments: retrain fairly and compare position sizing.
- **W12** — Migrate Qlib and deliver model waves: move Qlib over and add models in batches.
- **W13** — Compose general investigations and admitted repairs: combine tests into broader studies.
- **W14** — Add path risk and operational monitoring: watch risk along the path, and watch operations.
- **W15** — Add catalyst and expectations research: study events, filings and news expectations.
- **W16** — Add options expression when data is sufficient: options ideas, only once data supports them.
- **W17** — Qualify the whole research process and paper boundary: test the whole process to paper trading.
- **W18** — Deliver the evidence backed visual workspace: screens and charts backed by evidence.
- **W19** — Qualify data storage and governed queries: storage, queries and restore that are checked.
  Parts: W19a (ownership, workloads), W19b (query receipts), W19c (publish and restore).

## Research stages

The stages of one governed research case. Data is split by date groups, 60/20/20, into D1, D2, D3.

- **D0** — Synthetic Pilot. Tests the detector on made-up data before any real market data is touched.
- **D1** — Deep Research. Runs the frozen plan on the first 60% of real data (the discovery share).
- **D2** — One-Shot Confirmation. A sealed 20% share, read exactly once after you approve.
- **D3** — The last 20% of data. Research may never use it. Paper trading stays separate.
- **R1** — Research Command Center: read-only case list, evidence hub and scorecard.
- **R2** — Codex research desk: context packets, notes and protocols for the AI assistant.
- **R3** — Research Data Hub: data inventory, snapshots and data audits.
- **R4** — Source plane: papers and sources, and the claims drawn from them.
- **R5** — Pre-strategy experiment engine: the analysis plan and the D1 runner.
- **R6** — Confirmation, gate, promotion: the D2 runner, the checklist and promotion of a result.

## Delivery items

- **C04** — Risk numbers that state what they are based on (the "metric basis" shown with risk figures).
- **EX14** — Checklist item: a finite simulated Student-t wealth mean does not prove finite expected wealth.
- **H26** — Checklist feature: a lean, queryable store of project context. Superseded by ADR-0040 (Atlas was retired).
- **H60** — Checklist feature: generate AI context and prompt packs. Superseded by ADR-0040 (Atlas was retired).
- **Phase A–E (edge-first)** — Steps of the September 2026 "edge-first" programme. Phase B: get real
  crypto history in (resumable backfill). Phase C: a fast screening lane (`alpha scan hypotheses`).
  Phase E: widen that screening to every registered method (a backlog idea).
- **Packet 3** — Complete one real native rule-and-control study on daily data. In progress, not done.
- **T07** — Test scenario: restart after launch but before a receipt. Must not repeat work or reset budget.
- **T09** — Test scenario: cancellation or sudden loss of a worker. Absence of work is not a pass.
- **T10** — Test scenario: missing or wrong result file. Must be rejected and an old receipt never reused.

## Statistics and checks

- **Bias guard** — A test that plants future data and fails if anything uses it.
- **CPCV** — Combinatorial purged cross-validation: tests a model on many different date splits.
- **DSR** — Deflated Sharpe ratio: a return-per-risk score reduced for how many ideas were tried.
- **Embargo** — A gap of observations left between two data shares so nothing leaks across.
- **Gauntlet** — The set of strict statistical checks a strategy must survive (the validation gauntlet).
- **Oracle** — A test with a known right answer or rule that a wrong calculation cannot satisfy.
  They live in tests/oracles.
- **PBO** — Probability of backtest overfitting: the chance a best-looking result is just luck.
- **Point-in-time / as_of** — Data viewed as it was known on a date. The as_of reader refuses later data.

## Data

- **Admission** — The check that decides if evidence, data or a result is allowed in. It re-verifies hashes.
- **Alpha158** — A standard set of 158 daily price features used by the Qlib models.
- **Backfill** — Loading past history for a market. A backfill ledger records what was loaded.
- **Fixture / synthetic** — Made-up data used for tests. It is never real market evidence.
- **Ledger** — An append-only log. Entries are added and never changed.
- **Manifest** — The list of files and their hashes that identifies one stored item exactly.
- **Receipt** — A saved proof of a request, its version and its exact content hash.
- **Snapshot** — A frozen, hashed copy of data that a run is tied to.

## Tools and parts

- **ALPHA Quant Platform** — The owner's name for ALPHA as a whole. A name only: it adds no scope or authority.
- **Component (gate)** — One named group of checks run by `scripts/gate.py component NAME`. The names
  are backend, frontend, literature, qlib and eval.
- **ControlStore** — The program part that keeps the project's control database and its append-only ledger.
- **Gate** — `scripts/gate.py`: the local check tool. The real merge gate is CI on the pull request.
- **Codex** — OpenAI's coding assistant, used inside ALPHA as an advisory research assistant. Its answers
  are advice, never approval.
- **IBKR / IBKR Paper** — Interactive Brokers, a stock broker. IBKR Paper is its practice account, with no
  real money.
- **Kronos** — A foundation model used for price forecasts, run in a separate process.
- **MCP** — Model Context Protocol. The link that lets an AI assistant call ALPHA tools. It cannot approve.
- **Nautilus (NautilusTrader)** — The engine ALPHA uses to run backtests and paper trading.
- **Paper trading / paper session** — Simulated trading with no real money. It needs separate opt-in.
- **Qlib** — Microsoft's machine-learning toolkit for stock prediction. ALPHA runs its models in an
  isolated worker.
- **RD-Agent** — Microsoft's AI research agent, which writes and tests ideas by itself. "Native" in
  ALPHA means running through RD-Agent. ALPHA prefers its native loops over custom code.
- **Research Case** — One idea tracked from capture through the research stages to your decision.
- **Workstation** — The local ALPHA app: charts, Research Cases and reports in one window.

## Unclear — to confirm

- None. Every term above was found in the repo.
