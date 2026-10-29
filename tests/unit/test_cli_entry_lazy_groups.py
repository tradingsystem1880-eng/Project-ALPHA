"""The console entry loads only the invoked command group; the full app is unchanged."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.fixtures.cli_fixtures import seed_store

_RUN = """
import json, sys
import alpha_cli.main as entry
sys.argv = ["alpha", *json.loads(sys.argv[1])]
try:
    entry.main()
except SystemExit as exc:
    code = exc.code
else:
    code = 0
heavy = [m for m in ("alpha_cli.backtest_cmds", "alpha_validation", "scipy") if m in sys.modules]
print(json.dumps({"code": code, "heavy": heavy}), file=sys.stderr)
"""

_FULL = """
import json, sys
from alpha_cli.main import app
sys.argv = ["alpha", *json.loads(sys.argv[1])]
app()
"""


def _run(script: str, argv: list[str], data_dir: Path) -> subprocess.CompletedProcess[str]:
    env = {"PATH": "/usr/bin:/bin", "ALPHA_DATA_DIR": str(data_dir), "TYPER_USE_RICH": "0"}
    return subprocess.run(
        [sys.executable, "-c", script, json.dumps(argv)],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )


def test_data_command_does_not_import_unrelated_groups(tmp_path: Path) -> None:
    seed_store(tmp_path, symbol="SPY", n=60)
    result = _run(_RUN, ["data", "symbols", "--json"], tmp_path)
    report = json.loads(result.stderr.strip().splitlines()[-1])
    assert report == {"code": 0, "heavy": []}, result.stderr
    assert json.loads(result.stdout) == {"symbols": ["SPY"]}


@pytest.mark.parametrize(
    "argv",
    [["data", "symbols", "--json"], ["data", "--help"], ["rules", "--help"], ["info", "--help"]],
)
def test_entry_output_matches_full_app(tmp_path: Path, argv: list[str]) -> None:
    seed_store(tmp_path, symbol="SPY", n=60)
    lazy = _run(_RUN, argv, tmp_path)
    full = _run(_FULL, argv, tmp_path)
    assert lazy.stdout == full.stdout
    assert json.loads(lazy.stderr.strip().splitlines()[-1])["code"] == full.returncode


def test_full_app_keeps_every_command_group() -> None:
    import typer

    from alpha_cli.main import app

    group = typer.main.get_command(app)
    assert sorted(group.commands) == sorted(  # type: ignore[attr-defined]
        [
            "assistant",
            "backtest",
            "chart",
            "crypto-data",
            "data",
            "evidence",
            "figures",
            "forecast",
            "info",
            "ml",
            "monte-carlo",
            "optim",
            "owner-auth",
            "paper",
            "project",
            "propfirm",
            "provider",
            "quantpad-data",
            "report",
            "research",
            "risk",
            "rules",
            "scan",
            "strategy-candidate",
            "suite",
            "validate",
        ]
    )
    assert "import-pdf" in group.commands["research"].commands  # type: ignore[attr-defined]
