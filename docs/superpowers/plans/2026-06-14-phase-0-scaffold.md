# Phase 0 — Rails + Walking Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a CI-green `uv` workspace for Project ALPHA with all six package boundaries wired, the architecture enforced by import-linter, typed config, a working CLI, and the bias-guard test harness — proven end-to-end by a walking skeleton.

**Architecture:** A `uv` workspace ("monorepo") of small `src/`-layout packages with hard import boundaries (`alpha_core` at the bottom, `alpha_cli` at the top). The dependency DAG is enforced mechanically by `import-linter` in CI, not by convention. Phase 0 ships no trading logic — only the rails (CI, types, config, test harness) that every later phase is built inside.

**Tech Stack:** Python 3.12 · uv (workspace + deps) · pydantic / pydantic-settings · typer (CLI) · pytest + Hypothesis · ruff · mypy (strict) · import-linter · GitHub Actions.

**Dependency DAG (enforced):**
- `alpha_core` → (nothing internal)
- `alpha_data` → `alpha_core`
- `alpha_strategies` → `alpha_core`
- `alpha_backtest` → `alpha_core`, `alpha_data`
- `alpha_validation` → `alpha_core`
- `alpha_cli` → all of the above

**Prerequisite:** `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`). Verify: `uv --version`.

---

## File Map (created in this plan)

```
Project-ALPHA/
├── .gitignore
├── pyproject.toml                                   # uv workspace root + tool config
├── CLAUDE.md                                        # build conventions for AI agents
├── .github/workflows/ci.yml                         # ruff → mypy → lint-imports → pytest
├── packages/
│   ├── alpha-core/
│   │   ├── pyproject.toml
│   │   └── src/alpha_core/{__init__,errors,types,protocols,config}.py
│   ├── alpha-data/
│   │   ├── pyproject.toml
│   │   └── src/alpha_data/{__init__,placeholder}.py
│   ├── alpha-strategies/
│   │   ├── pyproject.toml
│   │   └── src/alpha_strategies/{__init__,placeholder}.py
│   ├── alpha-backtest/
│   │   ├── pyproject.toml
│   │   └── src/alpha_backtest/{__init__,placeholder}.py
│   └── alpha-validation/
│       ├── pyproject.toml
│       └── src/alpha_validation/{__init__,placeholder}.py
├── apps/alpha-cli/
│   ├── pyproject.toml
│   └── src/alpha_cli/{__init__,main}.py
└── tests/
    ├── unit/test_core_types.py
    ├── integration/test_cli_walking_skeleton.py
    └── bias_guards/test_future_poison_pattern.py
```

---

## Task 0: Initialize git and commit existing artifacts

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Initialize the repository**

Run:
```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA
git init -b main
```
Expected: `Initialized empty Git repository ...`

- [ ] **Step 2: Create `.gitignore`**

Create `.gitignore`:
```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/

# Tooling caches
.venv/
.mypy_cache/
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/

# uv
# (uv.lock IS committed — do not ignore it)

# Env / secrets
.env

# Data is large + reproducible from snapshots; never commit it
data/
```

- [ ] **Step 3: Commit the existing research + spec (pre-scaffold baseline)**

Run:
```bash
git add .gitignore "Building Elite AI Trading Software.md" research/ docs/
git commit -m "chore: baseline — research dossier, v1 spec, and phase-0 plan"
```
Expected: a commit containing the 8 research files, the spec, this plan, and `.gitignore`.

---

## Task 1: uv workspace root + tool configuration

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 1: Create the workspace root `pyproject.toml`**

