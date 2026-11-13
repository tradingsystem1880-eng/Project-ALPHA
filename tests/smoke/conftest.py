"""Shared homes for the smoke checks: the data steps run once, later workflows get a copy.

Offline data gets in the only way the project offers: no price source works offline through the
public command line (every ``alpha data pull`` source needs the network), so the store is seeded
with the same labelled synthetic bars the integration tests and the Playwright real backend use
(``tests.fixtures.cli_fixtures.seed_store``). Everything after that goes through the installed
programs, each step in a new process.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest
from run_owned_test import require_test_owner

from tests.fixtures.cli_fixtures import seed_store
from tests.smoke._harness import alpha

SNAPSHOT = "smoke-v1"
# Small but real strategy parameters: 400 daily bars warm up, trade and give several folds.
STRATEGY = (
    "--lookback", "20", "--skip", "1", "--vol-window", "10", "--rebalance-every", "5",
    "--starting-cash", "100000",
)  # fmt: skip
_BACKTEST_LINE = re.compile(r"-> run ([0-9a-f]{16}): .*final equity ([0-9.]+)")


@dataclass(frozen=True)
class BacktestHome:
    home: Path
    run_id: str
    final_equity: float


def copy_home(source: Path, tmp_path: Path) -> Path:
    return Path(shutil.copytree(source, tmp_path / "home", symlinks=True))


@pytest.fixture(scope="session")
def data_home(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Workflow 1's steps, done once: synthetic bars in, then snapshot and verify."""
    try:
        require_test_owner()  # same precondition as the owned_test_process fixture
    except RuntimeError as exc:
        pytest.fail(str(exc), pytrace=False)
    home = tmp_path_factory.mktemp("smoke-data")
    seed_store(home / "data", symbol="SPY", n=400)
    alpha(home, "data", "snapshot", SNAPSHOT, "SPY")
    alpha(home, "data", "verify", SNAPSHOT)
    return home


@pytest.fixture(scope="session")
def backtest_home(data_home: Path, tmp_path_factory: pytest.TempPathFactory) -> BacktestHome:
    """Workflow 2's run, done once on a copy of the data home."""
    home = copy_home(data_home, tmp_path_factory.mktemp("smoke-backtest"))
    ran = alpha(home, "backtest", "run", "SPY", *STRATEGY, "--snapshot", SNAPSHOT)
    match = _BACKTEST_LINE.search(ran.stdout)
    assert match, ran.report()
    return BacktestHome(home, match.group(1), float(match.group(2)))
