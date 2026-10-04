"""Signal-aware investigation host and parent-death watchdog for its isolated RPC tree."""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from typing import Any

from alpha_cli.investigation_case import Case


class InvestigationInterrupted(RuntimeError):
    """Known signal cancellation after the execution owner unwound its resources."""


def watched_argv(argv: Sequence[str]) -> list[str]:
    """Trusted wrapper shares the RPC-created process group with App Server descendants."""
    return [
        sys.executable,
        "-m",
        "alpha_cli.investigation_lifecycle",
        str(os.getpid()),
        "600",
        *argv,
    ]


def _watch(parent: int, seconds: float, command: list[str]) -> int:
    if os.getpgrp() != os.getpid():
        raise ValueError("watchdog requires its own isolated process group")
    if os.getppid() != parent:
        return 125
    child = subprocess.Popen(command)
    deadline = time.monotonic() + seconds
    while True:
        if os.getppid() != parent or time.monotonic() >= deadline:
            # This module runs only in the fresh group owned by CodexRpc.
            os.killpg(os.getpgrp(), signal.SIGKILL)
        try:
            child.wait(timeout=0.1)
            # EOF can make the leader exit before parent-death polling observes reparenting.
            # Its descendants must not outlive either the leader or this watchdog.
            os.killpg(os.getpgrp(), signal.SIGKILL)
            return child.returncode
        except subprocess.TimeoutExpired:
            # A polling timeout means the child is still running; recheck parent/deadline.
            continue


def run(
    case: Case,
    *,
    followup: str | None = None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Handle TERM/INT by cancelling the owner task, allowing journal/RPC cleanup."""
    from alpha_cli.codex_investigation import run_investigation

    async def execute() -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        task = asyncio.create_task(run_investigation(case, followup=followup, on_event=on_event))
        interrupted = False

        def cancel() -> None:
            nonlocal interrupted
            if not interrupted:
                interrupted = True
                task.cancel()

        signals = (signal.SIGTERM, signal.SIGINT)
        previous = {sig: signal.getsignal(sig) for sig in signals}
        try:
            for sig in signals:
                loop.add_signal_handler(sig, cancel)
            try:
                return await task
            except asyncio.CancelledError:
                raise InvestigationInterrupted(
                    "Investigation interrupted; spent budgets retained"
                ) from None
        finally:
            for sig in signals:
                loop.remove_signal_handler(sig)
                signal.signal(sig, previous[sig])

    return asyncio.run(execute())


if __name__ == "__main__":
    raise SystemExit(_watch(int(sys.argv[1]), float(sys.argv[2]), sys.argv[3:]))
