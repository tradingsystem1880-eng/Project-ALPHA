---
owner: forecasting model
sources:
  - packages/alpha-forecast/src/**
  - packages/alpha-forecast/pyproject.toml
verified: 0377681b
---

# alpha-forecast workspace

## Purpose

The facade around the Kronos foundation model: vendored pinned model code, a typed `Forecaster`
protocol, per-sample OHLCV paths with deterministic seeding, and an offline `FakeForecaster`.
It imports only `alpha_core` (import-linter contract "alpha_forecast depends only on core") and
only `alpha_cli` may import it. Importing the package never imports torch; torch and pandas stay
inside. [ADR-0008](../../docs/adr/0008-vendored-kronos-and-alpha-forecast-layer.md)

## Read first

| Read | Section | When |
|---|---|---|
| [forecast invariants](../../docs/reference/invariants/forecast.md) | — | always |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Models and isolated workers | always |
| [research integrity](../../docs/reference/invariants/research-integrity.md) | Point-in-time reads | always |
| [command line machine learning](../../docs/reference/invariants/cli-ml.md) | Kronos forecasts | changing how the CLI runs or caches forecasts |
| [engineering rules](../../docs/reference/invariants/engineering.md) | Polars by default | touching the pandas edge in `kronos.py` |

## How to change it

- Code: `packages/alpha-forecast/src/alpha_forecast/`; the vendored model in `_vendor/kronos/` is
  pinned upstream code, excluded from mypy and lint. Never edit it to fix style.
- Tests: `tests/unit/test_forecast_*.py`; bias guards `tests/bias_guards/test_forecast_*.py` and
  `test_kronos_cache_no_lookahead.py`; integration `tests/integration/test_forecast_cli.py`.
- Tests use `FakeForecaster`; nothing downloads model weights. Missing offline weights must fail
  loud before any network access.
- Check: `uv run python scripts/gate.py check`.

## Outputs

- Tests: a future-poison guard for any change to the forecast inputs or cache key.
- The owning document: `docs/reference/invariants/forecast.md`.
