"""Own one test command's descendants in a separate Linux subreaper process.

Never install this reaping loop in pytest or the application: only this dedicated
process owns the command and its adopted descendants. Other platforms exec the
original command and retain their native process ownership behavior.
"""

from __future__ import annotations

import ctypes
import math
import os
import signal
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path
from types import FrameType

_GRACE_SECONDS = 2.0


def _enable_subreaper() -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), "could not establish test descendant ownership")


def _signal_adopted(sig: int, already_sent: set[int]) -> None:
    # Some Linux kernels omit task/*/children. Select only our direct children
    # from stat metadata; we never signal or wait for a foreign parent's child.
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            continue  # An unrelated process may exit while /proc is enumerated.
        if int(fields[1]) != os.getpid():
            continue
        pid = int(entry.name)
        if pid not in already_sent:
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                continue
            already_sent.add(pid)


def main(argv: list[str]) -> int:
    limit: float | None = None
    if argv[:1] == ["--timeout"]:
        limit = float(argv[1])
        if not math.isfinite(limit) or limit <= 0:
            raise ValueError("owned-test timeout must be finite and positive")
        argv = argv[2:]
    if not argv or argv[0] != "--" or len(argv) < 2:
        raise ValueError("usage: run_owned_test.py -- COMMAND [ARG ...]")
    command = argv[1:]
    if sys.platform != "linux":
        if limit is not None:
            raise ValueError("owned-test timeout supervision is Linux-only")
        os.execvp(command[0], command)
        raise AssertionError("exec returned")
    _enable_subreaper()
    received: int | None = None

    def interrupted(sig: int, frame: FrameType | None) -> None:
        nonlocal received
        if received is None:
            received = sig

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, interrupted)
    process = subprocess.Popen(command, start_new_session=True)
    deadline = None if limit is None else time.monotonic() + limit
    timed_out = False
    status: int | None = None
    shutdown_at: float | None = None
    term_sent: set[int] = set()
    kill_sent: set[int] = set()
    cleanup_failed = False
    while True:
        try:
            pid, raw_status = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            break
        if pid:
            if pid == process.pid:
                status = os.waitstatus_to_exitcode(raw_status)
                process.returncode = status
                if shutdown_at is None:
                    shutdown_at = time.monotonic()
            continue
        now = time.monotonic()
        if deadline is not None and now >= deadline and received is None and status is None:
            timed_out = True
            received = signal.SIGTERM
            print(f"TimeoutExpired: owned test command exceeded {limit}s", file=sys.stderr)
        if received is not None and shutdown_at is None:
            shutdown_at = now
            with suppress(ProcessLookupError):
                os.killpg(process.pid, received)
            term_sent.add(process.pid)
        if shutdown_at is not None:
            elapsed = now - shutdown_at
            if received is not None:
                _signal_adopted(received, term_sent)
            elif elapsed >= _GRACE_SECONDS:
                if not cleanup_failed:
                    print("owned-test: command left live descendants; cleaning up", file=sys.stderr)
                cleanup_failed = True
                _signal_adopted(signal.SIGTERM, term_sent)
            kill_after = _GRACE_SECONDS if received is not None else 2 * _GRACE_SECONDS
            if elapsed >= kill_after:
                _signal_adopted(signal.SIGKILL, kill_sent)
            if elapsed >= kill_after + _GRACE_SECONDS:
                raise RuntimeError("owned-test: descendants could not be reaped after SIGKILL")
        time.sleep(0.01)
    if status is None:
        raise RuntimeError("owned-test: command exit status was not collected")
    if timed_out:
        return 124
    if cleanup_failed and status == 0:
        return 1
    return status if status >= 0 else 128 - status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
