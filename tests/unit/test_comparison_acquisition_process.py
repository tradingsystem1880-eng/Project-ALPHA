"""Real process-group cleanup and closed environment at the acquisition boundary."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from alpha_cli.comparison_acquisition import _dispatch


@pytest.mark.skipif(os.name != "posix", reason="process-group contract requires POSIX")
def test_real_acquisition_deadline_reaps_worker_and_descendant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only substitute the harmless worker program and shorten its actual wait deadline."""
    state_path = tmp_path / "worker.json"
    worker = r"""
import json, os, signal, subprocess, sys, time
from pathlib import Path
root = Path(sys.argv[1])
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
def finish(signum, frame):
    child.wait(timeout=5)
    (root / "reaped.json").write_text(json.dumps({"returncode": child.returncode}))
    raise SystemExit(0)
signal.signal(signal.SIGTERM, finish)
(root / "worker.json").write_text(json.dumps({
    "pid": os.getpid(), "child": child.pid, "group": os.getpgrp(),
    "keys": sorted(os.environ),
    "home": os.environ.get("HOME"), "tmp": os.environ.get("TMPDIR"),
    "cwd": os.getcwd(),
    "key_forwarded": os.environ.get("ALPHA_TIINGO_API_KEY") == "fixture-only",
}))
time.sleep(60)
"""
    children: list[subprocess.Popen[bytes]] = []

    class ShortDeadline(subprocess.Popen[bytes]):
        def wait(self, timeout: float | None = None) -> int:
            if timeout == 90:
                deadline = time.monotonic() + 5
                while not state_path.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                return super().wait(timeout=0.05)
            return super().wait(timeout=timeout)

    def launch(args: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        assert args == [
            sys.executable,
            "-m",
            "alpha_cli.comparison_acquisition_worker",
            str(tmp_path),
            "0",
        ]
        assert set(kwargs["env"]) <= {
            "PATH",
            "HOME",
            "TMPDIR",
            "PYTHONDONTWRITEBYTECODE",
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "POLARS_MAX_THREADS",
            "ALPHA_TIINGO_API_KEY",
        }
        assert kwargs["env"]["HOME"] == str(tmp_path / "worker-home")
        assert kwargs["env"]["TMPDIR"] == str(tmp_path / "worker-tmp")
        assert kwargs["env"]["PATH"] == "/usr/bin:/bin:/usr/sbin:/sbin"
        assert kwargs["cwd"] == tmp_path
        assert kwargs["start_new_session"] is True
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["stdout"] == subprocess.DEVNULL
        assert kwargs["stderr"] == subprocess.DEVNULL
        process = ShortDeadline([sys.executable, "-c", worker, str(tmp_path)], **kwargs)
        children.append(process)
        return process

    monkeypatch.setenv("ALPHA_TIINGO_API_KEY", "fixture-only")
    monkeypatch.setenv("ALPHA_PRIVATE_OWNER_CANARY", "must-not-reach-worker")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-worker")
    monkeypatch.setattr(subprocess, "Popen", launch)
    try:
        result = _dispatch(tmp_path, 0)
        assert result == {
            "status": "failed",
            "error_type": "TimeoutExpired",
            "message": "worker deadline exceeded",
        }
        assert len(children) == 1 and children[0].returncode is not None
        state = json.loads(state_path.read_text())
        assert state["pid"] == state["group"] == children[0].pid
        assert state["key_forwarded"] is True
        assert Path(state["home"]).resolve() == (tmp_path / "worker-home").resolve()
        assert Path(state["tmp"]).resolve() == (tmp_path / "worker-tmp").resolve()
        assert Path(state["cwd"]).resolve() == tmp_path.resolve()
        assert set(state["keys"]) <= {
            "PATH",
            "HOME",
            "TMPDIR",
            "PYTHONDONTWRITEBYTECODE",
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "POLARS_MAX_THREADS",
            "ALPHA_TIINGO_API_KEY",
            "LC_CTYPE",  # Python locale initialization.
            "__CF_USER_TEXT_ENCODING",  # Added by macOS runtime startup.
        }
        assert json.loads((tmp_path / "reaped.json").read_text())["returncode"] == -signal.SIGTERM
        for pid in (state["pid"], state["child"]):
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)
        with pytest.raises(ChildProcessError):
            os.waitpid(children[0].pid, os.WNOHANG)
    finally:
        for process in children:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
