"""Trusted CLI acquisition freezes scope before controller dispatch."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from alpha_cli import research_diagnostic_cmds as commands
from alpha_cli.investigation_case import Case


def test_draft_command_validates_series_and_outputs_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    from alpha_cli import comparison_acquisition as acquisition

    seen: list[Any] = []
    monkeypatch.setattr(Case, "open", lambda path: "case")

    def draft(case: object, series: list[Any]) -> Any:
        seen.append((case, series))
        return SimpleNamespace(model_dump_json=lambda **_: '{"schema_version":1}')

    monkeypatch.setattr(acquisition, "draft_acquisition", draft)
    result = CliRunner().invoke(
        commands.diagnostic_app,
        [
            "acquisition-plan",
            "/case",
            "--symbol",
            "SPY",
            "--symbol",
            "QQQ",
            "--asset-class",
            "etf",
            "--role",
            "market",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"schema_version": 1}
    assert [item.symbol for item in seen[0][1]] == ["SPY", "QQQ"]
    assert all(item.role == "market" and item.asset_class == "etf" for item in seen[0][1])


@pytest.mark.parametrize("status,exit_code", [("succeeded", 0), ("failed", 1)])
def test_acquisition_command_parses_strict_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: str, exit_code: int
) -> None:
    from alpha_cli import comparison_acquisition as acquisition

    monkeypatch.setattr(Case, "open", lambda path: "case")
    seen: list[Any] = []

    def acquire(case: object, plan: Any) -> dict[str, object]:
        seen.append((case, plan))
        return {"status": status}

    monkeypatch.setattr(acquisition, "acquire_comparisons", acquire)
    path = tmp_path / "plan.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "case_id": "a" * 64,
                "start": "2020-01-01",
                "end": "2020-01-02",
                "provider": "tiingo",
                "series": [{"symbol": "SPY", "asset_class": "etf", "role": "market"}],
            }
        )
    )
    result = CliRunner().invoke(
        commands.diagnostic_app, ["acquire-comparisons", "/case", str(path)]
    )
    assert result.exit_code == exit_code, result.output
    assert json.loads(result.stdout) == {"status": status}
    assert seen[0][1].start.isoformat() == "2020-01-01"
    path.write_bytes(b" " * 65537)
    result = CliRunner().invoke(
        commands.diagnostic_app, ["acquire-comparisons", "/case", str(path)]
    )
    assert result.exit_code != 0
    assert "64 KiB" in result.output
    assert len(seen) == 1


def test_investigate_separates_run_and_comparison_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import codex_investigation

    seen: list[Any] = []
    monkeypatch.setattr(
        commands, "AlphaSettings", lambda: SimpleNamespace(data_dir=tmp_path / "owner")
    )
    monkeypatch.setattr(Case, "create", lambda *args, **kwargs: seen.append((args, kwargs)))

    async def launch(case: object) -> dict[str, object]:
        return {"status": "fixture"}

    monkeypatch.setattr(codex_investigation, "run_investigation", launch)
    plan = tmp_path / "comparisons.json"
    plan.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "series": [
                    {
                        "snapshot_id": "frozen",
                        "snapshot_sha256": "a" * 64,
                        "symbol": "SPY",
                        "role": "market",
                    }
                ],
            }
        )
    )
    args = [
        "investigate",
        str(tmp_path / "case"),
        "--run-id",
        "1234567890abcdef",
        "--as-of",
        "2020-01-02",
        "--question",
        "Why?",
        "--comparison-data-root",
        str(tmp_path / "private"),
    ]
    runner = CliRunner()
    result = runner.invoke(commands.diagnostic_app, args + ["--comparisons", str(plan)])
    assert result.exit_code == 0, result.output
    assert seen[0][0][1] == tmp_path / "owner/runs/1234567890abcdef"
    assert seen[0][1]["data_dir"] == tmp_path / "private"
    for rejected in (
        args,
        [
            "investigate",
            str(tmp_path / "case"),
            "--resume",
            "--comparison-data-root",
            str(tmp_path),
        ],
    ):
        assert runner.invoke(commands.diagnostic_app, rejected).exit_code != 0
    assert len(seen) == 1


@pytest.mark.parametrize("asset_class,role", [("crypto", "market"), ("etf", "invented")])
def test_draft_invalid_series_never_dispatches(
    monkeypatch: pytest.MonkeyPatch, asset_class: str, role: str
) -> None:
    from alpha_cli import comparison_acquisition as acquisition

    def forbidden(*args: Any) -> Any:
        pytest.fail("invalid series must not reach case or controller")

    monkeypatch.setattr(Case, "open", forbidden)
    monkeypatch.setattr(acquisition, "draft_acquisition", forbidden)
    result = CliRunner().invoke(
        commands.diagnostic_app,
        [
            "acquisition-plan",
            "/case",
            "--symbol",
            "SPY",
            "--asset-class",
            asset_class,
            "--role",
            role,
        ],
    )
    assert result.exit_code != 0
    assert "validation error" in result.output


def test_invalid_acquisition_plan_never_opens_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any) -> Any:
        pytest.fail("invalid plan must not open case")

    monkeypatch.setattr(Case, "open", forbidden)
    path = tmp_path / "invalid.json"
    path.write_text('{"schema_version":1,"series":[],"unsupported":true}')
    result = CliRunner().invoke(
        commands.diagnostic_app, ["acquire-comparisons", "/case", str(path)]
    )
    assert result.exit_code != 0
    assert "validation error" in result.output
