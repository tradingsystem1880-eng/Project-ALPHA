"""Trusted watchdog for one inference tree, retaining the caller's inherited global lock.

The worker and Codex share a fresh process group created by assistant_runtime. A dead CLI parent
or expired deadline kills that entire group; no model-generated command reaches this module.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time


def main() -> None:
    parent_pid = int(sys.argv[1])
    timeout = float(sys.argv[2])
    command = sys.argv[3:]
    prompt = sys.stdin.read()
    if os.getppid() != parent_pid:
        raise SystemExit(125)
    child = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    deadline = time.monotonic() + timeout
    pending: str | None = prompt
    while True:
        try:
            stdout, stderr = child.communicate(pending, timeout=0.2)
            sys.stdout.write(stdout)
            sys.stderr.write(stderr)
            raise SystemExit(child.returncode)
        except subprocess.TimeoutExpired:
            pending = None
            if os.getppid() != parent_pid or time.monotonic() >= deadline:
                os.killpg(os.getpgrp(), signal.SIGKILL)


if __name__ == "__main__":
    main()
