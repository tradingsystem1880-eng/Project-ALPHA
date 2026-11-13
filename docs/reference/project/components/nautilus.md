---
owner: project layer
sources:
  - packages/alpha-backtest/CONTEXT.md
  - docs/adr/0003-t+1-fill-encoding.md
  - docs/roadmap/capabilities.toml
verified: f89aa1bb78af
---

# Nautilus

NautilusTrader is an open-source trading engine that ALPHA uses to simulate strategies on past
data (a backtest). ALPHA's harness around it makes every simulated order behave the way ALPHA's
rules require.

## Why it exists

A believable result needs a realistic simulation: orders, fills, fees and positions handled the
way a real trading engine handles them. NautilusTrader already does this well, so ALPHA uses it
rather than writing a simulator of its own. It is ALPHA's only simulation and execution engine;
paper sessions run through it too ([ADR-0017](../../../adr/0017-authoritative-daily-data-and-broker-paper-boundary.md)).

## Its job in the research loop

Step 5 of the [research loop](../overview.md#the-research-loop): every experiment, whether a
[trading rule](strategies-and-signals.md) or a [Qlib](qlib.md) model's predictions, is replayed
here with costs. Its results go to the [statistical checks](validation-and-evidence.md).

## Intended design

- The real NautilusTrader package at a fixed version, installed, not copied.
- ALPHA's harness turns daily bars into the engine's feed so that a decision made at a bar's close
  fills at the next bar's open, adds ALPHA's fee and slippage model, and writes a fixed result
  format ([ADR-0003](../../../adr/0003-t+1-fill-encoding.md)).
- Use Nautilus's own engine, adapters and lifecycle parts before writing equivalents; an upstream
  default (such as its default fill model) is never accepted without ALPHA's own checks.

## What is real today

See the capability below on [STATUS.md](../../../../STATUS.md).

## Where it lives

- **Workspaces:** `packages/alpha-backtest`
- **Capabilities:** `backtest`
- Code: `packages/alpha-backtest/src/alpha_backtest/` (`engine.py`, `feed.py`, `frictions.py`).
- Tests: `tests/smoke/test_backtest_smoke.py`, and the backtest tests under `tests/unit/`.
- How to change it: [packages/alpha-backtest/CONTEXT.md](../../../../packages/alpha-backtest/CONTEXT.md).
- Decision records: [ADR-0003](../../../adr/0003-t+1-fill-encoding.md),
  [ADR-0013](../../../adr/0013-run-identity-v3-and-causal-artifacts.md).

## Decisions and open questions

- Install and call the real package, never copy it: the owner's rule for Qlib applies here too
  ([owner decisions](../owner-decisions.md#2026-11-14-install-and-call-real-qlib)).
- The Qlib-to-Nautilus demonstration views (triage card F) are listed under [Qlib](qlib.md).
- Open: no next step for the harness itself is planned; its work follows the parts that feed it.
- Whether Nautilus and Qlib count as core engines like RD-Agent is asked of the owner under
  [Qlib](qlib.md#decisions-and-open-questions).

## Never

- Never let an order fill on the bar that triggered it.
- Never accept an upstream default or example as ALPHA's result without its own checks.
- The rules: [backtest invariants](../../invariants/backtest.md) and
  [decide at close, fill at next open](../../invariants/research-integrity.md#decide-at-close-fill-at-next-open).