Create `pyproject.toml`:
```toml
[project]
name = "project-alpha"
version = "0.0.0"
description = "Personal quantitative research platform (backtest + validation + paper)."
requires-python = ">=3.12"
dependencies = [
    "alpha-core",
    "alpha-data",
    "alpha-strategies",
    "alpha-backtest",
    "alpha-validation",
    "alpha-cli",
]

[tool.uv]
package = false  # virtual workspace root; not itself an installable package

[tool.uv.workspace]
members = ["packages/*", "apps/*"]

[tool.uv.sources]
alpha-core = { workspace = true }
alpha-data = { workspace = true }
alpha-strategies = { workspace = true }
alpha-backtest = { workspace = true }
alpha-validation = { workspace = true }
alpha-cli = { workspace = true }

[dependency-groups]
dev = [
    "pytest>=8",
    "hypothesis>=6",
    "mypy>=1.11",
    "ruff>=0.6",
    "import-linter>=2.1",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]

[tool.ruff.lint.isort]
known-first-party = ["alpha_core", "alpha_data", "alpha_strategies", "alpha_backtest", "alpha_validation", "alpha_cli"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_unused_configs = true
plugins = ["pydantic.mypy"]
explicit_package_bases = true

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "bias_guard: tests that mechanically prevent look-ahead / survivorship bias (gated in CI)",
]

[tool.importlinter]
root_packages = [
    "alpha_core",
    "alpha_data",
    "alpha_strategies",
    "alpha_backtest",
    "alpha_validation",
    "alpha_cli",
]

[[tool.importlinter.contracts]]
name = "alpha_core imports nothing internal"
type = "forbidden"
source_modules = ["alpha_core"]
forbidden_modules = ["alpha_data", "alpha_strategies", "alpha_backtest", "alpha_validation", "alpha_cli"]

[[tool.importlinter.contracts]]
name = "alpha_data depends only on core"
type = "forbidden"
source_modules = ["alpha_data"]
forbidden_modules = ["alpha_strategies", "alpha_backtest", "alpha_validation", "alpha_cli"]

[[tool.importlinter.contracts]]
name = "alpha_strategies depends only on core"
type = "forbidden"
source_modules = ["alpha_strategies"]
forbidden_modules = ["alpha_data", "alpha_backtest", "alpha_validation", "alpha_cli"]

[[tool.importlinter.contracts]]
name = "alpha_validation depends only on core"
type = "forbidden"
source_modules = ["alpha_validation"]
forbidden_modules = ["alpha_data", "alpha_strategies", "alpha_backtest", "alpha_cli"]

[[tool.importlinter.contracts]]
name = "alpha_backtest depends only on core + data"
type = "forbidden"
source_modules = ["alpha_backtest"]
forbidden_modules = ["alpha_strategies", "alpha_validation", "alpha_cli"]
```

- [ ] **Step 2: Verify the workspace resolves (will currently fail — no members yet)**

Run: `uv sync`
Expected: FAIL — uv cannot find the member packages because their `pyproject.toml` files don't exist yet. This confirms the root config is being read. Proceed to Task 2; we re-run `uv sync` once members exist.

---

## Task 2: `alpha-core` — types, errors, protocols, config

**Files:**
- Create: `packages/alpha-core/pyproject.toml`
- Create: `packages/alpha-core/src/alpha_core/__init__.py`
- Create: `packages/alpha-core/src/alpha_core/errors.py`
- Create: `packages/alpha-core/src/alpha_core/types.py`
- Create: `packages/alpha-core/src/alpha_core/protocols.py`
- Create: `packages/alpha-core/src/alpha_core/config.py`
- Test: `tests/unit/test_core_types.py`

- [ ] **Step 1: Create the package manifest**

Create `packages/alpha-core/pyproject.toml`:
```toml
[project]
name = "alpha-core"
version = "0.0.0"
description = "Domain types, protocols, errors, and config for Project ALPHA."
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/alpha_core"]
```

- [ ] **Step 2: Create the error hierarchy**

Create `packages/alpha-core/src/alpha_core/errors.py`:
```python
"""Typed error hierarchy. Never raise bare Exception; never swallow these silently."""
from __future__ import annotations


class AlphaError(Exception):
    """Base class for all Project ALPHA errors."""


class DataError(AlphaError):
    """Data ingestion, storage, or integrity failure."""


class LookAheadError(AlphaError):
    """Point-in-time access was violated — code attempted to read future data."""
```

- [ ] **Step 3: Create the core domain types**

Create `packages/alpha-core/src/alpha_core/types.py`:
```python
"""Frozen domain value types shared across all packages."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Bar(BaseModel):
    """A single OHLCV bar for one instrument. `ts` is the tz-aware bar-close time."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class ValidationOutcome(BaseModel):
    """The result of a single validation gate."""

    model_config = ConfigDict(frozen=True)

    name: str
    passed: bool
    detail: dict[str, float] = {}
```

- [ ] **Step 4: Create the protocol interfaces**

Create `packages/alpha-core/src/alpha_core/protocols.py`:
```python
"""Structural interfaces. Concrete implementations live in higher packages."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from alpha_core.types import Bar, ValidationOutcome


@runtime_checkable
class DataSource(Protocol):
    """A point-in-time source of market data. Implementations must never return future data."""

    def available_symbols(self) -> list[str]: ...

    def as_of(self, symbol: str, when: datetime) -> list[Bar]:
        """Return bars for `symbol` whose data was knowable no later than `when`."""
        ...


@runtime_checkable
class Validator(Protocol):
    """A statistical validation gate applied to a backtest result."""

    name: str

    def validate(self, result: object) -> ValidationOutcome: ...
```

