"""CLI selection preserves source inputs and keeps capability inspection out of process."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from tests.unit.test_ml_contract import _draft, _panel


def test_cli_model_selection_publishes_new_v3_request(tmp_path: Path) -> None:
    spec = tmp_path / "spec.json"
    original = json.dumps(_draft()).encode()
    spec.write_bytes(original)
    panel = tmp_path / "panel.parquet"
    _panel().write_parquet(panel)
    exchange = tmp_path / "linear"
    result = CliRunner().invoke(
        app,
        [
            "ml",
            "prepare",
            str(spec),
            str(panel),
            str(exchange),
            "--model",
            "linear",
            "--parameters-json",
            '{"alpha":2}',
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    request = json.loads((exchange / "request.json").read_text())
    assert request["schema_version"] == 3
    assert request["model"] == {"name": "linear", "parameters": {"alpha": 2}}
    assert spec.read_bytes() == original


@pytest.mark.parametrize("parameters", ["[]", '{"alpha":NaN}', '{"alpha":1,"alpha":2}', "{"])
def test_cli_bad_model_parameters_do_not_publish(tmp_path: Path, parameters: str) -> None:
    spec, panel, exchange = tmp_path / "spec.json", tmp_path / "panel.parquet", tmp_path / "out"
    spec.write_text(json.dumps(_draft()))
    _panel().write_parquet(panel)
    result = CliRunner().invoke(
        app,
        [
            "ml",
            "prepare",
            str(spec),
            str(panel),
            str(exchange),
            "--model",
            "linear",
            "--parameters-json",
            parameters,
        ],
    )
    assert result.exit_code != 0
    assert not exchange.exists()


def test_capabilities_inspection_does_not_sync_or_pass_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "worker"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='worker'\n")
    (project / "uv.lock").write_text("lock")
    (project / ".venv" / "bin").mkdir(parents=True)
    (project / ".venv" / "bin" / "alpha-qlib-worker").touch()
    payload = {"schema_version": 1, "qlib_version": "0.9.7", "backends": []}
    seen: dict[str, Any] = {}

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.update(command=command, **kwargs)
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr("alpha_cli.ml_cmds.subprocess.run", run)
    monkeypatch.setattr("alpha_cli.ml_cmds.shutil.which", lambda name: "/bin/uv")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "not-for-worker")
    result = CliRunner().invoke(
        app, ["ml", "capabilities", "--worker-project", str(project), "--json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == payload
    assert "--no-sync" in seen["command"]
    assert seen["command"][-1] == "capabilities"
    assert "AWS_SECRET_ACCESS_KEY" not in seen["env"]
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "BLIS_NUM_THREADS",
    ):
        assert seen["env"][name] == "1"
    assert seen["timeout"] <= 60


@pytest.mark.parametrize("environment_present", [False, True])
def test_missing_worker_capabilities_are_readiness_not_invalid_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, environment_present: bool
) -> None:
    project = tmp_path / "worker"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='worker'\n")
    (project / "uv.lock").write_text("lock")
    if environment_present:
        (project / ".venv" / "bin").mkdir(parents=True)

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("missing worker must not spawn or install")

    monkeypatch.setattr("alpha_cli.ml_cmds.subprocess.run", forbidden)
    result = CliRunner().invoke(
        app, ["ml", "capabilities", "--worker-project", str(project), "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["qlib_version"] is None
    assert {row["name"] for row in payload["backends"]} == {
        "lightgbm",
        "linear",
        "catboost",
        "xgboost",
        "double_ensemble",
    }
    for row in payload["backends"]:
        assert row["status"] == "missing_dependency"
        assert row["versions"] == {}
        assert "isolated worker entrypoint is not installed" in row["reason"]
    assert not (project / ".venv" / "bin" / "alpha-qlib-worker").exists()


def test_existing_worker_capability_error_is_not_reported_as_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "worker"
    (project / ".venv" / "bin").mkdir(parents=True)
    (project / "pyproject.toml").write_text("[project]\nname='worker'\n")
    (project / "uv.lock").write_text("lock")
    (project / ".venv" / "bin" / "alpha-qlib-worker").touch()

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="probe fault sentinel")

    monkeypatch.setattr("alpha_cli.ml_cmds.subprocess.run", run)
    monkeypatch.setattr("alpha_cli.ml_cmds.shutil.which", lambda name: "/bin/uv")
    result = CliRunner().invoke(
        app, ["ml", "capabilities", "--worker-project", str(project), "--json"]
    )
    assert result.exit_code != 0
    assert "probe fault sentinel" in result.output


@pytest.mark.parametrize("route", ["/api/ml/capabilities", "/api/v3/ml/capabilities"])
def test_missing_worker_readiness_survives_web_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    from fastapi.testclient import TestClient

    from alpha_web import _ml
    from alpha_web.app import create_app

    project = tmp_path / "worker"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='worker'\n")
    (project / "uv.lock").write_text("lock")
    monkeypatch.setattr("alpha_cli.ml_cmds._default_worker_project", lambda: project)

    def run_cli(args: list[str], **kwargs: object) -> dict[str, Any]:
        result = CliRunner().invoke(app, args)
        assert result.exit_code == 0, result.output
        payload: dict[str, Any] = json.loads(result.output)
        return payload

    monkeypatch.setattr(_ml, "_run_json", run_cli)
    response = TestClient(create_app()).get(route)
    assert response.status_code == 200, response.text
    assert response.json()["qlib_version"] is None
    assert len(response.json()["backends"]) == 5
    assert all(row["status"] == "missing_dependency" for row in response.json()["backends"])
    assert not (project / ".venv").exists()


@pytest.mark.parametrize("malformed", ["directory", "dangling_symlink"])
def test_malformed_worker_entrypoint_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, malformed: str
) -> None:
    project = tmp_path / "worker"
    entrypoint = project / ".venv" / "bin" / "alpha-qlib-worker"
    entrypoint.parent.mkdir(parents=True)
    (project / "pyproject.toml").write_text("[project]\nname='worker'\n")
    (project / "uv.lock").write_text("lock")
    if malformed == "directory":
        entrypoint.mkdir()
    else:
        entrypoint.symlink_to(entrypoint.parent / "missing-target")

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("malformed worker must not execute")

    monkeypatch.setattr("alpha_cli.ml_cmds.subprocess.run", forbidden)
    result = CliRunner().invoke(
        app, ["ml", "capabilities", "--worker-project", str(project), "--json"]
    )
    assert result.exit_code != 0
    assert "isolated worker entrypoint is not a file" in result.output
