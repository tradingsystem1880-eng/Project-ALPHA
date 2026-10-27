"""Executable assertions for the closed, synthetic development probe vocabulary."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
from collections.abc import Awaitable
from pathlib import Path
from typing import Any

from rdagent.core.experiment import Experiment
from rdagent.core.proposal import Hypothesis
from rdagent.core.serialization import UntrustedArtifactError
from rdagent.utils.workflow.loop import LoopBase, LoopMeta

from fixture_owner import FixtureOwner
from native_fixture import LABELS, METRICS, STAGES, FixtureFeedback, NativeFixtureLoop


async def _reject(awaitable: Awaitable[Any], message: str) -> None:
    try:
        await awaitable
    except RuntimeError as exc:
        assert message in str(exc), str(exc)
    else:
        raise AssertionError(f"expected rejection: {message}")


def _completed(owner: FixtureOwner) -> dict[str, Any]:
    loop = owner.loop
    assert type(loop) is NativeFixtureLoop
    assert type(loop) is not LoopBase
    assert loop.events == list(STAGES) == owner.charges
    assert owner.quiescent and owner.closed
    assert loop.step_idx[0] == 5
    output = loop.loop_prev_out[0]
    assert set(output) == {"_LOOP_IDX", *STAGES}
    assert set(output["direct_exp_gen"]) == {"propose", "exp_gen"}
    assert isinstance(output["direct_exp_gen"]["propose"], Hypothesis)
    exp = output["direct_exp_gen"]["exp_gen"]
    assert isinstance(exp, Experiment)
    assert output["coding"] is exp and output["running"] is exp
    assert exp.result == METRICS and exp.experiment_workspace is None
    assert exp.sub_workspace_list == [None]
    feedback = output["feedback"]
    assert type(feedback) is FixtureFeedback and feedback.label == loop.label
    assert feedback.metrics == exp.result and feedback.authority == "none"
    assert feedback.decision is False and feedback.acceptable is False
    for method in (bool, lambda item: item.is_acceptable(), lambda item: item.finished()):
        try:
            method(feedback)
        except TypeError as exc:
            assert "explicit label" in str(exc)
        else:
            raise AssertionError("feedback silently coerced to success")
    assert output["record"] is None
    assert loop.trace.hist == [(exp, feedback)]
    assert loop.trace.dag_parent == [()] and loop.trace.idx2loop_id == {0: 0}
    return {"events": loop.events, "label": feedback.label, "metrics": feedback.metrics}


async def _exercise(mode: str) -> dict[str, Any]:
    if mode in LABELS:
        owner = FixtureOwner(label=mode)
        await owner.start()
        result = _completed(owner)
        final = owner.loop.session_folder / "0" / "4_record"
        restored = NativeFixtureLoop.load(final, checkout=False, replace_timer=False)
        assert type(restored) is NativeFixtureLoop
        assert restored.events == owner.loop.events
        assert restored.trace.hist[0][1] == owner.loop.trace.hist[0][1]
        assert restored.queue.empty() and restored.semaphores == {}
        return {**result, "native_roundtrip": True}

    allowance = {"zero_allowance": 0, "partial_allowance": 2}.get(mode, 5)
    owner = FixtureOwner(allowance=allowance)
    if mode in {"zero_allowance", "partial_allowance"}:
        await _reject(owner.start(), "pre-effect allowance exhausted")
        assert owner.charges == owner.loop.events == list(STAGES[:allowance])
        assert owner.closed and owner.quiescent
        assert len(list(owner.loop.session_folder.glob("*/*"))) == allowance
        return {"effects": allowance, "closed": True}
    if mode == "unguarded":
        await _reject(owner.loop.run(loop_n=1), "no live fixture effect boundary")
        assert owner.loop.events == []
        return {"effects": 0}
    if mode == "post_effect_step_n":
        path = await owner.start(step_n=0)
        assert path is not None
        assert owner.loop.events == owner.charges == ["direct_exp_gen"]
        return {"step_n": 0, "effects": 1, "is_admission_budget": False}

    checkpoint = await owner.start(step_n=1)
    assert checkpoint is not None
    assert owner.loop.events == owner.charges == list(STAGES[:2])
    assert owner.quiescent and owner.loop.step_idx[0] == 2
    original = checkpoint.read_bytes()
    if mode == "resume":
        await _reject(owner.start(), "duplicate native start")
        await _reject(FixtureOwner().resume(checkpoint), "stale or foreign")
        await owner.resume(checkpoint)
        result = _completed(owner)
        await _reject(owner.resume(checkpoint), "closed fixture")
        assert checkpoint.read_bytes() == original
        return {**result, "native_resume": True, "duplicate_resume_rejected": True}
    if mode == "cancel":
        owner.wait_in_running = True
        continuation = asyncio.create_task(owner.resume(checkpoint))
        await asyncio.wait_for(owner.running_entered.wait(), timeout=2)
        await _reject(owner.resume(checkpoint), "concurrent native continuation")
        await _reject(owner.start(), "concurrent native continuation")
        continuation.cancel()
        try:
            await continuation
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("native continuation ignored cancellation")
        assert owner.running_quiescent and owner.quiescent and owner.closed
        assert owner.loop.events == list(STAGES[:2])
        assert owner.charges == list(STAGES[:3])  # Interrupted admitted work stays charged.
        assert "running" not in owner.loop.loop_prev_out[0]
        assert owner.loop.step_idx[0] == 3  # Upstream finally advances even on cancellation.
        assert checkpoint.read_bytes() == original
        assert not (checkpoint.parent / "2_running").exists()
        restored = NativeFixtureLoop.load(checkpoint, checkout=False, replace_timer=False)
        assert restored.step_idx[0] == 2  # Only successful checkpoint is a valid cursor.
        await _reject(owner.resume(checkpoint), "closed fixture")
        return {
            "cancelled": True,
            "quiescent": True,
            "concurrent_resume_rejected": True,
            "charged": owner.charges,
            "in_memory_cursor": 3,
            "checkpoint_cursor": 2,
        }
    if mode == "tamper":
        altered = bytearray(original)
        altered[-1] ^= 1
        checkpoint.write_bytes(altered)
        try:
            NativeFixtureLoop.load(checkpoint, checkout=False, replace_timer=False)
        except UntrustedArtifactError:
            pass
        else:
            raise AssertionError("upstream signed pickle accepted tampering")
        await _reject(owner.resume(checkpoint), "checkpoint bytes changed")
        assert owner.closed and owner.charges == list(STAGES[:2])
        return {"native_signature_rejected_tampering": True, "owner_digest_rejected": True}
    raise ValueError("unknown closed fixture probe")


def probe(mode: str) -> dict[str, Any]:
    assert NativeFixtureLoop.steps == list(STAGES)
    assert type(NativeFixtureLoop) is LoopMeta
    assert NativeFixtureLoop.run is LoopBase.run
    assert NativeFixtureLoop._run_step is LoopBase._run_step
    assert NativeFixtureLoop.dump is LoopBase.dump
    assert inspect.getattr_static(NativeFixtureLoop, "load") is inspect.getattr_static(
        LoopBase, "load"
    )
    result = asyncio.run(_exercise(mode))
    loop_source = Path(inspect.getfile(LoopBase))
    return {
        "mode": mode,
        "checks": result,
        "steps": NativeFixtureLoop.steps,
        "loop_source_sha256": hashlib.sha256(loop_source.read_bytes()).hexdigest(),
        "scheduler": "upstream LoopBase.run",
        "routes_enabled": False,
    }