- [ ] **Step 5: Create typed settings**

Create `packages/alpha-core/src/alpha_core/config.py`:
```python
"""Global configuration. Override via ALPHA_-prefixed env vars or a .env file."""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AlphaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ALPHA_", env_file=".env", extra="ignore")

    data_dir: Path = Field(default=Path("data"))
    random_seed: int = 7
```

- [ ] **Step 6: Create the package init with version export**

Create `packages/alpha-core/src/alpha_core/__init__.py`:
```python
"""Project ALPHA core domain package."""
from __future__ import annotations

from alpha_core.errors import AlphaError, DataError, LookAheadError
from alpha_core.types import Bar, ValidationOutcome

__version__ = "0.0.0"

__all__ = ["AlphaError", "DataError", "LookAheadError", "Bar", "ValidationOutcome", "__version__"]
```

- [ ] **Step 7: Write the failing unit test**

Create `tests/unit/test_core_types.py`:
```python
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from alpha_core import Bar, LookAheadError


def test_bar_is_frozen() -> None:
    bar = Bar(symbol="BTCUSD", ts=datetime(2024, 1, 1, tzinfo=UTC),
              open=1.0, high=2.0, low=0.5, close=1.5, volume=10.0)
    with pytest.raises(ValidationError):
        bar.__setattr__("close", 999.0)


def test_lookahead_error_is_alpha_error() -> None:
    from alpha_core import AlphaError
    assert issubclass(LookAheadError, AlphaError)
```

- [ ] **Step 8: Sync the workspace, now that one member exists plus the rest are pending**

Defer running tests until all members exist (Task 3 creates the remaining members so `uv sync` succeeds). Proceed.

---

## Task 3: Skeleton packages (`alpha-data`, `alpha-strategies`, `alpha-backtest`, `alpha-validation`)

Each gets a manifest, an `__init__.py`, and one typed placeholder that exercises its real dependency edge (so import-linter has edges to verify). No third-party data/engine deps yet — those arrive in their own phases.

**Files:**
- Create: `packages/alpha-data/pyproject.toml`, `packages/alpha-data/src/alpha_data/__init__.py`, `packages/alpha-data/src/alpha_data/placeholder.py`
- Create: `packages/alpha-strategies/pyproject.toml`, `packages/alpha-strategies/src/alpha_strategies/__init__.py`, `packages/alpha-strategies/src/alpha_strategies/placeholder.py`
- Create: `packages/alpha-backtest/pyproject.toml`, `packages/alpha-backtest/src/alpha_backtest/__init__.py`, `packages/alpha-backtest/src/alpha_backtest/placeholder.py`
- Create: `packages/alpha-validation/pyproject.toml`, `packages/alpha-validation/src/alpha_validation/__init__.py`, `packages/alpha-validation/src/alpha_validation/placeholder.py`

- [ ] **Step 1: `alpha-data` manifest**

Create `packages/alpha-data/pyproject.toml`:
```toml
[project]
name = "alpha-data"
version = "0.0.0"
description = "Free-data ingestion, point-in-time storage, and snapshots."
requires-python = ">=3.12"
dependencies = ["alpha-core"]

[tool.uv.sources]
alpha-core = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/alpha_data"]
```

- [ ] **Step 2: `alpha-data` source**

Create `packages/alpha-data/src/alpha_data/placeholder.py`:
```python
"""Phase-0 placeholder proving the alpha_data -> alpha_core dependency edge."""
from __future__ import annotations

from alpha_core.types import Bar


def describe(bar: Bar) -> str:
    return f"{bar.symbol}@{bar.ts.isoformat()} close={bar.close}"
```

Create `packages/alpha-data/src/alpha_data/__init__.py`:
```python
"""Project ALPHA data package."""
from __future__ import annotations

__version__ = "0.0.0"
```

- [ ] **Step 3: `alpha-strategies` manifest**

Create `packages/alpha-strategies/pyproject.toml`:
```toml
[project]
name = "alpha-strategies"
version = "0.0.0"
description = "Trading strategies (Phase 2+: nautilus Strategy subclasses)."
requires-python = ">=3.12"
dependencies = ["alpha-core"]

[tool.uv.sources]
alpha-core = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/alpha_strategies"]
```

