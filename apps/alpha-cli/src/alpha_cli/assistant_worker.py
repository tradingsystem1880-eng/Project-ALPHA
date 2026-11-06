"""Trusted watchdog for one inference tree, retaining the caller's inherited global lock.

The watchdog survives its model group's termination and retains the inherited lock until
cleanup completes. No model-generated command reaches this module.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import time
from types import FrameType


def _reap_group(child: subprocess.Popen[str]) -> None:
    # communicate() may already have reaped a successful child. Never authorize a
    # destructive numeric-group signal from that released identity.
    if child.returncode is None:
        # Group absence is not a wait receipt; still reap our direct child.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGKILL)
        child.wait()
    # No destructive signals after releasing the leader's PID. Keep the lock if
    # cleanup cannot yet be established, including an unavailable orphan reaper.
    while True:
        try:
            os.killpg(child.pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.02)


def main() -> None:
    parent_pid = int(sys.argv[1])
    timeout = float(sys.argv[2])
    command = sys.argv[3:]
    stopping = False
    launching = False
    child: subprocess.Popen[str] | None = None

    def stop(signum: int, frame: FrameType | None) -> None:
        nonlocal stopping
        stopping = True
        if not launching:
            raise SystemExit(125)  # Interrupt stdin before any child can exist.

    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        prompt = sys.stdin.read()
        if stopping or os.getppid() != parent_pid:
            raise SystemExit(125)
        deadline = time.monotonic() + timeout
        # Cancellation during Popen must not raise before its handle is assigned.
        launching = True
        child = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        pending: str | None = prompt
        while True:
            if stopping or os.getppid() != parent_pid or time.monotonic() >= deadline:
                raise SystemExit(137)
            try:
                stdout, stderr = child.communicate(pending, timeout=0.2)
                if stopping or os.getppid() != parent_pid:
                    raise SystemExit(137)
                sys.stdout.write(stdout)
                sys.stderr.write(stderr)
                raise SystemExit(child.returncode)
            except subprocess.TimeoutExpired:
                pending = None
    finally:
        if child is not None:
            _reap_group(child)
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    main()
