from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_core import __version__ as core_version

runner = CliRunner()


def test_info_runs_and_reports_core_version() -> None:
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert f"alpha-core {core_version}" in result.stdout  # tracks the version, not a literal
    assert "random_seed=7" in result.stdout
