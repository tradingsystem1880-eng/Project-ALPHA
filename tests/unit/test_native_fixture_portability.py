"""Non-Linux development hosts can import native code but cannot execute it."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn, cast

import pytest

from alpha_cli import _native_fixture_store as fixture_store
from alpha_cli import durable_lease
from alpha_cli import native_supervisor as supervisor
from alpha_cli.control_store import ControlStore
from alpha_core import DataError


@pytest.mark.parametrize("platform", ["darwin", "win32", "unknown"])
def test_unsupported_native_host_rejects_before_effects(
    platform: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def effect(*args: object, **kwargs: object) -> NoReturn:
        pytest.fail("unsupported native host attempted an effect")

    # Prepare the marker directly so this rejection test also runs on Darwin.
    with tempfile.TemporaryDirectory(prefix="alpha-native-fixture-") as directory:
        root = Path(directory).resolve()
        (root / "synthetic-only").write_text(supervisor._MARKER)
        store = ControlStore(root)
        monkeypatch.setattr(sys, "platform", platform)
        monkeypatch.setattr(ControlStore, "_open", effect)
        monkeypatch.setattr(supervisor, "_open_lock", effect)
        monkeypatch.setattr(fixture_store, "_open_lock", effect)
        monkeypatch.setattr(socket, "socket", effect)
        monkeypatch.setattr(subprocess, "Popen", effect)
        monkeypatch.setattr(signal, "signal", effect)
        monkeypatch.setattr(tempfile, "TemporaryDirectory", effect)
        monkeypatch.setattr(sys, "argv", ["owner", str(root), "job", "success", "2", "9"])
        actions: list[Callable[[], object]] = [
            lambda: supervisor.start_synthetic_owner(root, "job"),
            lambda: store.native_fixture_status("job", reconnect=True),
            lambda: store.cancel_native_fixture("job", reason="synthetic test"),
            supervisor._entry,
            lambda: supervisor.synthetic_workspace().__enter__(),
        ]
        for action in actions:
            with pytest.raises(DataError, match="linux-posix-v1 only"):
                action()


@pytest.mark.parametrize("platform", ["darwin", "win32"])
def test_retained_child_observer_rejects_without_accessing_process(
    platform: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "platform", platform)
    with pytest.raises(durable_lease.DurableLeaseError, match="requires Linux"):
        durable_lease._observe_retained_child(cast(subprocess.Popen[bytes], object()))


def test_native_imports_without_fcntl(tmp_path: Path) -> None:
    # Simulate Windows' missing module in a fresh interpreter. This is an import
    # boundary check on Linux, not Windows runtime qualification.
    code = """
import builtins
import sys
from alpha_cli import control_store
original = builtins.__import__
def without_fcntl(name, *args, **kwargs):
    if name == 'fcntl':
        raise ModuleNotFoundError('simulated Windows: no fcntl')
    return original(name, *args, **kwargs)
builtins.__import__ = without_fcntl
sys.platform = 'win32'
from alpha_cli import native_supervisor, _native_fixture_store
from alpha_core import DataError
try:
    native_supervisor.host_identity()
except DataError:
    pass
else:
    raise AssertionError('Windows unexpectedly admitted')
"""
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("capability", ["waitid", "WNOWAIT", "CLD_EXITED"])
@pytest.mark.parametrize("value", [None, False])
def test_unknown_observation_capability_denies_before_effects(
    capability: str, value: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    if sys.platform != "linux":
        pytest.skip("requires the Linux native execution profile")

    def effect(*args: object, **kwargs: object) -> NoReturn:
        pytest.fail("unknown observation capability attempted an effect")

    with supervisor.synthetic_workspace() as root:
        monkeypatch.setattr(os, capability, value)
        monkeypatch.setattr(supervisor, "_open_lock", effect)
        monkeypatch.setattr(signal, "signal", effect)
        monkeypatch.setattr(tempfile, "TemporaryDirectory", effect)
        for action in (supervisor._entry, lambda: supervisor.start_synthetic_owner(root, "job")):
            with pytest.raises(DataError, match="non-reaping child observation"):
                action()
