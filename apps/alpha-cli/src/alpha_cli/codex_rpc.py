"""Bounded App Server JSONL transport; capability policy belongs to the trusted caller."""

from __future__ import annotations

import asyncio
import json
import os
import signal
from collections.abc import Mapping, Sequence
from contextlib import suppress
from pathlib import Path
from types import TracebackType
from typing import Any


class CodexRpcError(RuntimeError):
    """The peer rejected a request or the transport can no longer be trusted."""


class CodexRpc:
    def __init__(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
        timeout: float = 30,
        max_line_bytes: int = 1_048_576,
        max_events: int = 256,
    ) -> None:
        if timeout <= 0 or max_line_bytes < 128 or max_events < 1:
            raise ValueError("positive timeout, line limit >=128 and event limit >=1 required")
        self.argv, self.cwd, self.env = list(argv), cwd, dict(env)
        self.timeout, self.max_line_bytes = timeout, max_line_bytes
        self.events: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=max_events)
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._serial = 0
        self._write_lock = asyncio.Lock()
        self._failed = asyncio.Event()
        self._error: CodexRpcError | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._reader: asyncio.Task[None] | None = None

    async def __aenter__(self) -> CodexRpc:
        if self._process is not None or self._error is not None:
            raise CodexRpcError("transport cannot be restarted")
        self._process = await asyncio.create_subprocess_exec(
            *self.argv,
            cwd=self.cwd,
            env=self.env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            limit=self.max_line_bytes,
            start_new_session=True,
        )
        self._reader = asyncio.create_task(self._read())
        try:
            await self.request(
                "initialize",
                {
                    "clientInfo": {"name": "alpha", "version": "1.0.0"},
                    "capabilities": {"experimentalApi": True},
                },
            )
            await self.notify("initialized", {})
        except BaseException:
            await self.close()
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    def _kill(self, sig: signal.Signals) -> None:
        if self._process is not None:
            with suppress(ProcessLookupError):
                os.killpg(self._process.pid, sig)

    def _fail(self, message: str) -> None:
        if self._error is None:
            self._error = CodexRpcError(message)
            self._failed.set()
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(self._error)
            self._kill(signal.SIGKILL)

    async def _send(self, value: dict[str, Any]) -> None:
        if self._error is not None:
            raise self._error
        if self._process is None or self._process.stdin is None:
            raise CodexRpcError("transport is not started")
        wire = (json.dumps(value, allow_nan=False) + "\n").encode()
        if len(wire) > self.max_line_bytes:
            raise CodexRpcError("outgoing line exceeds limit")
        async with self._write_lock:
            self._process.stdin.write(wire)
            await self._process.stdin.drain()

    async def request(
        self,
        method: str,
        params: dict[str, Any],
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        self._serial += 1
        identity = self._serial
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[identity] = future
        try:
            async with asyncio.timeout(self.timeout if timeout is None else timeout):
                await self._send({"id": identity, "method": method, "params": params})
                return await future
        except TimeoutError as exc:
            self._fail(f"request timed out: {method}; outcome unknown, no replay")
            raise CodexRpcError(f"request timed out: {method}; outcome unknown, no replay") from exc
        except asyncio.CancelledError:
            self._fail(f"request cancelled: {method}; outcome unknown, no replay")
            raise
        except (BrokenPipeError, ConnectionResetError) as exc:
            self._fail("server input closed")
            raise CodexRpcError("server input closed") from exc
        finally:
            self._pending.pop(identity, None)
            if future.done() and not future.cancelled():
                future.exception()  # Retrieve errors also when sending failed before awaiting.

    async def notify(self, method: str, params: dict[str, Any]) -> None:
        try:
            async with asyncio.timeout(self.timeout):
                await self._send({"method": method, "params": params})
        except (TimeoutError, OSError, asyncio.CancelledError):
            self._fail(f"notification interrupted: {method}; outcome unknown, no replay")
            raise

    async def _read(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        try:
            while True:
                try:
                    wire = await self._process.stdout.readline()
                except ValueError as exc:
                    raise CodexRpcError("server line exceeds limit") from exc
                if not wire:
                    raise CodexRpcError("server stdout closed")
                if len(wire) > self.max_line_bytes or not wire.endswith(b"\n"):
                    raise CodexRpcError("invalid or oversized server line")
                try:
                    value = json.loads(wire)
                except (ValueError, UnicodeDecodeError) as exc:
                    raise CodexRpcError("invalid server JSON") from exc
                if not isinstance(value, dict):
                    raise CodexRpcError("server JSON must be an object")
                if "method" in value:
                    if "id" in value:
                        async with asyncio.timeout(self.timeout):
                            await self._send(
                                {
                                    "id": value["id"],
                                    "error": {
                                        "code": -32601,
                                        "message": "Client requests are not permitted",
                                    },
                                }
                            )
                    else:
                        self.events.put_nowait(value)
                else:
                    identity = value.get("id")
                    if type(identity) is not int or identity not in self._pending:
                        raise CodexRpcError("unexpected response id")
                    future = self._pending[identity]
                    if future.done() or ("error" in value) == ("result" in value):
                        raise CodexRpcError("invalid or duplicate response")
                    if "error" in value:
                        future.set_exception(CodexRpcError(str(value["error"])))
                    elif isinstance(value["result"], dict):
                        future.set_result(value["result"])
                    else:
                        raise CodexRpcError("response result must be an object")
        except asyncio.CancelledError:
            raise
        except (ValueError, RuntimeError, OSError, asyncio.QueueFull) as exc:
            self._fail("event buffer exhausted" if isinstance(exc, asyncio.QueueFull) else str(exc))

    async def next_event(self, *, timeout: float | None = None) -> dict[str, Any]:
        if self._error is not None:
            raise self._error
        event = asyncio.create_task(self.events.get())
        failed = asyncio.create_task(self._failed.wait())
        try:
            async with asyncio.timeout(self.timeout if timeout is None else timeout):
                await asyncio.wait((event, failed), return_when=asyncio.FIRST_COMPLETED)
                if self._error is not None:
                    raise self._error
                return event.result()
        finally:
            for task in (event, failed):
                task.cancel()
            await asyncio.gather(event, failed, return_exceptions=True)

    async def close(self) -> None:
        self._fail("transport closed")
        if self._reader is not None:
            self._reader.cancel()
            await asyncio.gather(self._reader, return_exceptions=True)
        if self._process is not None:
            await self._process.wait()
