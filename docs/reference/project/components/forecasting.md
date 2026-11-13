---
owner: project layer
sources:
  - packages/alpha-forecast/CONTEXT.md
  - docs/adr/0008-vendored-kronos-and-alpha-forecast-layer.md
verified: a79d832d
---

# Forecasting

Kronos is an open-source "foundation model" for price charts: given recent bars, it draws many
possible future price paths. ALPHA wraps it so its forecasts can be studied and tested like any
other experiment.

## Why it exists

Forecast paths are one more kind of evidence about a market: a possible signal, and a way to
study risk. The decision to bring Kronos in, with its model code kept at a fixed version, is
[ADR-0008](../../../adr/0008-vendored-kronos-and-alpha-forecast-layer.md).

## Its job in the research loop

Step 4 of the [research loop](../overview.md#the-research-loop): a forecast can feed a rule or a
risk study. Its paths are also one family of the path-risk simulation in
[validation and evidence](validation-and-evidence.md).

## Intended design

- The model code is kept in ALPHA at a pinned version (vendored), unlike RD-Agent, Qlib and
  Nautilus, which are installed packages; the reasons are in ADR-0008.
- Weights are local and the model runs offline ([ADR-0010](../../../adr/0010-local-kronos-weights-offline-policy.md)).
- Periods the model was trained on are labelled, so a forecast that has seen the future is never
  mistaken for a real one ([ADR-0009](../../../adr/0009-forecast-leakage-and-tier2-cost-policy.md)).

## What is real today

See the capability below on [STATUS.md](../../../../STATUS.md).

## Where it lives

- **Workspaces:** `packages/alpha-forecast`
- **Capabilities:** `price-forecasts`
- Code: `packages/alpha-forecast/src/`; the `alpha forecast` commands in `apps/alpha-cli/`.
- How to change it: [packages/alpha-forecast/CONTEXT.md](../../../../packages/alpha-forecast/CONTEXT.md).
- Decision records: [ADR-0008](../../../adr/0008-vendored-kronos-and-alpha-forecast-layer.md),
  [ADR-0009](../../../adr/0009-forecast-leakage-and-tier2-cost-policy.md),
  [ADR-0010](../../../adr/0010-local-kronos-weights-offline-policy.md).

## Decisions and open questions

- No owner decision about this part is in the [owner decisions log](../owner-decisions.md) yet.
- Owner to confirm: what is Kronos for in your research: a trading signal, a risk tool, or both?
  The repository describes the tool but not its intended use.

## Never

- Never hide training-period overlap; leakage is labelled, never silent.
- Never import the model's heavy libraries outside this package.
- The rules: [forecast invariants](../../invariants/forecast.md).
