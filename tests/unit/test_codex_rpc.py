"""Exercise the real pipe transport against local protocol peers, without model calls."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from alpha_cli.codex_rpc import CodexRpc, CodexRpcError

PEER = r"""
import json, sys
def send(value):
    wire = json.dumps(value) + "\n"
    sys.stdout.write(wire[:7]); sys.stdout.flush()
    sys.stdout.write(wire[7:]); sys.stdout.flush()
first = json.loads(sys.stdin.readline())
assert first["method"] == "initialize"
send({"id": first["id"], "result": {"userAgent": "fixture"}})
assert json.loads(sys.stdin.readline())["method"] == "initialized"
"""


def client(tmp_path: Path, body: str, **kwargs: Any) -> CodexRpc:
    return CodexRpc(
        [sys.executable, "-u", "-c", PEER + body],
        cwd=tmp_path,
        env={"PATH": os.environ["PATH"]},
        **kwargs,
    )


def test_interleaved_notifications_and_out_of_order_responses(tmp_path: Path) -> None:
    async def run() -> None:
        async with client(
            tmp_path,
            """
a = json.loads(sys.stdin.readline())
b = json.loads(sys.stdin.readline())
send({"method": "item/started", "params": {"item": "abc"}})
send({"id": b["id"], "result": {"method": b["method"]}})
send({"id": a["id"], "result": {"method": a["method"]}})
sys.stdin.read()
""",
        ) as rpc:
            first, second = await asyncio.gather(
                rpc.request("turn/start", {}), rpc.request("turn/interrupt", {})
            )
            assert first == {"method": "turn/start"}
            assert second == {"method": "turn/interrupt"}
            assert (await rpc.next_event())["method"] == "item/started"

    asyncio.run(run())


def test_timeout_ends_transport_without_replay(tmp_path: Path) -> None:
    async def run() -> None:
        async with client(
            tmp_path,
            """
request = json.loads(sys.stdin.readline())
open("request.txt", "w").write(request["method"])
sys.stdin.read()
""",
        ) as rpc:
            with pytest.raises(CodexRpcError, match="outcome unknown, no replay"):
                await rpc.request("turn/start", {}, timeout=0.1)
            with pytest.raises(CodexRpcError, match="timed out"):
                await rpc.request("turn/start", {})
            assert (tmp_path / "request.txt").read_text() == "turn/start"

    asyncio.run(run())


def test_event_overflow_fails_and_eof_wakes_event_consumer(tmp_path: Path) -> None:
    async def run() -> None:
        async with client(
            tmp_path,
            """
request = json.loads(sys.stdin.readline())
for i in range(3): send({"method": "progress", "params": {"i": i}})
sys.stdin.read()
""",
            max_events=1,
        ) as rpc:
            with pytest.raises(CodexRpcError, match="buffer exhausted"):
                await rpc.request("turn/start", {})
            with pytest.raises(CodexRpcError, match="buffer exhausted"):
                await rpc.next_event()
        async with client(tmp_path, "sys.stdin.readline()\nsys.exit(0)") as rpc:
            await rpc.notify("quit", {})
            with pytest.raises(CodexRpcError, match="closed"):
                await rpc.next_event()

    asyncio.run(run())


def test_cancelled_request_kills_process_group_and_discards_stderr(tmp_path: Path) -> None:
    async def run() -> None:
        rpc = client(
            tmp_path,
            """
import subprocess
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
open("pid.txt", "w").write(str(child.pid))
sys.stderr.write("x" * 2000000); sys.stderr.flush()
request = json.loads(sys.stdin.readline())
send({"method": "ready", "params": {}})
sys.stdin.read()
""",
        )
        async with rpc:
            request = asyncio.create_task(rpc.request("turn/start", {}))
            assert (await rpc.next_event())["method"] == "ready"
            request.cancel()
            with pytest.raises(asyncio.CancelledError):
                await request
        await rpc.close()
        child = int((tmp_path / "pid.txt").read_text())
        for _ in range(100):
            try:
                os.kill(child, 0)
            except ProcessLookupError:
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("child process survived transport shutdown")

    asyncio.run(run())


def test_server_requests_rejected_and_remote_error_propagated(tmp_path: Path) -> None:
    async def run() -> None:
        async with client(
            tmp_path,
            """
request = json.loads(sys.stdin.readline())
send({"id": "approval", "method": "item/commandExecution/requestApproval", "params": {}})
denial = json.loads(sys.stdin.readline())
assert denial["id"] == "approval" and denial["error"]["code"] == -32601
send({"id": request["id"], "error": {"code": -1, "message": "denied"}})
sys.stdin.read()
""",
        ) as rpc:
            with pytest.raises(CodexRpcError, match="denied"):
                await rpc.request("turn/start", {})

    asyncio.run(run())


@pytest.mark.parametrize(
    "body, message",
    [
        ('sys.stdout.write("x" * 2048); sys.stdout.flush(); sys.stdin.read()', "line"),
        ('print("not-json", flush=True); sys.stdin.read()', "JSON"),
        ("send([]); sys.stdin.read()", "object"),
        ('send({"id": 999, "result": {}}); sys.stdin.read()', "unexpected response"),
        ('send({"id": 2, "result": {}, "error": {}}); sys.stdin.read()', "invalid"),
        ("sys.exit(0)", "closed"),
    ],
)
def test_bad_stream_fails_pending_request(tmp_path: Path, body: str, message: str) -> None:
    async def run() -> None:
        async with client(tmp_path, "sys.stdin.readline()\n" + body, max_line_bytes=1024) as rpc:
            with pytest.raises(CodexRpcError, match=message):
                await rpc.request("turn/start", {})

    asyncio.run(run())
