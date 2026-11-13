"""Actual CLI disclosure of recorded-path anchoring; no fitted models or studies."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner, Result

from alpha_cli import _artifacts, _runner
from alpha_cli.main import _root_app
from alpha_web.api.models import RiskReport


def source_run(tmp_path: Path, wealth: tuple[float, ...]) -> str:
    identity = _runner.run_identity_for({"command": "c04_anchor_fixture", "wealth": wealth})
    directory = tmp_path / "runs" / identity.run_id
    directory.mkdir(parents=True)
    start = datetime(2024, 1, 1, tzinfo=UTC)
    frame = pl.DataFrame(
        {"ts": [start + timedelta(days=i) for i in range(len(wealth))], "equity": wealth},
        schema={"ts": pl.Datetime("us", "UTC"), "equity": pl.Float64()},
    )
    _artifacts.publish_artifact(directory / "equity_curve.parquet", frame.write_parquet)
    # A declared cash parameter does not prove coverage of the corresponding
    # initial valuation or external flows in the artifact consumed by this CLI.
    _artifacts.write_manifest(
        directory,
        {
            "run_id": identity.run_id,
            "command": "c04_anchor_fixture",
            "metadata": {"starting_cash": 1000.0},
            **identity.manifest_fields(),
        },
    )
    return identity.run_id


def invoke(run_id: str, *args: str) -> Result:
    app = _root_app((("risk", "alpha_cli.risk_cmds", "risk_app"),), commands=False)
    return CliRunner().invoke(app, ["risk", "scenario", "--from-run", run_id, *args])


@pytest.mark.parametrize(
    "wealth,expected_row",
    [
        ((1000.0, 900.0, 1000.0), "maxdd=-0.100"),
        ((900.0, 950.0, 1000.0), "maxdd=0.000"),
        ((1.0, 0.9, 1.0), "maxdd=-0.100"),
    ],
)
def test_human_report_discloses_scope_of_actual_anchor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    wealth: tuple[float, ...],
    expected_row: str,
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    result = invoke(source_run(tmp_path, wealth))
    assert result.exit_code == 0, result.output
    text = " ".join(result.output.split())
    assert "Metric source: alpha_validation.scenario (ALPHA recomputation)" in text
    assert "total return compounds" in text
    assert "252 periods/year" in text
    assert "No benchmark adjustment" in text
    assert f"first recorded equity {wealth[0]:.17g}" in text
    assert "Initial-capital baseline and external cash-flow coverage are not verified" in text
    assert "losses before the anchor are not measured" in text
    base_line = next(
        line for line in result.output.splitlines() if line.lstrip().startswith("base:")
    )
    assert expected_row in base_line
    # The stored90%-of-declared-cash anchor remains900; do not silently insert1000.
    if wealth[0] == 900:
        assert "first recorded equity 1000" not in text


@pytest.mark.parametrize("periods_per_year", [252, 365])
def test_json_consumer_contract_and_metric_values_remain_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, periods_per_year: int
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    run_id = source_run(tmp_path, (900.0, 950.0, 1000.0))
    result = invoke(run_id, "--json", "--periods-per-year", str(periods_per_year))
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    report = RiskReport.model_validate(payload)  # current real web response contract
    base = next(row for row in report.scenarios if row.name == "base")
    assert base.max_drawdown == pytest.approx(0, abs=1e-12, rel=0)
    assert base.total_return == pytest.approx(1 / 9, abs=1e-12, rel=0)
    assert report.provenance.periods_per_year == periods_per_year
    assert "Metric source:" not in result.output
    human = invoke(run_id, "--periods-per-year", str(periods_per_year))
    assert human.exit_code == 0, human.output
    assert f"{periods_per_year} periods/year" in human.output


def test_invalid_source_does_not_print_a_metric_basis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    result = invoke("0000000000000000")
    assert result.exit_code != 0
    assert "no run" in result.output
    assert "Metric source:" not in result.output


@pytest.mark.parametrize(
    "wealth", [(1000.0, 900.0, 1000.0), (900.0, 950.0, 1000.0), (1.0, 0.9, 1.0)]
)
def test_opted_json_carries_versioned_basis_without_changing_legacy_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wealth: tuple[float, ...]
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    run_id = source_run(tmp_path, wealth)
    args = ("--json", "--periods-per-year", "365")
    legacy = invoke(run_id, *args)
    disclosed = invoke(run_id, *args, "--include-metric-basis")
    assert legacy.exit_code == 0, legacy.output
    assert disclosed.exit_code == 0, disclosed.output
    before = json.loads(legacy.output)
    after = json.loads(disclosed.output)
    RiskReport.model_validate(before)  # pre-extension strict consumers still work
    assert "metric_basis" not in before["provenance"]
    basis = after["provenance"].pop("metric_basis")
    assert after == before  # every metric and existing provenance field unchanged
    assert basis == {
        "schema_version": 1,
        "anchor_kind": "first_recorded_equity",
        "anchor_ts": "2024-01-01T00:00:00+00:00",
        "anchor_value": pytest.approx(wealth[0], abs=1e-12, rel=0),
        "anchor_units": "recorded_equity_units",
        "initial_capital_status": "unknown",
        "external_cash_flow_status": "unknown",
        "return_accumulation": "compounded_simple_returns",
        "drawdown_convention": "non_positive_fraction_from_scenario_wealth_peaks",
        "benchmark_adjustment": "none_by_projection",
        "pre_anchor_losses": "not_measured",
    }


def test_metric_basis_option_requires_machine_readable_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    result = invoke(source_run(tmp_path, (1000.0, 900.0, 1000.0)), "--include-metric-basis")
    assert result.exit_code != 0
    assert "requires --json" in " ".join(result.output.split())
