"""Deterministic components injected into UNMODIFIED pinned stock RDLoop."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING

from rdagent.components.workflow.conf import BasePropSetting
from rdagent.components.workflow.rd_loop import RDLoop
from rdagent.core.developer import Developer
from rdagent.core.experiment import Experiment, ExperimentPlan, FBWorkspace, Task
from rdagent.core.knowledge_base import KnowledgeBase
from rdagent.core.proposal import (
    Experiment2Feedback,
    Hypothesis,
    Hypothesis2Experiment,
    HypothesisFeedback,
    HypothesisGen,
    Trace,
)
from rdagent.core.scenario import Scenario

if TYPE_CHECKING:
    from stock_fixture_entry import StockRequest

ExperimentType = Experiment[Task, FBWorkspace, FBWorkspace]
TraceType = Trace[Scenario, KnowledgeBase]

STAGES = ["direct_exp_gen", "coding", "running", "feedback", "record"]
ACTIVE: ContextVar[Effects | None] = ContextVar("stock_fixture_effects", default=None)
FIXTURE_BINDING_ATTR = "alpha_fixture_binding"
RESULT = {"synthetic_score": -0.125, "unit": "fixture_only"}


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def active_effects() -> Effects:
    guard = ACTIVE.get()
    if guard is None:
        raise RuntimeError("stock fixture active guard is unavailable")
    return guard


class SyntheticScenario(Scenario):
    @property
    def background(self) -> str:
        return "Fixed synthetic stock RDLoop wiring; no research authority."

    @property
    def rich_style_description(self) -> str:
        return self.background

    def get_scenario_all_desc(
        self,
        task: Task | None = None,
        filtered_tag: str | None = None,
        simple_background: bool | None = None,
    ) -> str:
        return self.background

    def get_runtime_environment(self) -> str:
        return "synthetic components; no providers, tools or generated code"


class Generator(HypothesisGen):
    def gen(self, trace: TraceType, plan: ExperimentPlan | None = None) -> Hypothesis:
        active_effects().charge("direct_exp_gen", "model")
        return Hypothesis("fixed synthetic stock hypothesis", *["synthetic fixture only"] * 5)


class Converter(Hypothesis2Experiment[ExperimentType]):
    def convert(self, hypothesis: Hypothesis, trace: TraceType) -> ExperimentType:
        return Experiment([Task("fixed synthetic task")], hypothesis=hypothesis)


class Coder(Developer[ExperimentType]):
    def develop(self, exp: ExperimentType) -> ExperimentType:
        active_effects().charge("coding", "tool")
        # No code generation, workspace creation or shell execution.
        exp.sub_results["synthetic_coded"] = 1.0
        return exp


class Runner(Developer[ExperimentType]):
    def develop(self, exp: ExperimentType) -> ExperimentType:
        active_effects().charge("running", "tool")
        exp.result = dict(RESULT)
        return exp


class Summarizer(Experiment2Feedback):
    def generate_feedback(
        self,
        exp: ExperimentType,
        trace: TraceType,
        exception: Exception | None = None,
    ) -> HypothesisFeedback:
        active_effects().charge("feedback", "model")
        return HypothesisFeedback(
            reason="fixed synthetic unaccepted feedback", decision=False, acceptable=False
        )


class GuardedTrace(Trace[Scenario, KnowledgeBase]):
    def sync_dag_parent_and_hist(
        self,
        exp_and_fb: Trace.NodeType,
        cur_loop_id: int,
    ) -> None:
        active_effects().charge("record", None)
        return super().sync_dag_parent_and_hist(exp_and_fb, cur_loop_id)


class Effects:
    """Ephemeral counters outside native pickle; never reservation or quota accounting."""

    def __init__(self, request: StockRequest) -> None:
        self.request = request
        self.stages: list[str] = []
        self.model = 0
        self.tool = 0
        self.closed = False
        self.paused = False
        self.checkpoint_sha256: str | None = None
        self.persist("running")

    def persist(self, state: str) -> None:
        # Advisory evidence only: charge occurs BEFORE the stage body. Never restore
        # counters/authority from this file or from the native signed checkpoint.
        value = {
            "schema": "StockRDLoopProgressV1",
            "request": self.request,
            "request_sha256": digest(self.request),
            "state": state,
            "attempted_stages": list(self.stages),
            "fake_model_attempts": sum(s in self.stages for s in ("direct_exp_gen", "feedback")),
            "simulated_model_counter": self.model,
            "fake_tool_attempts": self.tool,
            "continuation_checkpoint_sha256": self.checkpoint_sha256,
            "actual_model_calls": 0,
            "scientific_acceptance": "not_admitted",
        }
        raw = (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()
        if len(raw) > 8192:
            raise RuntimeError("stock progress exceeds bound")
        temporary = Path("stock-progress.tmp")
        with temporary.open("wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace("stock-progress.json")

    def charge(self, stage: str, kind: str | None) -> None:
        if (
            self.closed
            or self.paused
            or len(self.stages) >= self.request["loop_steps"]
            or stage != STAGES[len(self.stages)]
        ):
            raise RuntimeError("stock synthetic effect denied")
        if (
            kind == "model"
            and self.model >= self.request["model_calls"]
            or kind == "tool"
            and self.tool >= self.request["tool_calls"]
        ):
            raise RuntimeError("stock synthetic attempt limit exhausted")
        self.stages.append(stage)
        if kind == "model":
            self.model += 1
        if kind == "tool":
            self.tool += 1
        self.persist("running")
        if stage == "running" and self.request["mode"] == "cancel":
            raise asyncio.CancelledError("synthetic interruption before runner body")


async def _continue(loop: RDLoop, guard: Effects, step_n: int | None) -> None:
    if guard.closed or guard.paused:
        raise RuntimeError("stock fixture continuation closed")
    token = ACTIVE.set(guard)
    before = asyncio.all_tasks()
    try:
        # Native step_n is post-effect; guard.charge is the separate pre-effect limit.
        loop.step_n = None
        await loop.run(loop_n=1, step_n=step_n)
    except BaseException as error:
        guard.closed = True
        guard.persist("cancelled" if isinstance(error, asyncio.CancelledError) else "failed")
        raise
    finally:
        tasks = asyncio.all_tasks() - before
        for task in tasks:
            task.cancel()
        try:
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            ACTIVE.reset(token)


async def run(request: StockRequest) -> dict[str, object]:
    guard = Effects(request)
    settings = BasePropSetting(
        _env_file=None,
        scen="stock_fixture.SyntheticScenario",
        hypothesis_gen="stock_fixture.Generator",
        hypothesis2experiment="stock_fixture.Converter",
        coder="stock_fixture.Coder",
        runner="stock_fixture.Runner",
        summarizer="stock_fixture.Summarizer",
    )
    loop = RDLoop(settings)
    loop.trace = GuardedTrace(loop.trace.scen)
    setattr(loop, FIXTURE_BINDING_ATTR, digest(request))
    assert type(loop) is RDLoop and loop.steps == STAGES
    await _continue(loop, guard, 1)  # Native semantics: proposal AND coding, then stop.
    assert guard.stages == STAGES[:2]
    checkpoint = loop.session_folder / "0/1_coding"
    original = checkpoint.read_bytes()
    Path("stock-checkpoint.bin").write_bytes(original)
    checkpoint_sha = hashlib.sha256(original).hexdigest()
    guard.checkpoint_sha256 = checkpoint_sha
    guard.persist("checkpoint_ready")
    if request["mode"] == "exhaust":
        guard.model = request["model_calls"]
    if request["mode"] == "tamper":
        checkpoint.write_bytes(original + b"synthetic tamper")
    # Verify exact own checkpoint bytes BEFORE native signed-pickle deserialization.
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != checkpoint_sha:
        guard.closed = True
        guard.persist("checkpoint_rejected")
        return {"status": "checkpoint_rejected", "charged_stages": guard.stages}
    restored = RDLoop.load(checkpoint, checkout=Path.cwd() / "continuation", replace_timer=False)
    if type(restored) is not RDLoop:
        raise RuntimeError("stock checkpoint native class differs")
    binding: object = getattr(restored, FIXTURE_BINDING_ATTR, None)
    if type(binding) is not str or binding != digest(request):
        raise RuntimeError("stock checkpoint request binding differs")
    try:
        await _continue(restored, guard, None)
    except asyncio.CancelledError:
        assert request["mode"] == "cancel" and guard.closed
        assert guard.stages == STAGES[:3] and not restored.trace.hist
        try:
            await _continue(restored, guard, None)
        except RuntimeError:
            return {
                "status": "cancelled",
                "charged_stages": guard.stages,
                "checkpoint_preserved": checkpoint.read_bytes() == original,
                "cancelled_continuation_rejected": True,
            }
        raise AssertionError("cancelled continuation accepted") from None
    except RuntimeError:
        if request["mode"] == "exhaust":
            assert guard.stages == STAGES[:3] and not restored.trace.hist
            return {"status": "attempt_limit_rejected", "charged_stages": guard.stages}
        raise
    guard.closed = True
    try:
        await _continue(restored, guard, None)
    except RuntimeError:
        replay_rejected = True
    else:
        raise AssertionError("replayed completed continuation")
    exp, feedback = restored.trace.hist[0]
    if not isinstance(exp.hypothesis, Hypothesis) or not isinstance(feedback, HypothesisFeedback):
        guard.persist("failed")
        raise RuntimeError("stock native result hypothesis or feedback shape differs")
    trace = {
        "schema": "StockRDLoopTraceV1",
        "request_sha256": digest(request),
        "native_class": type(restored).__module__ + "." + type(restored).__name__,
        "stages": guard.stages,
        "hist_count": len(restored.trace.hist),
        "dag_parent": restored.trace.dag_parent,
        "idx2loop_id": {str(k): v for k, v in restored.trace.idx2loop_id.items()},
        "hypothesis": exp.hypothesis.hypothesis,
        "result": exp.result,
        "decision": feedback.decision,
        "acceptable": feedback.acceptable,
        "scientific_acceptance": "not_admitted",
    }
    trace_bytes = (json.dumps(trace, sort_keys=True, allow_nan=False) + "\n").encode()
    Path("stock-trace.json").write_bytes(trace_bytes)
    receipt = {
        "schema": "StockRDLoopReceiptV1",
        "request": request,
        "source_sha256": "0266b2d63328f88fcaf6f239bf6d67f29c896b8161566f794ef69465b7788707",
        "trace_sha256": hashlib.sha256(trace_bytes).hexdigest(),
        "checkpoint_sha256": checkpoint_sha,
        "charged_stages": guard.stages,
        "fake_model_attempts": guard.model,
        "fake_tool_attempts": guard.tool,
        "actual_model_calls": 0,
        "resumed_without_repeating": guard.stages == STAGES,
        "checkpoint_unchanged": checkpoint.read_bytes() == original,
        "replay_rejected": replay_rejected,
        "routes_enabled": False,
        "scientific_acceptance": "not_admitted",
    }
    Path("stock-receipt.json").write_text(
        json.dumps(receipt, sort_keys=True, allow_nan=False) + "\n"
    )
    guard.persist("completed")
    return {"status": "completed", "charged_stages": guard.stages}
