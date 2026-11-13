---
owner: backtest engine
sources:
  - packages/alpha-backtest/src/**
  - packages/alpha-backtest/pyproject.toml
verified: a7e687ae729f
---

# alpha-backtest workspace

## Purpose

The NautilusTrader run harness: bar-to-feed encoding that makes orders fill at the next open,
engine configuration, instruments, the fee model, the result schema and the multi-asset weight
replay. It imports only `alpha_core` and `alpha_data` (import-linter contract "alpha_backtest
depends only on core + data"); only `alpha_cli` uses it. It must never let an order fill on the bar
that triggered it.

## Read first

| Read | Section | When |
|---|---|---|
| [backtest invariants](../../docs/reference/invariants/backtest.md) | — | always |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Decide at close, fill at next open | always |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Immutable, hash-bound artefacts | always |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Corporate actions: two clocks | changing dividend credits |
| [command line runs](../../docs/reference/invariants/cli-runs.md) | Artifacts and run directories | changing the result schema |
| [validation invariants](../../docs/reference/invariants/validation.md) | Gauntlet gates | a change alters what the gauntlet measures |

## How to change it

- Code: `packages/alpha-backtest/src/alpha_backtest/` (`feed.py`, `engine.py`, `frictions.py`,
  `instruments.py`, `results.py`, `portfolio_replay.py`).
- Tests: `tests/unit/test_nautilus_feed.py`, `tests/unit/test_utc_day_execution_feed.py`,
  `tests/unit/test_portfolio_replay_engine.py`; integration `tests/integration/test_nautilus_engine.py`,
  `test_dividend_credit.py`, `test_frictions.py`, `test_order_rejection.py`; oracles
  `tests/oracles/test_metamorphic_engine.py`, `tests/oracles/test_pnl_rederivation.py`.
- Check: `uv run python scripts/gate.py check`. Engine source bytes are part of run identity, so an
  edit changes run ids. Ask for an independent review on the pull request; it is advisory.

## Outputs

- Tests: an integration test through the real engine for every fill, fee or rejection rule.
- The owning document: `docs/reference/invariants/backtest.md`.
