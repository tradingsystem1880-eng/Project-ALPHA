# Project ALPHA — Python Architecture & AI-Agent Build Workflow

**Doc:** 07-architecture-ai-workflow
**Date:** 2026-06-14
**Scope:** Repository architecture, tooling, and development workflow for a $0/free, Python-first, single-user, institutional-grade quant research platform (backtest + statistical validation + paper trade) built primarily by Claude Code agents and maintained by a solo, non-senior-engineer owner.

---

## TL;DR — The Decisive Picks

| Decision | Pick | One-line reason |
|---|---|---|
| **Project layout** | **uv workspace ("monorepo") of small `src/`-layout packages** | Hard module boundaries are the single biggest reliability lever for AI agents; one lockfile, one venv. |
| **Dependency manager** | **`uv`** (Astral) | nautilus_trader *officially recommends uv and discourages conda*; TA-Lib now ships official binary wheels (no C build); 10–100× faster than poetry; free. |
| **Config** | **pydantic-settings `BaseSettings`** + TOML/`.env` | Validated, typed config; fail-fast on bad inputs; agents can't pass a string where a float belongs. |
| **Typing** | **Strict, gate-enforced** (`mypy --strict` or `pyright` in strict mode) | Types are machine-checkable contracts; they catch a large class of agent mistakes for free. |
| **DataFrame default** | **Polars** (Arrow-backed); pandas only at library edges | Faster, lower memory, *immutable + explicit* API that resists silent look-ahead bugs. |
| **Testing** | **pytest + Hypothesis**, with dedicated *bias-guard* test suites | Tests are the guardrail; AI writes code, tests prove it didn't cheat. |
| **Data versioning** | **Immutable Parquet snapshots + JSON manifest** (hash-addressed); DVC optional later | Lightest sound option for one person; zero infra; fully reproducible. |
| **Notebooks** | **marimo** for research (pure-`.py`, reactive, git-diffable); scripts/CLI for the production path | Kills hidden-state non-reproducibility; research never imports into prod. |
| **CI** | **GitHub Actions free tier**: lint + type + test + bias-guards on every push | A free, automated reviewer that never gets tired — critical when an AI writes the code. |
| **Build workflow** | **Interface-first, phase-gated, subagent-delegated** with a strong `CLAUDE.md` | Small files + explicit interfaces + verifiable tests = reliable agent edits. |

---

## 1. Project Layout — uv Workspace of Small Packages

### Recommendation: a **uv workspace** ("monorepo") of small, single-responsibility `src/`-layout packages.

