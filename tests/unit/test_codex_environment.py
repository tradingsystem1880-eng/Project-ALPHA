"""Dedicated Codex configuration and actual-RPC isolation probes fail closed."""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from alpha_cli.codex_environment import preflight, prepare
from alpha_cli.codex_policy import config_text, launch_config
from alpha_core import DataError


@pytest.fixture(autouse=True)
def isolated_owner_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)


@pytest.fixture
def synthetic_codex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Exercise executable discovery without using an installed Codex runtime."""
    directory = tmp_path / "test-bin"
    directory.mkdir()
    executable = directory / "codex"
    executable.write_text("#!/bin/sh\nexit 99\n")
    executable.chmod(0o700)
    monkeypatch.setenv("PATH", str(directory))
    return executable


def credential(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    source = tmp_path / "source-home"
    source.mkdir()
    (source / "auth.json").write_text("synthetic-secret")
    monkeypatch.setenv("CODEX_HOME", str(source))
    monkeypatch.setenv("UNRELATED_SECRET", "must-not-inherit")
    return source / "auth.json"


def test_prepare_isolated_configuration_and_credential_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, synthetic_codex: Path
) -> None:
    import sys

    auth = credential(tmp_path, monkeypatch)
    case = tmp_path / "case"
    case.mkdir()
    argv, workspace, env = prepare(case)
    assert argv == [str(synthetic_codex), "app-server"]
    assert workspace == case / "workspace"
    assert set(env) == {"HOME", "PATH", "TMPDIR", "LANG", "CODEX_HOME"}
    assert env["CODEX_HOME"] == str(case / "codex-home")
    linked = Path(env["CODEX_HOME"]) / "auth.json"
    assert linked.is_symlink() and linked.resolve() == auth
    config = Path(env["CODEX_HOME"]) / "config.toml"
    assert config.read_text() == config_text(
        launch_config(case, workspace, python=Path(sys.executable))
    )
    assert "synthetic-secret" not in config.read_text()
    assert prepare(case) == (argv, workspace, env)
    assert list(workspace.iterdir()) == []


def test_missing_credentials_block_without_leaking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "absent"))
    with pytest.raises(DataError, match="auth.json"):
        prepare(tmp_path / "case")


def test_missing_executable_blocks_before_creating_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, synthetic_codex: Path
) -> None:
    credential(tmp_path, monkeypatch)
    synthetic_codex.unlink()
    case = tmp_path / "case"
    with pytest.raises(DataError, match="executable is unavailable"):
        prepare(case)
    assert not case.exists()


def test_config_drift_and_directory_symlink_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, synthetic_codex: Path
) -> None:
    credential(tmp_path, monkeypatch)
    case = tmp_path / "case"
    case.mkdir()
    prepare(case)
    config = case / "codex-home" / "config.toml"
    config.write_text("ambient = true")
    with pytest.raises(DataError, match="config"):
        prepare(case)
    other = tmp_path / "other"
    other.mkdir()
    (other / "workspace").symlink_to(case / "workspace")
    with pytest.raises(DataError, match="symlink"):
        prepare(other)


class Peer:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        self.params: dict[str, Any] = {}

    async def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        assert method == "command/exec"
        self.params = params
        assert "sandboxPolicy" not in params
        assert params["command"][:2] == ["/usr/bin/python3", "-c"]
        return self.result


def test_preflight_uses_actual_rpc_and_cleans_up(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    peer = Peer({"exitCode": 0, "stdout": "alpha-isolation-verified\n", "stderr": ""})
    receipt = asyncio.run(preflight(peer, workspace))
    assert receipt["verified"] is True
    assert len(receipt["probes"]) == 8
    assert peer.params["timeoutMs"] == 10_000
    assert set(tmp_path.iterdir()) == {workspace}
    assert list(workspace.iterdir()) == []


@pytest.mark.parametrize(
    "response",
    [
        {"exitCode": 1, "stdout": "secret"},
        {"exitCode": 0, "stdout": ""},
        {"exitCode": False, "stdout": "alpha-isolation-verified\n"},
    ],
)
def test_preflight_failure_is_redacted_and_cleans_up(
    tmp_path: Path, response: dict[str, Any]
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with pytest.raises(DataError, match="isolation preflight") as error:
        asyncio.run(preflight(Peer(response), workspace))
    assert "secret" not in str(error.value)
    assert list(workspace.iterdir()) == []
    assert set(tmp_path.iterdir()) == {workspace}


def test_existing_workspace_contents_and_wrong_auth_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, synthetic_codex: Path
) -> None:
    credential(tmp_path, monkeypatch)
    case = tmp_path / "case"
    prepare(case)
    artifact = case / "workspace" / "unexpected"
    artifact.write_text("do not expose")
    with pytest.raises(DataError, match="empty"):
        prepare(case)
    artifact.unlink()
    link = case / "codex-home" / "auth.json"
    link.unlink()
    link.symlink_to(tmp_path / "missing")
    with pytest.raises(DataError, match="auth reference"):
        prepare(case)


def test_cancelled_preflight_cleans_only_its_canaries(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    user_file = tmp_path / "keep"
    user_file.write_text("keep")

    class Cancelled:
        async def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(preflight(Cancelled(), workspace))
    assert set(tmp_path.iterdir()) == {workspace, user_file}
    assert list(workspace.iterdir()) == []
