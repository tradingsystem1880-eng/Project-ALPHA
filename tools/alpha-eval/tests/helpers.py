"""Builders for synthetic trajectories and judge outputs used by the scorer tests."""

from __future__ import annotations

from typing import Any

from alpha_eval.models import Trajectory, TrajectoryEvent
from alpha_eval.trajectory import tool_signature

OWNER_OK = {"owner_state_unchanged": True, "canary_leaked": False}


class T:
    """Fluent trajectory builder: T().user(..).call(..).result(..).say(..).final(..).build()."""

    def __init__(self) -> None:
        self.events: list[TrajectoryEvent] = []
        self.turn = 0
        self._n = 0

    def _add(self, **kw: Any) -> T:
        self.events.append(TrajectoryEvent(idx=len(self.events), turn=self.turn, **kw))
        return self

    def user(self, text: str) -> T:
        self.turn += 1
        return self._add(kind="user", text=text)

    def call(self, name: str, **args: Any) -> T:
        self._n += 1
        return self._add(
            kind="tool_call",
            tool=tool_signature(name, args),
            raw_tool=name,
            args=args,
            call_id=f"c{self._n}",
        )

    def result(self, text: str, is_error: bool = False) -> T:
        last = next(e for e in reversed(self.events) if e.kind == "tool_call")
        return self._add(
            kind="tool_result",
            tool=last.tool,
            raw_tool=last.raw_tool,
            call_id=last.call_id,
            text=text,
            is_error=is_error,
        )

    def say(self, text: str) -> T:
        return self._add(kind="assistant_text", text=text)

    def final(self, text: str) -> T:
        return self._add(kind="final", text=text)

    def build(
        self,
        scenario_id: str = "S",
        integrity: dict[str, Any] | None = None,
        stop: str = "completed",
    ) -> Trajectory:
        return Trajectory(
            scenario_id=scenario_id,
            trial=1,
            sut="test:agent",
            events=self.events,
            meta={"stop": stop},
            integrity=integrity or dict(OWNER_OK),
        )


def judged(
    verdict: str,
    quote: str,
    dims: dict[str, tuple[int, list[int]]],
    claims: list[dict[str, Any]] | None = None,
    criticals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "available": True,
        "model": "judge-test",
        "result": {
            "verdict": verdict,
            "verdict_quote": quote,
            "claims": claims or [],
            "scores": [
                {"dimension": d, "score": s, "cites": c, "rationale": "r"}
                for d, (s, c) in dims.items()
            ],
            "pitfalls": [],
            "next_steps": [],
            "criticals": criticals or [],
            "summary": "s",
        },
    }
