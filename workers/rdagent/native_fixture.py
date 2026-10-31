"""Fixed synthetic operators on the real pinned native loop; no production dispatch."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, cast

from rdagent.core.experiment import Experiment, Task
from rdagent.core.knowledge_base import KnowledgeBase
from rdagent.core.proposal import Hypothesis, HypothesisFeedback, Trace
from rdagent.core.scenario import Scenario
from rdagent.utils.workflow.loop import LoopBase, LoopMeta

STAGES = ("direct_exp_gen", "coding", "running", "feedback", "record")
LABELS = ("SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "INVALID")
# Exact synthetic observations, never a derived classification or admitted evidence.
METRICS = (("net_return", -0.125, "fraction"), ("cost", 0.03125, "fraction"))
_ACTIVE: ContextVar[Any] = ContextVar("fixture_effect_boundary", default=None)
type FixtureExperiment = Experiment[Task, Any, Any]


class FixtureScenario(Scenario):
    def __init__(self, daily: bool = False) -> None:
        self._daily = daily

    @property
    def background(self) -> str:
        return (
            "Frozen daily rule/control; exploratory discovery, no promotion authority."
            if self._daily
            else "Fixed synthetic native conformance; authority none."
        )

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
        return (
            "qualified installed rule profile and canonical engine; no generated code"
            if self._daily
            else "isolated development worker; deterministic noop operators"
        )


@dataclass
class FixtureFeedback(HypothesisFeedback):
    label: str
    metrics: tuple[tuple[str, float, str], ...] = METRICS
    authority: str = "none"
    synthetic: bool = True

    def __post_init__(self) -> None:
        if self.label not in LABELS or self.metrics != METRICS:
            raise ValueError("only fixed synthetic feedback is supported")
        if self.authority != "none" or self.synthetic is not True:
            raise ValueError("fixture feedback cannot confer authority")
        # Native Trace expects ExperimentFeedback. Every synthetic label stays unaccepted.
        super().__init__(reason="synthetic fixture only", decision=False, acceptable=False)

    def __bool__(self) -> bool:
        raise TypeError("use the explicit label; feedback is not a success boolean")


class NativeFixtureLoop(LoopBase, metaclass=LoopMeta):
    """Only the five stage functions are public: LoopMeta treats public helpers as steps."""

    def __init__(self, label: str = "INCONCLUSIVE") -> None:
        if label not in LABELS:
            raise ValueError("unknown synthetic label")
        super().__init__()
        self.scenario = FixtureScenario()
        self.trace: Trace[FixtureScenario, KnowledgeBase] = Trace(self.scenario)
        self.label = label
        self.events: list[str] = []
        self.admission_binding: str | None = None
        self.rule_request: dict[str, Any] | None = None
        self.rule_profile: str | None = None

    def _admit(self, stage: str, prev_out: dict[str, Any]) -> None:
        boundary = _ACTIVE.get()
        if boundary is None:
            raise RuntimeError("no live fixture effect boundary")
        boundary.admit(self, stage, prev_out)

    async def direct_exp_gen(self, prev_out: dict[str, Any]) -> dict[str, Any]:
        self._admit("direct_exp_gen", prev_out)
        daily = (
            self.rule_request is not None
            and self.rule_request["study"].get("schema") == "FrozenDailyRuleStudyV1"
        )
        if daily:
            self.scenario = FixtureScenario(daily=True)
            self.trace = Trace(self.scenario)
        hypothesis = Hypothesis(
            *(
                [
                    "frozen daily discovery question; no promotion claim"
                    if daily
                    else "fixed synthetic hypothesis"
                ]
                * 6
            )
        )
        exp: FixtureExperiment = Experiment(
            [Task("frozen-daily-rule-control" if daily else "fixed-noop")], hypothesis=hypothesis
        )
        exp.local_selection = ()
        self.events.append("direct_exp_gen")
        return {"propose": hypothesis, "exp_gen": exp}

    def coding(self, prev_out: dict[str, Any]) -> FixtureExperiment:
        self._admit("coding", prev_out)
        exp = cast(FixtureExperiment, prev_out["direct_exp_gen"]["exp_gen"])
        self.events.append("coding")
        return exp  # No workspace, generated code, environment or coder is invoked.

    async def running(self, prev_out: dict[str, Any]) -> FixtureExperiment:
        self._admit("running", prev_out)
        boundary = _ACTIVE.get()
        if boundary.fail_in_running:
            raise RuntimeError("fixed synthetic native running failure")
        if boundary.wait_in_running:
            boundary.running_entered.set()
            try:
                await boundary.running_release.wait()
            finally:
                boundary.running_quiescent = True
        exp = cast(FixtureExperiment, prev_out["coding"])
        if self.rule_request is None:
            exp.result = METRICS
        else:
            from rule_probe import evaluate

            if self.rule_profile is None:
                raise ValueError("rule loop has no pinned profile")
            exp.result = evaluate(self.rule_request, self.rule_profile)
        self.events.append("running")
        return exp

    def feedback(self, prev_out: dict[str, Any]) -> HypothesisFeedback:
        self._admit("feedback", prev_out)
        feedback = (
            FixtureFeedback(self.label, prev_out["running"].result)
            if self.rule_request is None
            else HypothesisFeedback(
                reason=(
                    "exploratory daily rule/control; no promotion authority"
                    if self.rule_request["study"].get("schema") == "FrozenDailyRuleStudyV1"
                    else "synthetic position mechanics only"
                ),
                decision=False,
                acceptable=False,
            )
        )
        self.events.append("feedback")
        return feedback

    def record(self, prev_out: dict[str, Any]) -> None:
        self._admit("record", prev_out)
        self.trace.sync_dag_parent_and_hist(
            (prev_out["running"], prev_out["feedback"]), prev_out[self.LOOP_IDX_KEY]
        )
        self.events.append("record")
