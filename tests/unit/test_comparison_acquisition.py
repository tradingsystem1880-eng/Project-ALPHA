"""Private acquisition retains source evidence, failures and spent request scope."""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from alpha_cli.artifact_contract import artifact_contract
from alpha_cli.comparison_acquisition import AcquisitionPlan, AcquisitionSeries, draft_acquisition
from alpha_cli.investigation_case import Case
from alpha_core import DataError
from alpha_data.adapters.base import FetchResult
from tests.unit.test_research_execution import run_fixture


def parent_case(tmp_path: Path) -> Case:
    run = run_fixture(tmp_path)
    for path in run.glob("*.parquet"):
        frame = pl.read_parquet(path)
        frame = frame.with_columns(
            [
                pl.col(name) + pl.duration(days=1)
                for name, dtype in frame.schema.items()
                if isinstance(dtype, pl.Datetime)
            ]
        )
        if path.name == "equity_curve.parquet":
            frame = frame.with_columns(pl.Series("equity", [100.0, 60.0]))
        frame.write_parquet(path)
    manifest = json.loads((run / "manifest.json").read_text())
    manifest.update(research_cutoff="2020-01-03", artifacts=artifact_contract(run))
    (run / "manifest.json").write_text(json.dumps(manifest))
    case = Case.create(tmp_path / "case", run, "2020-01-03", "Compare losses", "gpt-6-astra")
    case.call("inspect_execution")
    case.call("inspect_losses")
    return case


def series() -> list[AcquisitionSeries]:
    return [AcquisitionSeries(symbol="SPY", asset_class="etf", role="market")]


def test_draft_binds_parent_and_episode_window(tmp_path: Path) -> None:
    case = parent_case(tmp_path)
    plan = draft_acquisition(case, series())
    assert plan.case_id == case.context()["case_id"]
    assert (plan.start, plan.end) == (date(2020, 1, 2), date(2020, 1, 3))
    assert plan.provider == "tiingo"
    assert case.context()["requests_remaining"] == 10


@pytest.mark.parametrize("change", ["duplicate", "future", "empty", "extra", "provider"])
def test_invalid_contract_rejected(tmp_path: Path, change: str) -> None:
    case = parent_case(tmp_path)
    values = draft_acquisition(case, series()).model_dump(mode="json")
    if change == "duplicate":
        values["series"] *= 2
    elif change == "empty":
        values["series"] = []
    elif change == "future":
        values["end"] = "2050-01-03"
    elif change == "provider":
        values["provider"] = "unknown"
    else:
        values["url"] = "https://example.invalid"
    with pytest.raises(ValueError):
        AcquisitionPlan.model_validate_json(json.dumps(values))


def provider_result(plan: AcquisitionPlan, index: int, limit: int) -> FetchResult:
    from alpha_data.adapters.tiingo_adapter import parse_tiingo_eod

    rows = []
    for day, price in ((2, 100.0), (3, 80.0)):
        rows.append(
            {
                "date": f"2020-01-{day:02}T00:00:00Z",
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": 1000,
                "adjOpen": price,
                "adjHigh": price,
                "adjLow": price,
                "adjClose": price,
                "divCash": 0,
                "splitFactor": 1,
            }
        )
    item = plan.series[index]
    return parse_tiingo_eod(
        json.dumps(rows).encode(),
        symbol=item.symbol,
        provider_symbol=item.symbol,
        asset_class=item.asset_class,
        venue=item.venue,
        calendar=item.calendar,
        currency=item.currency,
        start=plan.start,
        end=plan.end,
        fetched_at=datetime(2026, 10, 4, tzinfo=UTC),
    )


def fixture_dispatch(root: Path, index: int) -> dict[str, Any]:
    from alpha_cli.comparison_acquisition_worker import perform_request

    return perform_request(root, index)


def test_private_acquisition_and_verified_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import comparison_acquisition as module
    from alpha_cli import comparison_acquisition_worker as worker

    case = parent_case(tmp_path)
    request = draft_acquisition(case, series())
    monkeypatch.setenv("ALPHA_TIINGO_API_KEY", "fixture")
    monkeypatch.setattr(worker, "_fetch", provider_result)
    monkeypatch.setattr(module, "_dispatch", fixture_dispatch)
    result = module.acquire_comparisons(case, request)
    assert result["status"] == "succeeded"
    assert result["admitted"] is False
    assert result["attempts"][0]["status"] == "succeeded"
    assert result["comparisons"]["series"][0]["symbol"] == "SPY"
    assert Path(result["data_root"]).is_relative_to(case.path)
    monkeypatch.delenv("ALPHA_TIINGO_API_KEY")
    monkeypatch.setattr(module, "_dispatch", lambda *args: pytest.fail("replay fetched"))
    assert module.acquire_comparisons(case, request) == result
    assert case.context()["requests_remaining"] == 10
    quality = case.path / "comparison-acquisition" / result["attempts"][0]["quality_path"]
    quality.write_text("{}")
    with pytest.raises(DataError, match="artifact"):
        module.acquire_comparisons(case, request)


