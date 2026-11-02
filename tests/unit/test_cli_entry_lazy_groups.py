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
heavy = [m for m in ("alpha_cli.backtest_cmds", "alpha_validation", "scipy",
                    "alpha_cli.research_intake", "alpha_cli.research_runtime") if m in sys.modules]
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


@pytest.mark.parametrize("command", ["job-event", "job-status", "job-show"])
def test_project_job_commands_do_not_import_research_intake(tmp_path: Path, command: str) -> None:
    from alpha_cli.control_store import ControlStore

    store = ControlStore(tmp_path)
    job = store.create_job(kind="kronos_forecast", request={"fixture": "lazy intake import"})
    job_id = str(job["job_id"])
    if command != "job-status":
        store.set_job_status(job_id, "running")
    argv = ["project", command, job_id]
    if command == "job-event":
        argv += ["heartbeat", "--payload-json", '{"surface":"workstation"}']
    elif command == "job-status":
        argv += ["running"]
    result = _run(_RUN, [*argv, "--json"], tmp_path)
    report = json.loads(result.stderr.strip().splitlines()[-1])
    assert report == {"code": 0, "heavy": []}, result.stderr
    row = json.loads(result.stdout)
    if command == "job-event":
        assert row["event_type"] == "heartbeat" and row["cancel_requested"] is False
        assert row["payload"] == {"surface": "workstation"}
    else:
        assert row["status"] == "running"


@pytest.mark.parametrize("valid", [True, False])
def test_project_create_loads_intake_and_preserves_validation(tmp_path: Path, valid: bool) -> None:
    result = _run(
        _RUN,
        [
            "project",
            "create",
            "Lazy intake fixture",
            "--hypothesis",
            "A bounded event may have an effect." if valid else "   ",
            "--falsification",
            "Reject when evidence is inconclusive.",
            "--json",
        ],
        tmp_path,
    )
    report = json.loads(result.stderr.strip().splitlines()[-1])
    assert "alpha_cli.research_intake" in report["heavy"]
    if valid:
        assert report["code"] == 0, result.stderr
        assert json.loads(result.stdout)["name"] == "Lazy intake fixture"
    else:
        assert report["code"] == 2 and "raw idea" in result.stderr


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
