---
owner: pattern geometry
sources:
  - packages/alpha-patterns/src/**
  - packages/alpha-patterns/pyproject.toml
verified: 0377681b
---

# alpha-patterns workspace

## Purpose

Pure chart-pattern geometry and causal indicators over OHLCV bars: swing structure, trendlines,
wedges, head and shoulders, order blocks, fair-value gaps, harmonics and oscillators. It imports
only `alpha_core` and numpy (import-linter contract "alpha_patterns depends only on core");
`alpha_strategies`, `alpha_study` and `alpha_cli` import it. A pattern must only be reported once
it was knowable from the bars seen so far.

## Read first

| Read | Section | When |
|---|---|---|
| [pattern invariants](../../docs/reference/invariants/patterns.md) | — | always |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Point-in-time reads | always |
| [architecture](../../docs/ARCHITECTURE.md) | 2. The Layered DAG | always |
| [strategy invariants](../../docs/reference/invariants/strategies.md) | Rule specs | a strategy rule reads the changed indicator |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Statistical evidence | porting or changing a statistic |

## How to change it

- Code: `packages/alpha-patterns/src/alpha_patterns/` (one module per detector or indicator).
- Tests: one unit file per detector in `tests/unit/` (for example `test_wedge.py`, `test_harmonics.py`),
  `tests/unit/test_pattern_*.py`, `tests/unit/test_*_bias_guard.py`; bias guards
  `tests/bias_guards/test_hs_no_lookahead.py`, `test_pattern_no_lookahead.py`,
  `test_indicator_no_lookahead.py`, `test_oscillator_no_lookahead.py`.
- Parity tests pin other packages to this one: `tests/unit/test_rules_indicators_parity.py`
  (strategies read exactly what the chart draws) and `tests/oracles/test_differential_runs_test.py`.
- Check: `uv run python scripts/gate.py check`. This package is not in the quant tier.

## Outputs

- Tests: a no-look-ahead bias guard and a synthetic ground-truth case for every new detector.
- The owning document: `docs/reference/invariants/patterns.md`.
