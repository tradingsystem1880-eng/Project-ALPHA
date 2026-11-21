---
owner: project layer
sources:
  - packages/alpha-validation/CONTEXT.md
  - apps/alpha-cli/src/alpha_cli/spine/**
verified: e55243237f9125af
---

# Validation and evidence

The statistical checks (the "gauntlet") that decide whether a backtest result is believable, and
the reports that show the result: walk-forward tests, random "null" comparisons, bootstrap
ranges, the deflated Sharpe ratio, path-risk simulation and risk numbers.

## Why it exists

A profitable backtest is easy to find by chance. Before anything is trusted with real money the
owner needs to know whether the edge survives costs, data it was not tuned on, and the many ideas
that were tried ([owner decisions](../owner-decisions.md#2026-11-14-precision-and-live-capital)).
This is that test.

## Its job in the research loop

Step 6 of the [research loop](../overview.md#the-research-loop): it judges each experiment after
[Nautilus](nautilus.md) has run it. Its verdict is the feedback [RD-Agent](rd-agent.md) uses for
the next round, and the evidence the owner looks at in [research cases](research-cases-and-approval.md).

## Intended design

- The statistics know nothing about the engine; the [command line](command-line.md) joins them to
  backtest results.
- Every statistic has an independent correctness check (an oracle) and is held to a stricter code
  standard (the quant tier).
- Path risk (Monte Carlo) is measured separately from proof of an edge
  ([ADR-0029](../../../adr/0029-four-family-monte-carlo-validation.md)).

## What is real today

Every plain rule test also stores an automatic diagnostic pass and mechanical audit, unless it is
run with `--no-diagnose` and labelled `no-diagnostics`: benchmark comparisons, drawdowns,
concentration, sensitivity re-runs and explicitly counted variants. The owner can read these
through `alpha results` and `alpha diagnose`; flags identify observations to examine and grant no
research authority. [Stored facts](../../invariants/cli-runs.md#stored-facts-and-diagnostics)
retain the basis and source for each number, including a reason when it is unavailable. A run's diagnostics
and manifest appear together or not at all.
`alpha results check <file>` reads a drafted answer and verifies each tagged number, run label,
the trial count and any sentence that contradicts a stored flag against those stored facts, and `alpha results compare` computes differences
between runs in code. Both are mechanical: they catch an invented or mistyped number, not bad
reasoning. `alpha partner selftest` runs 25 planted honest and dishonest answers through the check.

The inverted-signal research control trades the opposite direction without adding a trial; CASH shorts
are hypothetical and no borrow or funding cost is charged. Walk-forward efficiency compares each fold's
out-of-sample return with the rule's return over that fold's recorded training window; it is a
practitioner rule of thumb, not a statistical test. See the
[inversion card](../../../../research/tools/inverted-signal-control.md) and
[efficiency card](../../../../research/tools/walk-forward.md).

Price-noise controls re-run 50 perturbed copies without counting trials; the plausibility flag asks for a data/look-ahead check.
Neither is proof of an edge. See the [noise card](../../../../research/tools/price-noise.md).

Three follow-up [investigation tools](../../invariants/cli-investigation-tools.md) answer
questions the flags raise, on one recorded rule test. They are entries of the
[toolbox](toolbox.md), run together with `alpha tool run-set market-context`:
`market.attribution` (how much of the return is market exposure, with Newey-West uncertainty),
`market.vol_regimes` (calm versus turbulent markets from a Markov-switching model) and
`market.changepoints` (dates where the behaviour shifted). They are glue over statsmodels and
ruptures, write no new statistics, log every attempt, and label what they cannot avoid:
`hindsight`, `parameters-fit-in-sample`, `benchmark-is-same-asset`, `non-default-params`.

See the capabilities below on [STATUS.md](../../../../STATUS.md).

## Where it lives

- **Workspaces:** `packages/alpha-validation`
- **Capabilities:** `validation-gauntlet`, `risk-numbers`, `prop-firm-check`, `run-reports`, `result-diagnostics`,
  `answer-check`, `family-deflated-sharpe`, `inverted-signal-control`, `walk-forward-efficiency`, `price-noise`, `implausibly-good`
- Code: `packages/alpha-validation/src/`; the gauntlet is assembled in
  `apps/alpha-cli/src/alpha_cli/_gauntlet.py`.
- Tests: `tests/smoke/test_validation_smoke.py`, `tests/oracles/`, and the validation tests under `tests/unit/`.
- How to change it: [packages/alpha-validation/CONTEXT.md](../../../../packages/alpha-validation/CONTEXT.md).
- Plans: the `plans` of each capability above in `docs/roadmap/capabilities.toml`.
- Decision records: [ADR-0006](../../../adr/0006-two-tier-null-model.md),
  [ADR-0029](../../../adr/0029-four-family-monte-carlo-validation.md).
- **Plan:** [stages 5 and 6](../../../roadmap/production-scope-2.md#5-overfit-tests) of the
  checklist; [toolkit](../../../roadmap/backlog/afml-toolkit-worker.md).

## Decisions and open questions

- Triage card 5 (risk numbers): KEEP, 2026-11-14 under the owner's delegation ([triage sheet](../../../roadmap/triage-2026-11.md)).
- Path-risk simulation has its own page, [Monte Carlo](monte-carlo.md); the investigation tools are in the [toolbox](toolbox.md).

## Never

- Never weaken a check, an oracle or a tolerance to make a change pass.
- Never present a passing check as proof of a profitable strategy.
- The rules: [validation invariants](../../invariants/validation.md) and
  [statistical evidence](../../invariants/research-integrity.md#statistical-evidence).