**Why not a single flat package?** A solo owner *could* ship one `alpha/` package. But the dominant constraint here is **AI-agent reliability**, and the thing that most improves it is **hard, enforced module boundaries**. When `alpha-backtest` can only import `alpha-data` through its public interface (not reach into a sibling's internals), an agent editing the backtester physically cannot create a hidden dependency on, say, future-labeled data. Boundaries that are *structural* beat boundaries that are *conventional* — an agent will respect a real import error but will happily ignore a comment that says "don't import this."

**Why not separate repos (polyrepo)?** Cross-cutting changes (e.g., changing a `Bar` dataclass used everywhere) would require coordinated multi-repo PRs — punishing for one person and confusing for agents. A workspace gives you **one `uv.lock`, one virtualenv, one `git` history**, while still enforcing package boundaries. ([uv workspaces docs](https://docs.astral.sh/uv/concepts/projects/workspaces/))

**Why `src/` layout (not flat)?** The `src/` layout is the 2025/2026 consensus because it forces you to test against the *installed* package, not the source tree sitting in CWD — catching packaging bugs and accidental imports of un-shipped files. ([pytest good practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html))

> **uv workspace mechanics (confirmed):** A workspace is defined by a `[tool.uv.workspace]` table at the root; members are glob-matched dirs each with their own `pyproject.toml`; the whole workspace shares **one `uv.lock`**; member-to-member deps use `tool.uv.sources` with `{ workspace = true }` and are **editable** by default. Limitation: a workspace enforces a single `requires-python` (the intersection of members) and cannot stop a member from importing another member's transitive deps — so keep each member's deps honest. ([source](https://docs.astral.sh/uv/concepts/projects/workspaces/))

### The Annotated Directory Tree

```text
Project-ALPHA/
├── pyproject.toml                  # WORKSPACE ROOT. Virtual root: [tool.uv.workspace] + dev deps + tool config.
│                                   #   NOT a publishable package itself (package = false).
├── uv.lock                         # SINGLE lockfile for the whole workspace. Commit this.
├── .python-version                 # Pins CPython (e.g. 3.12) — vanilla CPython, per nautilus_trader guidance.
├── CLAUDE.md                       # The agent operating manual (see §9). Most important non-code file.
├── README.md
├── Makefile                        # or justfile — one-word commands: `make test`, `make check`, `make snapshot`.
├── .gitignore                      # ignores .venv/, data/raw/, __pycache__, .marimo, etc.
├── .pre-commit-config.yaml         # ruff + mypy/pyright run locally before every commit.
│
├── .github/
│   └── workflows/
│       └── ci.yml                  # lint → type → test → bias-guards. Free-tier GitHub Actions (§8).
│
├── .claude/                        # Claude Code project config (committed so the workflow is reproducible).
│   ├── agents/                     # Subagents (specialists) — see §9.
│   │   ├── strategy-author.md
│   │   ├── bias-auditor.md         # READ-ONLY auditor that hunts look-ahead/survivorship bugs.
│   │   ├── test-writer.md
│   │   └── data-engineer.md
│   ├── skills/                     # Reusable workflows invoked like tools — see §9.
│   │   ├── new-strategy/SKILL.md   # scaffold a strategy + its bias tests from a template.
│   │   ├── run-backtest/SKILL.md
│   │   └── add-data-source/SKILL.md
│   └── settings.json               # permissions, allowed tools, hooks (e.g. run ruff on save).
│
├── packages/                       # ── WORKSPACE MEMBERS (the actual code) ──
│   │
│   ├── alpha-core/                 # Shared kernel: domain types, protocols/interfaces, errors, time utils.
│   │   ├── pyproject.toml          #   Depends on NOTHING internal. Everything else depends on it.
│   │   └── src/alpha_core/
│   │       ├── __init__.py
│   │       ├── types.py            # Bar, Tick, Order, Fill, Position — frozen pydantic/dataclasses.
│   │       ├── interfaces.py       # Protocols: DataSource, Strategy, Broker, Validator (interface-first!).
│   │       ├── time.py             # Clock abstraction (PIT-safe "as-of" access lives here).
│   │       ├── enums.py
│   │       └── errors.py           # LookAheadError, SurvivorshipError, etc. (raised by guards).
│   │
│   ├── alpha-data/                 # Ingest, clean, point-in-time storage, snapshotting. Polars-first.
│   │   ├── pyproject.toml          #   deps: alpha-core, polars, pyarrow, pydantic-settings.
│   │   └── src/alpha_data/
│   │       ├── sources/            # one module per free provider (yfinance, stooq, etc.).
│   │       ├── universe.py         # survivorship-bias-free universe (includes delisted!).
│   │       ├── calendars.py        # trading calendars (exchange_calendars).
│   │       ├── snapshot.py         # write immutable Parquet + manifest (§6).
│   │       └── pit.py              # PointInTimeFrame: as_of(t) returns only rows with available_at <= t.
│   │
│   ├── alpha-backtest/             # Event-driven backtest engine + portfolio accounting.
│   │   ├── pyproject.toml          #   deps: alpha-core, alpha-data, polars, (optionally nautilus_trader).
│   │   └── src/alpha_backtest/
│   │       ├── engine.py           # the event loop; only ever sees data via Clock.as_of(t).
│   │       ├── portfolio.py
│   │       ├── execution.py        # fill models, slippage, costs.
│   │       └── metrics.py          # returns, Sharpe, drawdown, turnover.
│   │
│   ├── alpha-strategies/           # Strategy implementations (where most agent work happens).
│   │   ├── pyproject.toml          #   deps: alpha-core ONLY (strategies must not touch raw IO).
│   │   └── src/alpha_strategies/
│   │       ├── base.py             # Strategy ABC/Protocol impl helpers.
│   │       └── momentum/ ...        # one folder per strategy (small files!).
│   │
│   ├── alpha-validation/           # Statistical validation: the "is this real or luck?" layer.
│   │   ├── pyproject.toml          #   deps: alpha-core, numpy, scipy, statsmodels.
│   │   └── src/alpha_validation/
│   │       ├── walkforward.py      # walk-forward / purged k-fold w/ embargo (CPCV).
│   │       ├── deflated_sharpe.py  # deflated/PSR; multiple-testing correction.
│   │       ├── mc.py               # Monte Carlo / bootstrap, reality check.
│   │       └── reports.py
│   │
│   └── alpha-paper/                # Paper-trading runner (live-ish loop, no real money).
│       ├── pyproject.toml          #   deps: alpha-core, alpha-data, alpha-strategies, (nautilus_trader).
│       └── src/alpha_paper/
│           ├── runner.py           # reuses the SAME Strategy interface as backtest (parity!).
│           └── broker_paper.py
│
├── apps/                           # Thin entry points (CLIs). Logic lives in packages, not here.
│   └── alpha-cli/
│       ├── pyproject.toml
│       └── src/alpha_cli/main.py   # `alpha backtest ...`, `alpha snapshot ...` (Typer).
│
├── tests/                          # Workspace-wide tests (mirrors package structure). See §5.
│   ├── conftest.py                 # shared fixtures (synthetic OHLCV, calendars, tmp snapshots).
│   ├── fixtures/                   # reusable fixture data + builders.
│   ├── unit/                       # per-module unit tests.
│   ├── property/                   # Hypothesis property tests (invariants).
│   ├── bias_guards/                # ⭐ DEDICATED look-ahead & survivorship tests (§5). The crown jewels.
│   └── integration/               # end-to-end: snapshot → backtest → validate.
│
├── research/                       # marimo notebooks + findings. NEVER imported by packages. (§7)
│   ├── notebooks/                  # *.py marimo notebooks (git-diffable).
│   ├── reports/                    # generated HTML/MD outputs.
│   └── 07-architecture-ai-workflow.md   # (this document)
│
├── data/                           # Git-ignored data root (snapshots are immutable & hash-named). (§6)
│   ├── raw/                        # raw provider pulls (ignored).
│   ├── snapshots/                  # immutable Parquet datasets, e.g. snapshots/2026-06-14_a1b2c3/.
│   └── manifests/                  # JSON manifests (hashes, row counts, provenance) — COMMITTED.
│
└── docs/
    ├── adr/                        # Architecture Decision Records (short, one per decision).
    └── interfaces.md               # human-readable contract reference for agents.
```

**Root `pyproject.toml` (sketch):**

```toml
[project]
name = "project-alpha"
version = "0.0.0"
requires-python = ">=3.12"

[tool.uv.workspace]
members = ["packages/*", "apps/*"]

[tool.uv.sources]
# all internal packages resolved from the workspace, editable:
alpha-core        = { workspace = true }
alpha-data        = { workspace = true }
alpha-backtest    = { workspace = true }
alpha-strategies  = { workspace = true }
alpha-validation  = { workspace = true }
alpha-paper       = { workspace = true }

[dependency-groups]
dev = ["pytest", "pytest-cov", "pytest-xdist", "hypothesis", "mypy", "ruff"]

[tool.ruff]
line-length = 100
[tool.ruff.lint]
select = ["E","F","I","UP","B","SIM","PD","NPY","RUF"]  # incl. pandas/numpy lints

[tool.mypy]
strict = true
[tool.pytest.ini_options]
addopts = "--import-mode=importlib --strict-markers --strict-config"
markers = ["bias_guard: tests that detect look-ahead/survivorship bias"]
```

> **Pragmatic note:** Start with **`alpha-core`, `alpha-data`, `alpha-backtest`** as real members on day one; the others can begin as sub-packages and be "promoted" to workspace members when they grow. The workspace makes promotion cheap (move a dir, add a `pyproject.toml`, add a `workspace = true` source).

---

## 2. Environment & Dependency Management — **Pick: `uv`**

### The verdict: **uv**, decisively. Not poetry, not conda/mamba.

This used to be a genuinely hard call because the heavy quant/scientific libraries historically installed more reliably under conda. **That argument has collapsed in 2025**, and the two libraries that mattered most for this project now point straight at uv:

1. **nautilus_trader** (the production-grade engine you'll likely use for the event-driven core / paper trading): the official docs state *"We highly recommend installing using the uv package manager with a 'vanilla' CPython,"* support **Python 3.12–3.14**, and explicitly say *"Conda and other Python distributions may work but aren't officially supported."* ([NautilusTrader install](https://nautilustrader.io/docs/latest/getting_started/installation/)). Install: `uv pip install nautilus_trader` (or `--index-url=https://packages.nautechsystems.io/simple` for their wheel index).

2. **TA-Lib** (the historical poster child for "you must use conda"): as of **version 0.6.5 (official wheels landed on PyPI Aug 2025)**, prebuilt binary wheels bundle the underlying C library for Linux/macOS/Windows × x86_64/arm64, Python 3.9–3.14. *You no longer need to install the C library or compile anything* — `pip install TA-Lib` (hence `uv add ta-lib`) just works. ([TA-Lib README](https://github.com/TA-Lib/ta-lib-python), [PyPI](https://pypi.org/project/TA-Lib/)). The whole scientific stack (numpy, scipy, pandas, polars, statsmodels, scikit-learn) has shipped manylinux/macos/win wheels for years.

So the historical conda advantage (binary distribution of compiled libs) is now matched by PyPI wheels, while uv keeps conda's speed-of-resolution benefit **and** is fully `pyproject.toml`/PEP-standard native.

**Why uv over poetry (the only real alternative now):**
- **Speed:** uv resolves/installs 10–100× faster (Rust). For a solo dev iterating with agents, fast `uv sync`/`uv lock` is a quality-of-life multiplier — and CI minutes are free-tier-finite.
- **First-class workspaces:** uv has native workspace support with a single lockfile (§1). Poetry's multi-package story is weaker.
- **One tool:** uv also manages **Python versions** (`uv python install 3.12`), runs tools (`uvx ruff`), and replaces pip/pip-tools/pipx/pyenv. Fewer moving parts = fewer things a solo owner (or agent) can misconfigure.
- **Dependency groups** (`[dependency-groups]`, PEP 735) for dev tooling, separate from runtime deps. ([uv docs](https://docs.astral.sh/uv/))

**Why not conda/mamba:** heavier, slower for a single-user pure-Python project, non-standard env files, and — critically — *not recommended by your most important dependency (nautilus_trader)*. Reserve conda only if you later adopt a library that ships **conda-only** binaries (rare in this stack; none of your core libs do).

**The one caveat (be honest):** if you build nautilus_trader *from source* (you won't normally — use the wheels), you'd need the Rust toolchain + clang. Using the published wheels via uv avoids all of that.

**Day-1 commands:**
```bash
uv python install 3.12
uv init --no-package            # or scaffold the workspace root by hand
uv add polars pyarrow pydantic pydantic-settings typer
uv add nautilus_trader ta-lib   # wheels; no compilers needed
uv add --group dev pytest hypothesis mypy ruff pytest-cov pytest-xdist
uv sync                          # creates .venv, installs everything from uv.lock
```

---

## 3. Config & Typing

### Config: **pydantic-settings `BaseSettings`** (TOML + `.env` + env vars), validated.

Configuration is a classic place where AI-written code goes wrong silently: a string `"0.001"` used where a float `0.001` is expected, a missing key defaulting to `None`, a typo'd env var. **pydantic-settings makes config a typed, validated object that fails loudly at startup**, not deep inside a backtest at 2 a.m.

```python
# packages/alpha-core/src/alpha_core/config.py
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class CostModel(BaseModel):
    commission_bps: float = Field(ge=0)        # validated: can't be negative
    slippage_bps: float = Field(ge=0)

class BacktestSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ALPHA_",
        env_nested_delimiter="__",   # ALPHA_COSTS__COMMISSION_BPS=1.0
    )
    start: str
    end: str
    initial_cash: float = Field(gt=0)
    costs: CostModel
    seed: int = 42                    # reproducibility: a single seed for the whole run
```
Env vars (`ALPHA_INITIAL_CASH=100000`, `ALPHA_COSTS__COMMISSION_BPS=1.0`) and `.env` are read automatically; type coercion + validation are free. ([pydantic-settings docs](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/)). For experiment configs prefer **TOML committed next to the run** (reproducibility) via a `TomlConfigSettingsSource` in `settings_customise_sources`.

**Rule:** every run is fully described by one config object + one data snapshot id + one seed. That triple is your reproducibility unit (§6).

### Typing: **strict, and enforced by CI** (`mypy --strict` or `pyright` strict).

Strong typing is not bureaucracy here — **it is the cheapest guardrail for AI-generated code.** Three concrete payoffs:

1. **Types are machine-checkable contracts between modules.** When `alpha_core.interfaces.Strategy` declares `def on_bar(self, bar: Bar) -> list[Order]`, an agent implementing a strategy gets an immediate, local error if it returns the wrong shape — no need for a human to notice.
2. **They make agent edits *local and safe*.** With small typed modules, an agent changing `metrics.py` can be checked in isolation; the type checker flags every call site that the change breaks. This is what lets you trust agent refactors.
3. **They encode domain semantics.** Use `NewType`/branded types to make look-ahead bias *type-incorrect*: e.g. `AsOf = NewType("AsOf", datetime)` and a `PITFrame.as_of(t: AsOf) -> Frame` so that "give me data" requires you to name the timestamp you're allowed to see (see §5).

**Why small modules + strong types specifically help agents:** an LLM edits most reliably when (a) the file it must change fits comfortably in context, (b) the contract it must honor is explicit in the signature, and (c) a fast checker tells it immediately when it's wrong. Small typed modules give all three. Big, dynamically-typed files give none.

Tooling: **`ruff`** for lint+format (single fast tool), **`mypy --strict`** *or* **`pyright`** for types (pyright is faster and has great inference; mypy is the de-facto standard — pick one and make it a CI gate). Run both via **pre-commit** so issues never reach a commit.

---

## 4. Data Handling Default — **Polars** (pandas at the edges)

### Default: **Polars** (Apache Arrow-backed). Use pandas only where a third-party lib demands it.

**Why Polars is the right *default* for this project specifically:**
- **Speed & memory:** Rust + Arrow columnar layout → faster joins/filters/group-bys and lower RAM, which matters for multi-year, multi-asset panels on a single machine. ([Real Python](https://realpython.com/polars-vs-pandas/), [Flowfile](https://flowfile.io/blog/polars-vs-pandas-2026/))
- **It resists look-ahead bias by design.** Polars DataFrames are **immutable** and the API is **explicit**: no chained in-place mutation, no silent index alignment, no ambiguous `df.shift()` on a hidden index. Expressions are declarative (`pl.col("close").shift(1).over("symbol")`), so "use yesterday's close, per symbol" is written *explicitly and per-group* — exactly the discipline that prevents leakage. pandas' implicit index alignment and `inplace=` mutations are a frequent source of subtle leakage and of bugs an agent won't notice.
- **Lazy engine for free correctness/perf:** `pl.scan_parquet(...).filter(...).collect()` lets you push down predicates over big snapshots without loading everything.
- **Arrow interop:** zero-copy to/from pandas, DuckDB, PyArrow; you can hand Arrow tables to any consumer. So choosing Polars doesn't lock you out of the ecosystem.

**When to use pandas (the honest exceptions):**
- A required library only speaks pandas (e.g. `statsmodels`, some `scikit-learn` flows, certain plotting). Convert at the boundary: `df.to_pandas()` / `pl.from_pandas()`.
- You're pasting in legacy/research pandas code that isn't a bottleneck and isn't on the production path (research notebooks are fine; just don't let pandas leak into `alpha-backtest`/`alpha-data` core paths).

**Rule of thumb:** *Polars everywhere in `packages/`; pandas allowed only in `research/` and at explicit library boundaries, with a `to_pandas()`/`from_pandas()` conversion you can see.* Store all on-disk data as **Parquet** (Arrow-native, columnar, typed) — the lingua franca for both engines.

---

## 5. Testing — Tests as the Guardrail for AI Code

This is the heart of the institutional-grade bar for a solo owner: **the AI writes the code; the tests prove it didn't cheat.** Layout follows the `src/`-layout consensus — package in `src/`, tests in a sibling `tests/`, importlib import mode, fixtures in `conftest.py`/`fixtures/`. ([pytest good practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html))

### 5a. Layout & fixtures
- `tests/unit/` (per-module), `tests/property/` (Hypothesis), `tests/integration/` (end-to-end), and the dedicated **`tests/bias_guards/`**.
- `conftest.py` provides **synthetic, fully-known fixtures**: a deterministic OHLCV generator (seeded), a tiny fake trading calendar, a tmp snapshot dir. Synthetic data is essential — with a *known* generating process you can assert exact expected outcomes and engineer leakage traps.
- `pyproject.toml`: `addopts = "--import-mode=importlib --strict-markers"`, a registered `bias_guard` marker, `pytest-xdist` for parallel, `pytest-cov` for coverage.

### 5b. Property-based testing with **Hypothesis** — encode market invariants
Markets are full of invariants Hypothesis can hammer with thousands of generated cases ([Hypothesis](https://github.com/HypothesisWorks/hypothesis), [PBT + financial data](https://www.susanpotter.net/quant/property-based-testing-statistical-validation/)):
- **OHLC consistency:** for every generated bar, `low <= open,close <= high` and `low <= high`.
- **Monotonic timestamps:** any series your loaders emit is strictly time-ordered, no dupes.
- **Non-negative spreads / prices / volumes.**
- **Accounting identities:** `cash + Σ(position·price) == equity` after every fill (and a **stateful** `RuleBasedStateMachine` that applies random buy/sell/mark sequences and asserts the ledger never goes inconsistent or negative-where-impossible).
- **Corporate-action continuity:** adjusted-price series are continuous across splits/dividends.

```python
from hypothesis import given, strategies as st

@given(prices=st.lists(st.floats(1, 1e4, allow_nan=False), min_size=2))
def test_returns_are_inverse_of_cumprod(prices):
    # property: reconstructing prices from returns recovers the originals
    ...
```

### 5c. ⭐ Tests that specifically catch **look-ahead bias** (the key question)

Look-ahead bias = using information at time *t* that wasn't *available* at *t*. The defense is **structural + tested**, in four layers:

**Pattern 1 — Point-in-Time (PIT) data access is the *only* legal door.**
Make the engine physically unable to see the future. Data is wrapped so the *only* accessor is `as_of(t)`, which returns rows whose `available_at <= t`. There is **no** raw `df` handed to strategies.
```python
# the guard, in alpha-data/pit.py
class PointInTimeFrame:
    def as_of(self, t: AsOf) -> pl.DataFrame:
        return self._df.filter(pl.col("available_at") <= t)
```
*Test:* call `as_of(t)` and assert **every** returned `available_at <= t`; assert that requesting a field with a future `available_at` raises `LookAheadError`. Hypothesis-generate random `t` across the panel.

**Pattern 2 — The "future poison" / sentinel test (the highest-signal trick).**
Build a fixture where **all data strictly after a cutoff is poisoned** — replaced with `NaN`, `inf`, or absurd sentinels (e.g. price = 1e12). Run the strategy/backtest *up to the cutoff*. **If any output, signal, or metric is affected by the poison, the code peeked.** This catches leakage no static check can.
```python
@pytest.mark.bias_guard
def test_no_lookahead_via_future_poison(strategy, panel):
    poisoned = panel.with_columns(
        pl.when(pl.col("ts") > CUTOFF).then(float("nan")).otherwise(pl.col("close")).alias("close")
    )
    sig_clean    = strategy.run(panel.up_to(CUTOFF))
    sig_poisoned = strategy.run(poisoned.up_to(CUTOFF))
    assert sig_clean.equals(sig_poisoned)   # future data must NOT change the past
```

**Pattern 3 — Causality / shift test for features.**
For any feature/indicator `f`, assert it depends only on `x[:t]`: recompute `f` on a series truncated at each `t` and assert it equals the full-series `f` at `t`. Equivalent guard: a signal generated at bar *t* may only be *acted on* at *t+1* (the engine enforces a one-bar delay between signal and fill; test that a same-bar fill is impossible).

**Pattern 4 — Walk-forward / purged-embargo validation, tested for leakage.**
In `alpha-validation`, use **purged k-fold with an embargo** (López de Prado's CPCV): assert no training index falls within the embargo window around any test index. *Test the validator itself*: feed overlapping folds and assert it raises if train/test windows touch. This stops leakage *across* the validation split, not just within a single backtest.

> **Make these `@pytest.mark.bias_guard` and run them in CI on every push.** They are the contract that an agent's clever-looking strategy isn't secretly cheating.

### 5d. Tests that catch **survivorship bias**
- **Universe-completeness assertion:** the as-of universe for a past date **must include securities later delisted**. *Test:* with a fixture universe containing a security delisted before "today," assert it appears in `universe.as_of(past_date)` and is *absent* from `universe.as_of(today)`. A backtest that silently uses only currently-listed names will fail this.
- **No look-back-from-survivors:** assert the backtest's tradable set at date *d* is derived from `universe.as_of(d)`, never from the full current membership.
- **Delisting handling:** assert positions in a security are force-closed/handled at its delist date (no "frozen" survivors inflating returns).

### 5e. How tests become the guardrail for AI code
1. **TDD-by-interface:** for each module, the *interface* and its tests (incl. bias guards) are written/approved **before** the implementation. The agent then codes to green tests.
2. **Bias guards are non-negotiable CI gates.** A PR that adds a strategy without passing `bias_guards` cannot merge.
3. **A read-only `bias-auditor` subagent** (§9) reviews diffs specifically for `shift(-n)`, `.iloc[-1]` on full series, `.rolling(...).mean()` without causality, `df.dropna()` that drops *future* rows, `train_test_split` without time ordering, etc. — and proposes a failing test when it finds a smell.
4. **Coverage floor + mutation sanity (optional):** keep coverage high on engine/accounting; periodically run `mutmut`/`cosmic-ray` on `metrics.py`/`portfolio.py` to confirm tests actually bite.

---

## 6. Reproducibility & Data Versioning — **Immutable Parquet Snapshots + Manifest**

### Pick: **immutable, content-addressed Parquet snapshots + a committed JSON manifest.** Add DVC only if/when you outgrow it.

For **one person, $0, and reproducibility-over-everything**, the lightest *sound* design is:

1. **Every dataset write is immutable.** Pull raw → clean → write to `data/snapshots/<date>_<shorthash>/...parquet`. Never mutate a snapshot; new data = new snapshot dir.
2. **A manifest describes the snapshot** and is **committed to git** (small JSON): dataset id, creation time, source + version, row counts per file, **content hash (sha256) of each Parquet file**, the universe/date range, and the code git-SHA that produced it.
3. **A run is reproducible from a triple:** `(snapshot_id, config.toml, seed)`. Backtests record this triple in their output. Re-running the same triple reproduces results bit-for-bit (deterministic seed; no wall-clock or `random` without seed).

```jsonc
// data/manifests/2026-06-14_a1b2c3.json   (committed)
{
  "snapshot_id": "2026-06-14_a1b2c3",
  "created_utc": "2026-06-14T12:00:00Z",
  "source": {"provider": "stooq", "endpoint": "daily", "pull_sha": "..."},
  "git_sha": "e4f5a6...",
  "universe": "us_equity_incl_delisted",
  "date_range": ["2005-01-01", "2026-06-13"],
  "files": [
    {"path": "ohlcv.parquet", "rows": 18234110, "sha256": "a1b2c3..."}
  ]
}
```

**Why not DVC (yet)?** DVC is the *next* step up and a fine, Git-native, serverless choice for solo/small projects ([lakeFS comparison](https://lakefs.io/blog/dvc-vs-git-vs-dolt-vs-lakefs/)). But two things argue for the manifest approach *first*: (1) it's **zero new tooling/infra** — just Parquet + JSON + hashes you already understand; (2) **note the 2025 stewardship change — lakeFS acquired DVC (Nov 2025)** ([search summary](https://startupstash.com/top-data-versioning-tools/)), so it's reasonable to avoid taking a hard dependency until you actually need remote/large-blob versioning. When your snapshots get big or you want push/pull to cheap object storage, layering DVC *on top of the same immutable-snapshot directories* is a clean, non-disruptive upgrade.

**Why not lakeFS?** It's excellent but is a **server/object-store platform** built for petabytes/teams — overkill and over-budget-of-complexity for a single user.

**Reproducibility checklist (institutional-grade, solo-sized):** pinned `uv.lock` + `.python-version`; committed config TOML per run; single `seed`; immutable hashed snapshots; manifest committed; backtest outputs stamped with `(snapshot_id, config_hash, git_sha, seed)`.

---

## 7. Notebooks vs Scripts — **marimo for research, scripts/CLI for production**

### Research: **marimo.** Production path: plain modules + Typer CLI. Never let research import into packages.

**Why marimo over Jupyter for this project:**
- **Reproducibility by construction.** Jupyter's hidden execution order is a documented reproducibility disaster (a large-scale study found only ~24% of GitHub notebooks even re-ran in order, ~4% reproduced results). marimo is a **reactive dataflow graph**: changing a cell re-runs (or marks stale) its dependents, so **there is no hidden state** and outputs always match code. ([marimo dataflow](https://marimo.io/blog/dataflow), [vs Jupyter](https://marimo.io/features/vs-jupyter-alternative))
- **Git-native.** marimo notebooks are **pure `.py` files**, so they diff and review like normal code — perfect when an agent edits them and you review the PR. Jupyter's JSON blobs (with embedded outputs) are painful to diff/review. ([marimo](https://github.com/marimo-team/marimo))
- **Executable both ways:** a marimo notebook can run as a script (`python notebook.py`) or be served as an app — so the *same* research artifact can be parameterized and re-run for reproducibility.

**Keeping research out of the production path (critical discipline):**
- `research/` is a **leaf**: packages must never `import` from it (enforce with a ruff/import-linter rule and a CI check). Research *uses* `packages/`, not vice versa.
- Any code that proves useful in a notebook gets **promoted** into a package (with tests + types) before it's relied on — the notebook then imports the package. Notebooks explore; packages are the source of truth.
- Notebooks read from **snapshots by id** (not live pulls) so research is reproducible too.

*(If you ever need a hosted/standard `.ipynb` for sharing, use `jupytext`/marimo export — but the working format stays `.py`.)*

---

## 8. CI — GitHub Actions (Free Tier) Worth Having

Even solo, CI is **a tireless reviewer for AI-written code** — and free for public repos / generous for private. One workflow, fast, gating:

```yaml
# .github/workflows/ci.yml
name: ci
on: [push, pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4          # official uv action; caches the venv
        with: { enable-cache: true }
      - run: uv python install 3.12
      - run: uv sync --all-extras
      - run: uv run ruff check . && uv run ruff format --check .
      - run: uv run mypy .                    # strict types as a gate
      - run: uv run pytest -m "not integration" -n auto --cov
      - run: uv run pytest -m bias_guard      # ⭐ bias guards as an explicit, named gate
```

**What's worth having for a solo quant repo:**
- **The four gates:** format/lint (ruff) → types (mypy/pyright) → tests → **bias_guards** (run as their own step so a failure is unmistakable).
- **uv cache** via `astral-sh/setup-uv` to keep runs fast and within free minutes.
- **Branch protection** on `main` requiring the `check` job to pass (so an agent's PR can't merge red).
- **(Optional, free) Dependabot/`uv lock --upgrade` weekly** to catch security updates; **CodeQL** for basic SAST.
- **(Optional) Nightly scheduled run** of the full integration suite + a canary backtest to detect drift.
- Pin actions to major versions; keep secrets out (no real broker keys — paper only).

---

## 9. AI-Agent Build Workflow — Building ALPHA Reliably in Phases

The architecture above exists to serve **one goal: make Claude Code agents build this reliably.** Five principles, then the concrete phase decomposition.

### 9.1 The five reliability principles (and how the repo encodes them)
1. **Interface-first.** Define the Protocols in `alpha-core/interfaces.py` *before* implementations. An agent implements against a fixed contract; the type checker + tests verify conformance. This is the single biggest lever.
2. **Small, focused files.** One responsibility per module; keep files small enough to fit in an agent's working context with room to edit. (`alpha-strategies/momentum/` with several small files beats one 800-line `strategies.py`.)
3. **Strong types + docstrings as the spec.** Every public function: typed signature + a docstring stating *what it guarantees* (incl. "PIT-safe: only reads data ≤ t"). The docstring is the prompt the next agent reads.
4. **Tests are the acceptance criteria.** Especially the **bias_guards** — they turn "looks right" into "provably didn't cheat." Agents code to green tests.
5. **Structural boundaries over conventions.** The workspace's import graph (strategies can't touch raw IO; research can't be imported) makes whole classes of mistakes *impossible*, not merely discouraged.

### 9.2 `CLAUDE.md` — the agent operating manual (the most important non-code file)
Keep it tight and high-signal (agents read it every session). Contents:
- **Mission & hard constraints** ($0/free, Python 3.12, Polars-first, paper-only).
- **Commands:** `uv sync`, `make test`, `make check`, `make snapshot`, `uv run pytest -m bias_guard`.
- **Architecture map:** the package graph + the rule "strategies depend only on `alpha-core`; nothing imports `research/`."
- **The bias doctrine:** "All data access is via `PointInTimeFrame.as_of(t)`. Never hand a raw DataFrame to a strategy. Every new feature/strategy ships with a `future-poison` bias test." (Make this loud.)
- **Definition of done:** ruff clean, mypy strict clean, unit + property + **bias_guard** green, docstrings present.
- **Conventions:** Polars over pandas; pydantic-settings for config; immutable snapshots; one seed per run.
- **Pointers** to `docs/interfaces.md` and `docs/adr/` rather than duplicating them.
Keep it current with the `/init` and "revise CLAUDE.md" workflows; prune aggressively. ([Claude Code best practices](https://www.anthropic.com/engineering/claude-code-best-practices))

### 9.3 Subagents, Skills, and Plan Mode — how to actually drive the build
- **Plan Mode first, always.** For each phase/feature, have Claude produce a **written plan** (files to touch, interfaces, tests) and approve it *before* code. Planning before coding is the most-cited best practice. ([Anthropic](https://www.anthropic.com/engineering/claude-code-best-practices), [DataCamp](https://www.datacamp.com/tutorial/claude-code-best-practices))
- **Subagents (`.claude/agents/`)** = specialists in isolated context, keeping the main thread clean:
  - `data-engineer` — sources, snapshotting, PIT layer.
  - `strategy-author` — implements strategies against `alpha-core` interfaces only.
  - `test-writer` — writes unit/property/bias tests *first*.
  - **`bias-auditor` (read-only)** — reviews diffs for look-ahead/survivorship smells and proposes failing tests. Give it no write tools.
  Delegate research/exploration to subagents ("use a subagent to investigate X") so context stays focused. ([best practices](https://rosmur.github.io/claudecode-best-practices/))
- **Skills (`.claude/skills/`)** = repeatable workflows invoked like tools:
  - `new-strategy` — scaffolds a strategy folder *plus its bias-guard tests* from a template (so every strategy is born with guards).
  - `run-backtest` — runs a backtest from `(snapshot_id, config, seed)` and stamps outputs.
  - `add-data-source` — scaffolds a new provider module + ingestion test + snapshot wiring.
- **Verification is the highest-leverage thing.** Every loop ends with `make check` + `pytest -m bias_guard`. *"Give Claude a way to verify its work"* is the single best reliability practice ([Anthropic](https://www.anthropic.com/engineering/claude-code-best-practices)) — your test suite is that mechanism.

### 9.4 Decomposing the 6 build phases into agent-sized tasks
Each phase is **interface → tests (incl. bias guards) → implementation → verify (CI green) → ADR**. Phases are sequential; tasks within a phase are agent-sized (one module / one PR).

**Phase 0 — Scaffold & rails.** Create the uv workspace + `alpha-core` (types, interfaces, errors), `CLAUDE.md`, ruff/mypy config, pytest skeleton, CI, `Makefile`, pre-commit. *Done when:* empty packages import, CI is green on an empty test. *(Mostly human + one setup agent; everything downstream rides these rails.)*

**Phase 1 — `alpha-data` + reproducibility spine.** Implement one free source, calendars, the **PIT layer**, and immutable snapshot+manifest. Agent tasks: `sources/<provider>.py`, `calendars.py`, `pit.py`, `snapshot.py` — each with unit + property tests; **bias guards: PIT `as_of` correctness, survivorship-complete universe.** *Done when:* you can produce a hashed snapshot and `as_of(t)` provably hides the future.

**Phase 2 — `alpha-backtest` engine.** Event loop (data only via `Clock.as_of`), portfolio accounting, execution/costs, metrics. Agent tasks per module + the accounting **stateful Hypothesis** test and the **future-poison** end-to-end guard. *Done when:* a trivial strategy backtests and all bias guards pass.

**Phase 3 — `alpha-strategies`.** `base.py`, then strategies one folder at a time via the `new-strategy` skill (each born with bias tests). Agent tasks = one strategy per PR. *Done when:* ≥1 strategy runs end-to-end, guards green.

**Phase 4 — `alpha-validation`.** Walk-forward, **purged k-fold + embargo (CPCV)**, deflated Sharpe/PSR, Monte Carlo/bootstrap, reports. Agent tasks per method + **tests that the validator itself rejects leaky splits**. *Done when:* a strategy produces a deflated, multiple-testing-aware verdict.

**Phase 5 — `alpha-paper` + `alpha-cli`.** Paper runner reusing the *same* `Strategy` interface (backtest/live parity), paper broker, and the Typer CLI (`alpha snapshot|backtest|validate|paper`). Agent tasks: `runner.py`, `broker_paper.py`, CLI commands + a **parity test** (same signals in backtest vs paper on identical data). *Done when:* a strategy paper-trades on a schedule, reproducibly.

> **Cadence:** one phase → review → merge → `/clear` context → next phase. Within a phase, dispatch independent modules to subagents in parallel where they don't share state; serialize where they do.

---

## Sources
- uv workspaces — https://docs.astral.sh/uv/concepts/projects/workspaces/
- uv (overview / dependency groups / settings) — https://docs.astral.sh/uv/
- NautilusTrader installation (recommends uv, Py 3.12–3.14, conda discouraged) — https://nautilustrader.io/docs/latest/getting_started/installation/
- TA-Lib python (official binary wheels since 0.6.5) — https://github.com/TA-Lib/ta-lib-python and https://pypi.org/project/TA-Lib/
- pydantic-settings — https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/
- Polars vs pandas — https://realpython.com/polars-vs-pandas/ and https://flowfile.io/blog/polars-vs-pandas-2026/
- pytest good practices (src layout, importlib) — https://docs.pytest.org/en/stable/explanation/goodpractices.html
- Hypothesis (property-based / stateful) — https://github.com/HypothesisWorks/hypothesis and https://www.susanpotter.net/quant/property-based-testing-statistical-validation/
- Look-ahead bias detection — https://mikeharrisny.medium.com/look-ahead-bias-in-backtests-and-how-to-detect-it-ad5e42d97879 and https://medium.com/auquan/backtesting-biases-and-how-to-avoid-them-776180378335
- Data versioning (DVC/lakeFS; DVC acquired by lakeFS Nov 2025) — https://lakefs.io/blog/dvc-vs-git-vs-dolt-vs-lakefs/ and https://startupstash.com/top-data-versioning-tools/
- marimo (reactive, reproducible, pure-.py) — https://marimo.io/blog/dataflow and https://marimo.io/features/vs-jupyter-alternative and https://github.com/marimo-team/marimo
- Claude Code best practices (planning, subagents, skills, verification) — https://www.anthropic.com/engineering/claude-code-best-practices and https://rosmur.github.io/claudecode-best-practices/
