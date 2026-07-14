# Kronos on your Mac — quickstart

One command sets up everything (toolchain, torch stack, **Kronos-base** weights — the
largest open checkpoint at 102.3M params — market data, a first real forecast, and the
web UI):

```bash
git clone https://github.com/tradingsystem1880-eng/Project-ALPHA.git
cd Project-ALPHA
bash scripts/setup_kronos_mac.sh AAPL     # any symbol; default AAPL
```

When it finishes, http://127.0.0.1:8800 opens with the run browser; click the forecast run
to see the chart (solid history, dashed Kronos forecast, p10/p90 band when sampling).
Apple-silicon GPUs (MPS) are used automatically; even on CPU a Kronos-base forecast takes
only ~5–8 s (measured on Apple silicon). `--model mini` is the instant-feedback option.

## Daily use

```bash
uv run alpha data pull NVDA --source yfinance --start 2023-01-01 --end 2026-07-11
uv run alpha forecast run NVDA --model base --horizon 30            # price forecast
uv run alpha forecast run NVDA --model base --sample-count 5        # + uncertainty band
uv run alpha backtest run NVDA --strategy kronos_forecast --param model=2
uv run alpha validate NVDA --strategy kronos_forecast --param model=0 --tier2-paths 8
uv run alpha report <run_id>                                        # re-display any run
uv run alpha-web                                                    # browse everything
```

Model sizes: `mini` (4.1M, context up to 2048 bars), `small` (24.7M, 512), `base`
(102.3M, 512 — default and most capable open checkpoint). In `--param` form (strategy
runs) they are `model=0|1|2`.

## The one caveat that matters

Kronos pretrained weights saw market data up to **~2025-08**. Any forecast/backtest whose
window starts earlier gets a loud yellow warning and a `leakage_warning` field in the run
manifest: over that region the model may be remembering, not forecasting. Treat those
results as upper bounds; genuinely out-of-sample evaluation exists only on post-2025-08
data.

## Troubleshooting

- `weights not found ... run alpha forecast pull` → the download step was skipped; run
  `uv run alpha forecast pull --model base`.
- `the Kronos torch stack is not installed` → run `uv sync --group kronos`.
- Slow forecasts → check the model size; the forecast cache makes *repeat* runs instant,
  but each new window/params combination costs one real inference.
- Weight/data reset: `rm -rf data/models data/forecast_cache`.