- [ ] **Step 4: `alpha-strategies` source**

Create `packages/alpha-strategies/src/alpha_strategies/placeholder.py`:
```python
"""Phase-0 placeholder proving the alpha_strategies -> alpha_core dependency edge."""
from __future__ import annotations

from alpha_core.types import Bar


def signal_sign(prev_close: float, bar: Bar) -> int:
    """Trivial momentum stub: +1 if price rose, -1 if it fell, 0 if flat."""
    if bar.close > prev_close:
        return 1
    if bar.close < prev_close:
        return -1
    return 0
```

Create `packages/alpha-strategies/src/alpha_strategies/__init__.py`:
```python
"""Project ALPHA strategies package."""
from __future__ import annotations

__version__ = "0.0.0"
```

- [ ] **Step 5: `alpha-backtest` manifest (depends on core + data)**

Create `packages/alpha-backtest/pyproject.toml`:
```toml
[project]
name = "alpha-backtest"
version = "0.0.0"
description = "Event-driven backtest harness (Phase 2+: nautilus_trader)."
requires-python = ">=3.12"
dependencies = ["alpha-core", "alpha-data"]

[tool.uv.sources]
alpha-core = { workspace = true }
alpha-data = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/alpha_backtest"]
```

- [ ] **Step 6: `alpha-backtest` source**

Create `packages/alpha-backtest/src/alpha_backtest/placeholder.py`:
```python
"""Phase-0 placeholder proving the alpha_backtest -> {alpha_core, alpha_data} edges."""
from __future__ import annotations

from alpha_core.types import Bar
from alpha_data.placeholder import describe


def summarize(bar: Bar) -> str:
    return f"backtest sees: {describe(bar)}"
```

Create `packages/alpha-backtest/src/alpha_backtest/__init__.py`:
```python
"""Project ALPHA backtest package."""
from __future__ import annotations

__version__ = "0.0.0"
```

- [ ] **Step 7: `alpha-validation` manifest**

Create `packages/alpha-validation/pyproject.toml`:
```toml
[project]
name = "alpha-validation"
version = "0.0.0"
description = "Statistical validation gauntlet (Phase 3+: arch, skfolio)."
requires-python = ">=3.12"
dependencies = ["alpha-core"]

[tool.uv.sources]
alpha-core = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/alpha_validation"]
```

- [ ] **Step 8: `alpha-validation` source**

Create `packages/alpha-validation/src/alpha_validation/placeholder.py`:
```python
"""Phase-0 placeholder proving the alpha_validation -> alpha_core dependency edge."""
from __future__ import annotations

from alpha_core.types import ValidationOutcome


def always_passes(name: str) -> ValidationOutcome:
    return ValidationOutcome(name=name, passed=True)
```

Create `packages/alpha-validation/src/alpha_validation/__init__.py`:
```python
"""Project ALPHA validation package."""
from __future__ import annotations

__version__ = "0.0.0"
```

---

## Task 4: `alpha-cli` — typer app + walking skeleton

**Files:**
- Create: `apps/alpha-cli/pyproject.toml`
- Create: `apps/alpha-cli/src/alpha_cli/__init__.py`
- Create: `apps/alpha-cli/src/alpha_cli/main.py`
- Test: `tests/integration/test_cli_walking_skeleton.py`

- [ ] **Step 1: Create the CLI manifest with a console entry point**

Create `apps/alpha-cli/pyproject.toml`:
```toml
[project]
name = "alpha-cli"
version = "0.0.0"
description = "Project ALPHA command-line interface."
requires-python = ">=3.12"
dependencies = [
    "alpha-core",
    "alpha-data",
    "alpha-strategies",
    "alpha-backtest",
    "alpha-validation",
    "typer>=0.12",
]

[project.scripts]
alpha = "alpha_cli.main:main"

[tool.uv.sources]
alpha-core = { workspace = true }
alpha-data = { workspace = true }
alpha-strategies = { workspace = true }
alpha-backtest = { workspace = true }
alpha-validation = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/alpha_cli"]
```

- [ ] **Step 2: Create the CLI app (the walking skeleton — touches every layer)**

Create `apps/alpha-cli/src/alpha_cli/main.py`:
```python
"""Project ALPHA CLI. Phase 0 proves cross-package wiring end-to-end."""
from __future__ import annotations

import typer

from alpha_core import __version__ as core_version
from alpha_core.config import AlphaSettings

app = typer.Typer(help="Project ALPHA command-line interface.")


@app.command()
def info() -> None:
    """Print resolved configuration and the core version."""
    settings = AlphaSettings()
    typer.echo(f"alpha-core {core_version}")
    typer.echo(f"data_dir={settings.data_dir}")
    typer.echo(f"random_seed={settings.random_seed}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
```

