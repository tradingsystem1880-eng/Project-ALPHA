# Python Dependency Review — Project ALPHA (2026-06-19)

Status: **adopted**. This is the standing reference for which third-party libraries Project ALPHA
uses, why, and — equally important — which popular quant libraries we deliberately **do not** adopt
and the reasons. Future agents: consult the REJECT list before adding any dependency.

Scope reviewed: the most robust 2026 libraries for algorithmic trading + data science, informed by
curated sources (e.g. `awesome-quant`, quant-twitter recommendation lists). The platform's founding
constraints frame every decision: **$0/free, fail-loud, deterministic-by-hash, minimal, and the
import-linter DAG is inviolable**.

---

## Verdict

The existing stack is already well chosen. The genuinely "best 2026" libraries are mostly (a)
redundant with what we have, (b) license traps for a free platform, or (c) in direct conflict with
our founding principles (parity-by-construction, determinism-by-hash, minimalism). This is a
**targeted refinement, not a revamp**: zero replacements, three DAG-safe additions, an explicit
reject list, and a defer list keyed to concrete future triggers.

---

## Current stack (kept as-is)

| Package | Runtime deps | Coupling / verdict |
|---|---|---|
| `alpha-core` | pydantic, pydantic-settings | Keep. Baked into domain types (`Bar`, `CorporateAction`, `ValidationOutcome`). |
| `alpha-data` | ccxt, yfinance, polars, pandas | Keep. polars at the data boundary; pandas edge-only (yfinance parse). Clean `DataAdapter` seam. |
| `alpha-backtest` | nautilus-trader | Keep. Deeply woven (engine/feed/frictions/instruments) **by design** — parity-by-construction. |
| `alpha-strategies` | nautilus-trader | Keep. `ts_momentum.py` is engine-coupled by design. |
| `alpha-validation` | numpy, scipy, pandas, quantstats-lumi | Keep. numpy/scipy behind clean module APIs; pandas+quantstats lazy at the tear-sheet edge. |
| `alpha-cli` | typer | Keep. Sole composition layer. |
| dev/root | pytest, hypothesis, mypy, ruff, import-linter, pandas-stubs | Keep. |

**Replace recommendations: none.** `nautilus_trader`, `polars`, and `quantstats_lumi` are all
confirmed best-in-class *for our constraints* in 2026. LEAN remains the documented engine Plan B;
there is no trigger to switch.

---

## ADD (this review — 3 additions)

### 1. `pandera[polars]` → `alpha_data`
- **Why:** the platform's thesis is "fail loud on data gaps / NaN / inf / disorder." That firewall
  was hand-rolled and scattered; `pit.py` relied on a *comment* ("bars arrive ts-sorted from the
  store; downstream positional reads depend on it") for a frame-level invariant never mechanically
  asserted. Pandera turns it into a declarative, enforced contract at the store read boundary.
- **Footprint check (pre-flight gate, passed):** `pandera[polars]` resolves with **no pandas and no
  numpy** pulled into `alpha_data` (it brings `pandera`, `typeguard`, `typing-inspect`; polars +
  pydantic already present). The "pandas stays edge-only" principle is preserved.
- **DAG:** `alpha_data → core` unchanged; composes nothing cross-package → no new import-linter
  contract. `SchemaError` is wrapped in our typed `DataError` to honour the fail-loud rule.

### 2. `arch` → `alpha_validation`
- **Why:** conditional-volatility (GARCH/EGARCH/GJR) modelling — a robust primitive for vol-aware
  diagnostics and a future upgrade path for vol-targeted sizing (today: simple realized vol).
- **Footprint:** slots into validation's existing numpy/scipy/pandas stack; adds `statsmodels` +
  `patsy`. Exposed as a pure, fail-loud function. `alpha_cli._runner` is the seam to feed output
  into sizing (strategies cannot import validation under the DAG).

### 3. `skfolio` → new **`alpha_portfolio`** package (BSD-3)
- **Why:** establish the multi-asset allocation primitive ahead of moving beyond single-symbol
  TS-momentum. `skfolio` is sklearn-native and BSD-3 (lighter-licensed than riskfolio-lib;
  `PyPortfolioOpt`/MIT is the simpler fallback if its cvxpy/sklearn/plotly footprint becomes a
  burden).
- **DAG (critical):** new `packages/alpha-portfolio/` depends on **`alpha_core` only**, exposing
  pure optimizer functions over numpy/`core` types. `alpha_cli` composes it. A **6th import-linter
  contract** forbids `alpha_portfolio` from importing any sibling except `core`.

---

## REJECT (standing "do not adopt" list)

**License traps — automatic reject for a $0 platform:**
- `vectorbtpro` — paid license.
- `mlfinlab` — dual/commercial license (do not vendor "borrowed" implementations either).
- any **AGPL** tooling — viral copyleft, incompatible with a freely-operated platform.

**Principle conflicts:**
- `vectorbt` (OSS) — a vectorized engine **breaks parity-by-construction**: the same nautilus
  event engine must run research *and* the Tier-2 `full_engine` null. LEAN is the engine Plan B,
  not vectorbt.
- `backtrader` — unmaintained / effectively dead.
- `zipline-reloaded` / `empyrical` / `pyfolio-reloaded` — pandas-era stacks that duplicate
  `metrics.py` + nautilus + quantstats_lumi and drag pandas deeper.
- `pandas-ta` — a pandas TA library for what pure functions in `signals.py` already do.
- `narwhals` — a cross-dataframe abstraction over a deliberately-singular polars choice = overhead.

**Premature / heavyweight infra (reject for v1):**
- `mlflow` / `hydra` / `optuna` — our determinism is already solved *by content*: `run_id = sha256`
  of canonical params, byte-stable manifests, `SeedSequence` child seeds. Optuna invites
  overfitting-by-search (the gauntlet exists to defend against exactly that); Hydra collides with
  the typed `AlphaSettings`/Typer config surface.
- `numba` / `numexpr` — no measured hot loop justifies them; premature optimization.
- `great-expectations` — heavy, stateful; pandera covers the real need at a fraction of the weight.
- `openbb` — broad aggregator with a large transitive footprint; the narrow `DataAdapter` pattern
  is cleaner.
- `duckdb` — polars already has native `join_asof`; do not add a second query engine. Revisit only
  if a multi-symbol PIT as-of join in pure polars becomes a measured bottleneck.

---

## DEFER (add only when a concrete consumer appears)

| Candidate | Future home | Trigger |
|---|---|---|
| `fredapi` | `alpha_data/adapters/fred_adapter.py` | macro series needed (trivial via existing seam). |
| `alphalens-reloaded` | `alpha_cli` / analysis edge | cross-sectional factor research. |
| `statsmodels` (standalone) | `alpha_validation` | arrives transitively with `arch`; standalone only if a gate needs OLS-style diagnostics. |
| `sktime` / `tsfresh` / `statsforecast` | TBD | a genuine forecasting feature. |
| Paid data (`polygon`/`databento`/`tiingo`) | optional user adapters | never a default; $0 constraint. |

---

## On curated quant-twitter / awesome-quant recommendations

Most frequently-promoted libraries (vectorbt, mlfinlab, mlflow/optuna, pandas-ta, openbb) either
conflict with our principles or are license traps for a free platform. The genuinely additive items
from that universe are the three ADDs above. Popularity is not a maintenance, license, or
architectural-fit signal — this document is the filter.
