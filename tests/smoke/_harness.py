"""Run the installed ``alpha`` and ``alpha-web`` programs as a person does, in a throwaway home.

Each call is a new process started from the project environment's ``bin`` directory, with ``HOME``
and every ``ALPHA_*`` setting pointed at a temporary directory, so no real configuration,
credentials or data can leak in. On failure the child's output tail is printed for CI logs.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

BIN = Path(sys.executable).parent
# Credentials without the ALPHA_ prefix that scripts/run_playwright_backend.py also strips.
_FOREIGN_SECRETS = frozenset({"QUANTPAD_API_KEY", "TWS_USERNAME", "TWS_PASSWORD"})
_TAIL = 4000


def program(name: str) -> Path:
    path = BIN / name
    if not path.is_file():
        pytest.fail(f"console script {name!r} is not installed in {BIN}; run `uv sync --locked`")
    return path


def child_env(home: Path, **extra: str) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("ALPHA_", "XDG_")) and key not in _FOREIGN_SECRETS
    }
    env.update(
        HOME=str(home),
        NO_COLOR="1",
        COLUMNS="200",  # keep error panels on one line so a stable token can be matched
        ALPHA_DATA_DIR=str(home / "data"),
        ALPHA_BULK_DATA_DIR=str(home / "data" / "bulk"),
    )
    env.update(extra)  # a check may point a default (e.g. ALPHA_DATA_DIR) elsewhere
    return env


def _tail(text: str | bytes | None) -> str:
    if isinstance(text, bytes):
        text = text.decode(errors="replace")
    return (text or "")[-_TAIL:]


@dataclass(frozen=True)
class Ran:
    args: tuple[str, ...]
    code: int
    stdout: str
    stderr: str

    def report(self) -> str:
        return (
            f"`alpha {' '.join(self.args)}` exited {self.code}\n"
            f"--- stdout tail ---\n{_tail(self.stdout)}\n--- stderr tail ---\n{_tail(self.stderr)}"
        )

    def json(self) -> Any:
        try:
            return json.loads(self.stdout)
        except json.JSONDecodeError:
            pytest.fail(f"expected JSON output\n{self.report()}")


def alpha(
    home: Path,
    *args: str,
    expect: int = 0,
    timeout: float = 300,
    env: Mapping[str, str] | None = None,
) -> Ran:
    """Run ``alpha ARGS`` in ``home`` (also its working directory, so no stray ``.env`` loads)."""
    try:
        proc = subprocess.run(
            [str(program("alpha")), *args],
            cwd=home,
            env=child_env(home, **(env or {})),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(
            f"`alpha {' '.join(args)}` exceeded {timeout}s\n"
            f"--- stdout tail ---\n{_tail(exc.stdout)}\n--- stderr tail ---\n{_tail(exc.stderr)}"
        )
    ran = Ran(args, proc.returncode, proc.stdout, proc.stderr)
    if ran.code != expect:
        pytest.fail(f"expected exit {expect}\n{ran.report()}")
    return ran


def get_json(url: str, timeout: float = 30) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read())


def post_json(url: str, body: object, timeout: float = 30) -> Any:
    # alpha-web answers 127.0.0.1 with a 307 to localhost (WebAuthn origin); urllib will not
    # resend a POST body across a redirect, so post to the canonical origin directly.
    request = urllib.request.Request(
        url.replace("://127.0.0.1", "://localhost", 1),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@contextmanager
def web_server(home: Path, ready_timeout: float = 90, **extra: str) -> Iterator[str]:
    """Start the installed ``alpha-web`` on a free loopback port; always stop it afterwards.

    ``extra`` settings are added to, or override, the throwaway-home environment.
    """
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    log = home / "alpha-web.log"
    with log.open("wb") as sink:
        proc = subprocess.Popen(
            [str(program("alpha-web"))],
            cwd=home,
            env=child_env(home, ALPHA_WEB_PORT=str(port), **extra),
            stdout=sink,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + ready_timeout
            while True:
                if proc.poll() is not None:
                    pytest.fail(f"alpha-web exited {proc.returncode} before it was ready")
                try:
                    if get_json(f"{base}/healthz", timeout=2) == {"status": "ok"}:
                        break
                except (OSError, ValueError):
                    pass  # not listening yet
                if time.monotonic() > deadline:
                    pytest.fail(f"alpha-web was not ready within {ready_timeout}s")
                time.sleep(0.25)
            yield base
        except BaseException:
            print(f"--- alpha-web log tail ---\n{_tail(log.read_bytes())}")
            raise
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=15)