Create `apps/alpha-cli/src/alpha_cli/__init__.py`:
```python
"""Project ALPHA CLI package."""
from __future__ import annotations

__version__ = "0.0.0"
```

- [ ] **Step 3: Sync the full workspace (all members now exist)**

Run: `uv sync`
Expected: PASS — resolves and installs all six members (editable) plus the dev group, writes `uv.lock`.

- [ ] **Step 4: Write the failing walking-skeleton test**

Create `tests/integration/test_cli_walking_skeleton.py`:
```python
from typer.testing import CliRunner

from alpha_cli.main import app

runner = CliRunner()


def test_info_runs_and_reports_core_version() -> None:
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "alpha-core 0.0.0" in result.stdout
    assert "random_seed=7" in result.stdout
```

- [ ] **Step 5: Run the test suite**

Run: `uv run pytest -q`
Expected: PASS — `test_core_types.py`, `test_cli_walking_skeleton.py` all green (bias-guard test added in Task 5).

- [ ] **Step 6: Confirm the installed console script works**

Run: `uv run alpha info`
Expected: prints `alpha-core 0.0.0`, `data_dir=data`, `random_seed=7`.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock packages/ apps/ tests/unit tests/integration
git commit -m "feat: scaffold uv workspace, core types, package skeletons, and CLI walking skeleton"
```

---

## Task 5: Bias-guard harness + architecture enforcement

**Files:**
- Create: `tests/bias_guards/test_future_poison_pattern.py`

- [ ] **Step 1: Write the future-poison pattern test (establishes the guard template)**

This Phase-0 guard runs on a self-contained causal function. Later phases reuse this exact pattern on the real data accessor and strategy.

Create `tests/bias_guards/test_future_poison_pattern.py`:
```python
"""The future-poison template: poisoning post-cutoff data must not change pre-cutoff outputs.
Later phases apply this same pattern to the real PIT accessor and strategy signals."""
from __future__ import annotations

import math

import pytest

pytestmark = pytest.mark.bias_guard


def causal_rolling_mean(xs: list[float], window: int) -> list[float]:
    out: list[float] = []
    for i in range(len(xs)):
        lo = max(0, i - window + 1)
        chunk = xs[lo : i + 1]
        out.append(sum(chunk) / len(chunk))
    return out


def test_future_poison_does_not_change_past_outputs() -> None:
    clean = [1.0, 2.0, 3.0, 4.0, 5.0]
    cutoff = 2  # outputs at indices 0..cutoff must not depend on indices > cutoff
    poisoned = clean[: cutoff + 1] + [math.nan, math.nan]
    assert (
        causal_rolling_mean(clean, 3)[: cutoff + 1]
        == causal_rolling_mean(poisoned, 3)[: cutoff + 1]
    )
```

- [ ] **Step 2: Run only the bias-guard marker**

Run: `uv run pytest -m bias_guard -q`
Expected: PASS — exactly one test selected and green. Confirms the marker + harness work.

- [ ] **Step 3: Verify the architecture contract passes**

Run: `uv run lint-imports`
Expected: `Contracts: 5 kept, 0 broken.`

- [ ] **Step 4: Prove the contract actually bites (temporary violation)**

Temporarily append to `packages/alpha-core/src/alpha_core/types.py`:
```python
from alpha_cli.main import app  # noqa: F401  TEMP — must be rejected by import-linter
```
Run: `uv run lint-imports`
Expected: FAIL — "alpha_core imports nothing internal" broken. This proves the gate is real.

- [ ] **Step 5: Revert the violation**

Remove the temporary import line from `types.py`. Re-run `uv run lint-imports`.
Expected: `Contracts: 5 kept, 0 broken.`

- [ ] **Step 6: Commit**

```bash
git add tests/bias_guards
git commit -m "test: add bias-guard harness (future-poison template) and verify import-linter gate"
```

---

## Task 6: CI workflow + CLAUDE.md

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `CLAUDE.md`

- [ ] **Step 1: Create the CI workflow**

Create `.github/workflows/ci.yml`:
```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          python-version: "3.12"
          enable-cache: true
      - name: Install
        run: uv sync
      - name: Lint
        run: uv run ruff check .
      - name: Format check
        run: uv run ruff format --check .
      - name: Types
        run: uv run mypy -p alpha_core -p alpha_data -p alpha_strategies -p alpha_backtest -p alpha_validation -p alpha_cli tests
      - name: Architecture
        run: uv run lint-imports
      - name: Tests (incl. bias guards)
        run: uv run pytest -q
