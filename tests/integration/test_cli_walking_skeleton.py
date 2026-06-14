from typer.testing import CliRunner

from alpha_cli.main import app

runner = CliRunner()


def test_info_runs_and_reports_core_version() -> None:
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "alpha-core 0.0.0" in result.stdout
    assert "random_seed=7" in result.stdout
