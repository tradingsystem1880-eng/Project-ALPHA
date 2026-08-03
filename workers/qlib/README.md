# Project ALPHA isolated Qlib worker

This project is deliberately outside ALPHA's root uv workspace. It is the only environment that
contains Qlib or LightGBM. The root CLI exchanges canonical JSON/Parquet files with this process;
no model pickle or executable worker object crosses the boundary.

Pinned runtime:

- `pyqlib==0.9.7` (MIT), CPython 3.12 wheel;
- `lightgbm==4.6.0` (MIT), deterministic CPU execution only;
- `numpy==2.2.6`, `pandas==2.3.3`, and `polars==1.41.2` as worker-local data edges.

`uv.lock` resolves the complete 212-package worker and development graph. Qlib brings a large
diagnostic stack (including MLflow, Jupyter, CVXPY, and their transitive dependencies); none enters
the ALPHA root lock. The two directly used upstream notices are preserved in
`THIRD_PARTY_NOTICES.md`. Project ALPHA still has no declared distribution license, so packaging or
redistributing the worker remains blocked on the repository-wide owner decision and a generated
full transitive notice bundle.

## Run

```bash
uv sync --project workers/qlib --locked
uv run alpha ml train EXCHANGE --mode real --no-sync --json
```

The worker builds a causal 158-column Alpha158-style matrix from the verified in-memory panel,
fits preprocessing statistics on each training fold only, trains one Qlib `LGBModel` per fold,
and writes OOS predictions plus portable diagnostics. Qlib Recorder data and LightGBM boosters stay
inside an ephemeral worker directory and are deleted when the process exits.

Daily panel rows and predictions are availability-stamped at the canonical session close
(`session_ts + 23h`), never at midnight. After import, `alpha ml replay EXCHANGE` validates the
complete exchange and executes one synchronized, long-only, top-quintile/equal-weight portfolio
across the frozen universe through ALPHA's canonical multi-asset replay engine with declared costs.
The resulting ALPHA metrics, decisions, orders, fills, portfolio state, and tear sheet are
authoritative for that replay; Qlib's own Recorder/backtest diagnostics are not.

This is still labeled `OOS replay validated — model not recomputed under counterfactual`. ALPHA does
not yet retrain every fold on randomized/counterfactual paths, so the replay is not a full ML
gauntlet and is not promotion-eligible. Single-asset ML equivalence is also not claimed.

## Gate

```bash
cd workers/qlib
uv lock --check
uv sync --locked
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src tests
uv run pytest -q
```

Removal is bounded: delete `workers/qlib`, remove the root `alpha ml` projections, and delete
worker exchanges/control links. No root package dependency or run artifact needs migration.