def test_acquired_snapshot_drives_new_case_without_mutating_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import comparison_acquisition as module
    from alpha_cli import comparison_acquisition_worker as worker
    from alpha_cli.investigation_comparisons import ComparisonPlan

    case = parent_case(tmp_path)
    before = case.verify()
    monkeypatch.setenv("ALPHA_TIINGO_API_KEY", "fixture")
    monkeypatch.setattr(worker, "_fetch", provider_result)
    monkeypatch.setattr(module, "_dispatch", fixture_dispatch)
    result = module.acquire_comparisons(case, draft_acquisition(case, series()))
    run_id = case.context()["run_id"]
    run = next(
        path.parent for path in tmp_path.rglob("manifest.json") if path.parent.name == run_id
    )
    child = Case.create(
        tmp_path / "comparison-case",
        run,
        "2020-01-03",
        "Compare acquired market data",
        "gpt-6-astra",
        comparisons=ComparisonPlan.model_validate(result["comparisons"]),
        data_dir=Path(result["data_root"]),
    )
    evidence = child.verify()["observations"]["comparisons"]
    assert evidence["series"][0]["windows"][0]["price_change"] == pytest.approx(-0.2)
    assert evidence["causal_attribution"] == "not_tested"
    assert evidence["quality_certification"] == "not_established"
    assert evidence["series"][0]["historical_vintage"] == "unverified"
    assert case.verify() == before
    assert case.context()["requests_remaining"] == 10


@pytest.mark.bias_guard
def test_future_request_poison_rejected_with_leaky_control(tmp_path: Path) -> None:
    from alpha_cli.comparison_acquisition import _scope

    case = parent_case(tmp_path)
    plan = draft_acquisition(case, series())
    assert _scope(case, plan)["plan"]["end"] == "2020-01-03"
    poisoned = plan.model_copy(update={"end": date(2020, 1, 6)})
    with pytest.raises(DataError, match="run/cutoff"):
        _scope(case, poisoned)
    # Control: trusting schema validation alone demonstrably admits future dates.
    leaky = AcquisitionPlan.model_validate_json(poisoned.model_dump_json())
    with pytest.raises(AssertionError):
        assert leaky.end <= date.fromisoformat(case.context()["cutoff"])


@pytest.mark.bias_guard
def test_future_provider_rows_rejected_with_leaky_control(tmp_path: Path) -> None:
    from alpha_data.adapters.tiingo_adapter import parse_tiingo_eod

    plan = draft_acquisition(parent_case(tmp_path), series())
    fetched = provider_result(plan, 0, 1024)
    assert fetched.raw_response is not None
    rows = json.loads(fetched.raw_response)
    future = dict(rows[-1], date="2020-01-06T00:00:00Z", close=1000000)
    rows.append(future)
    with pytest.raises(DataError, match="outside requested range"):
        parse_tiingo_eod(
            json.dumps(rows).encode(),
            symbol="SPY",
            provider_symbol="SPY",
            asset_class="etf",
            venue="US",
            calendar="XNYS",
            currency="USD",
            start=plan.start,
            end=plan.end,
            fetched_at=datetime(2026, 10, 4, tzinfo=UTC),
        )
    # Control: blindly taking the vendor's last close changes the endpoint return.
    leaky_return = rows[-1]["close"] / rows[0]["close"] - 1
    with pytest.raises(AssertionError):
        assert leaky_return == pytest.approx(-0.2)


def test_cli_real_fixture_pipeline_and_cached_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from alpha_cli import comparison_acquisition as module
    from alpha_cli import comparison_acquisition_worker as worker
    from alpha_cli.research_diagnostic_cmds import diagnostic_app

    case = parent_case(tmp_path)
    monkeypatch.setenv("ALPHA_TIINGO_API_KEY", "fixture")
    monkeypatch.setattr(worker, "_fetch", provider_result)
    monkeypatch.setattr(module, "_dispatch", fixture_dispatch)
    runner = CliRunner()
    draft = runner.invoke(
        diagnostic_app,
        [
            "acquisition-plan",
            str(case.path),
            "--symbol",
            "SPY",
            "--asset-class",
            "etf",
            "--role",
            "market",
        ],
    )
    assert draft.exit_code == 0, draft.output
    plan_file = tmp_path / "request.json"
    plan_file.write_text(draft.stdout)
    acquired = runner.invoke(
        diagnostic_app, ["acquire-comparisons", str(case.path), str(plan_file)]
    )
    assert acquired.exit_code == 0, acquired.output
    receipt = json.loads(acquired.stdout)
    assert receipt["status"] == "succeeded"
    assert Path(receipt["data_root"]).is_dir()
    monkeypatch.delenv("ALPHA_TIINGO_API_KEY")
    monkeypatch.setattr(module, "_dispatch", lambda *args: pytest.fail("cached CLI fetched"))
    cached = runner.invoke(diagnostic_app, ["acquire-comparisons", str(case.path), str(plan_file)])
    assert cached.exit_code == 0, cached.output
    assert json.loads(cached.stdout) == receipt


def test_partial_batch_never_publishes_comparisons_or_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import comparison_acquisition as module
    from alpha_cli import comparison_acquisition_worker as worker

    case = parent_case(tmp_path)
    requested = series() + [AcquisitionSeries(symbol="QQQ", asset_class="etf", role="sector")]
    plan = draft_acquisition(case, requested)
    calls: list[int] = []

    def fetch(plan: AcquisitionPlan, index: int, limit: int) -> FetchResult:
        calls.append(index)
        if index == 1:
            raise DataError("fixture second symbol unavailable")
        return provider_result(plan, index, limit)

    monkeypatch.setenv("ALPHA_TIINGO_API_KEY", "fixture")
    monkeypatch.setattr(worker, "_fetch", fetch)
    monkeypatch.setattr(module, "_dispatch", fixture_dispatch)
    receipt = module.acquire_comparisons(case, plan)
    assert calls == [0, 1]
    assert receipt["status"] == "failed"
    assert [attempt["status"] for attempt in receipt["attempts"]] == ["succeeded", "failed"]
    assert "comparisons" not in receipt
    assert not (case.path / "comparison-acquisition/comparisons.json").exists()
    assert not (Path(receipt["data_root"]) / "snapshots").exists()
    assert module.acquire_comparisons(case, plan) == receipt
    assert calls == [0, 1]
