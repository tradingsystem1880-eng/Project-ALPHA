"""Ephemeral effect guard for one trusted fixture process, never a recovery ledger."""

from __future__ import annotations

import asyncio
import hashlib
import threading
from pathlib import Path
from typing import Any

from native_fixture import _ACTIVE, STAGES, NativeFixtureLoop


class FixtureOwner:
    def __init__(
        self,
        *,
        label: str = "INCONCLUSIVE",
        allowance: int = 5,
        admission_binding: str | None = None,
    ) -> None:
        if type(allowance) is not int or not 0 <= allowance <= len(STAGES):
            raise ValueError("invalid fixed fixture allowance")
        self.loop = NativeFixtureLoop(label)
        self.admission_binding = admission_binding
        self.loop.admission_binding = admission_binding
        self.allowance = allowance
        self.charges: list[str] = []  # Kept outside the native pickle; never refunded by load.
        self.wait_in_running = False
        self.running_entered = asyncio.Event()
        self.running_release = asyncio.Event()
        self.fail_in_running = False
        self.running_quiescent = False
        self.quiescent = True
        self.closed = False
        self.started = False
        self._lock = threading.Lock()
        self._checkpoint: tuple[Path, str] | None = None

    def admit(self, loop: NativeFixtureLoop, stage: str, prev_out: dict[str, Any]) -> None:
        if self.closed or loop is not self.loop or not self._lock.locked():
            raise RuntimeError("fixture owner is not active")
        index = len(self.charges)
        if index >= self.allowance:
            raise RuntimeError("fixture pre-effect allowance exhausted")
        if stage != STAGES[index] or prev_out.get(loop.LOOP_IDX_KEY) != 0:
            raise RuntimeError("unexpected fixture stage or loop")
        if set(prev_out) != {loop.LOOP_IDX_KEY, *STAGES[:index]}:
            raise RuntimeError("native stage input contract mismatch")
        self.charges.append(stage)

    async def start(self, *, step_n: int | None = None) -> Path | None:
        return await self._continue(None, step_n)

    async def resume(self, checkpoint: Path) -> Path | None:
        return await self._continue(checkpoint, None)

    async def _continue(self, checkpoint: Path | None, step_n: int | None) -> Path | None:
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("concurrent native continuation rejected")
        continuing = False
        try:
            if self.closed:
                raise RuntimeError("closed fixture cannot continue")
            if checkpoint is None:
                if self.started:
                    raise RuntimeError("duplicate native start rejected")
                self.started = True
                continuing = True
            else:
                if self._checkpoint is None or checkpoint != self._checkpoint[0]:
                    raise RuntimeError("stale or foreign checkpoint rejected")
                if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != self._checkpoint[1]:
                    self.closed = True
                    raise RuntimeError("checkpoint bytes changed")
                self._checkpoint = None  # Fail closed even if deserialization fails.
                continuing = True
                try:
                    restored = NativeFixtureLoop.load(
                        checkpoint, checkout=False, replace_timer=False
                    )
                    if type(restored) is not NativeFixtureLoop:
                        raise RuntimeError("checkpoint does not contain the native fixture")
                    if restored.admission_binding != self.admission_binding:
                        raise RuntimeError("checkpoint belongs to another admitted run")
                    self.loop = restored
                except BaseException:
                    self.closed = True
                    raise
            # Native step_n is a post-step stop knob, never the effect allowance above.
            self.loop.step_n = None
            token = _ACTIVE.set(self)
            before = asyncio.all_tasks()
            self.quiescent = False
            try:
                await self.loop.run(step_n=step_n, loop_n=1)
            except BaseException:
                self.closed = True
                self._checkpoint = None
                raise
            finally:
                # Pinned run cancels its tasks but does not await them. Drain before unlock/load.
                remaining = asyncio.all_tasks() - before
                for task in remaining:
                    task.cancel()
                interrupted = False
                try:
                    if remaining:
                        drained = asyncio.gather(*remaining, return_exceptions=True)
                        while not drained.done():
                            try:
                                await asyncio.shield(drained)
                            except asyncio.CancelledError:
                                # A repeated cancellation must not release the owner early.
                                interrupted = True
                        for outcome in drained.result():
                            if isinstance(outcome, BaseException) and not isinstance(
                                outcome, asyncio.CancelledError
                            ):
                                raise RuntimeError("native cleanup task failed") from outcome
                    self.quiescent = not (asyncio.all_tasks() - before)
                finally:
                    _ACTIVE.reset(token)
                if interrupted:
                    raise asyncio.CancelledError
            if not self.quiescent:
                self.closed = True
                raise RuntimeError("native tasks did not quiesce")
            if self.loop.events == list(STAGES):
                self.closed = True
                return None
            index = len(self.loop.events) - 1
            path = self.loop.session_folder / "0" / f"{index}_{STAGES[index]}"
            self._checkpoint = (path, hashlib.sha256(path.read_bytes()).hexdigest())
            return path
        except BaseException:
            if continuing:
                self.closed = True
                self._checkpoint = None
            raise
        finally:
            self._lock.release()