```

- [ ] **Step 2: Create `CLAUDE.md`**

Create `CLAUDE.md`:
```markdown
# Project ALPHA — Build Conventions

Personal, $0/free, Python quant research platform. Spec: `docs/superpowers/specs/2026-06-14-project-alpha-v1-design.md`. Research: `research/00-SYNTHESIS.md`.

## Architecture (enforced by import-linter — never violate)
Dependency DAG: `alpha_core` ← `alpha_data` ← `alpha_backtest`; `alpha_strategies`, `alpha_validation` ← `alpha_core`; `alpha_cli` ← everything. `alpha_core` imports nothing internal.

## Golden rules
- **TDD.** Failing test → minimal code → green → commit. Small commits.
- **No look-ahead, ever.** Strategies read data only via the point-in-time accessor (`as_of`). Every data/strategy unit gets a `@pytest.mark.bias_guard` future-poison test.
- **Execution convention:** decide on close of bar `t`, fill at open of `t+1`.
- **No empty `except`.** Log with context or re-raise. Fail loud on data gaps / NaN / disorder.
- **Polars** is the default dataframe; pandas only at library edges.
- Strong typing everywhere; `mypy --strict` is a CI gate.

## Commands
- Install: `uv sync`
- Test: `uv run pytest -q` · bias guards only: `uv run pytest -m bias_guard -q`
- Lint/format/types/arch: `uv run ruff check . && uv run ruff format --check . && uv run mypy -p alpha_core -p alpha_data -p alpha_strategies -p alpha_backtest -p alpha_validation -p alpha_cli tests && uv run lint-imports`
- CLI: `uv run alpha info`
```

- [ ] **Step 3: Commit**

```bash
git add .github CLAUDE.md
git commit -m "ci: add GitHub Actions gate (ruff, mypy, import-linter, pytest) and CLAUDE.md"
```

---

## Task 7: Full green gate

- [ ] **Step 1: Run the complete local gate (mirrors CI)**

Run:
```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy -p alpha_core -p alpha_data -p alpha_strategies -p alpha_backtest -p alpha_validation -p alpha_cli tests && uv run lint-imports && uv run pytest -q
```
Expected: ruff clean; format clean; mypy "Success: no issues found"; import-linter "5 kept, 0 broken"; pytest all PASS (3 tests).

- [ ] **Step 2: Fix anything red, then re-run until fully green.**

If `ruff format --check` fails, run `uv run ruff format .`, review the diff, and commit it. If mypy flags a missing stub, add the dependency or a typed shim — never `# type: ignore` without a reason comment.

- [ ] **Step 3: Final commit (if any fixes were made)**

```bash
git add -A
git commit -m "chore: phase-0 gate green (ruff, mypy, import-linter, pytest)"
```

---

## Done = Phase 0 complete

- `uv sync` installs all six packages.
- `uv run alpha info` works (walking skeleton proves cross-package wiring).
- `uv run pytest -q` is green, including the `bias_guard` marker.
- `uv run lint-imports` reports 5 kept / 0 broken; the temporary-violation step proved the gate bites.
- CI workflow runs the same gate.
- Git history: baseline → scaffold → bias-guard → CI → green.

**Next plan:** Phase 1 — Data spine (free-data ingest → Parquet → DuckDB as-of view → PIT accessor → snapshots → the corporate-action bias guards from spec §6.1).

## Notes / risks

- **uv workspace specifics** move fast. If `uv sync` errors on workspace sources, check current uv docs (Context7: `astral-sh/uv`) — the `[tool.uv.sources] { workspace = true }` + `[tool.uv.workspace] members` pattern is correct as of uv 0.6, but verify the installed version with `uv --version`.
- **mypy + src-layout** can emit "Source file found twice" / namespace errors. The plan uses `mypy -p <pkg>` (import-system resolution of the editable installs) plus `explicit_package_bases` to avoid this; if the `tests` arg errors, check it per-directory. The `pydantic.mypy` plugin must be importable (it is, via `alpha-core`'s pydantic dependency).
- **No remote yet.** Pushing to GitHub (so CI actually runs) is deferred until the owner chooses a remote; the workflow file is ready for when they do.
