"""Repair legacy Codex normalization into a separate scoring artifact."""

from __future__ import annotations

import json
from pathlib import Path

from alpha_eval.models import Trajectory
from alpha_eval.trajectory import Normalizer


def replay_codex(original: Trajectory, raw_path: Path) -> Trajectory:
    if not original.sut.startswith("codex:") or not raw_path.exists():
        return original
    raw = [json.loads(line) for line in raw_path.read_text().splitlines() if line.strip()]
    users = [e for e in original.events if e.kind == "user"]
    completed = sum(e.get("type") == "turn.completed" for e in raw)
    if completed != len(users) or not users:
        return original.model_copy(
            update={
                "meta": original.meta
                | {"normalization_warning": "Unaligned raw turns; original retained"}
            }
        )
    norm = Normalizer()
    turn = 0
    norm.user(users[0].text)
    for event in raw:
        norm.codex(event)
        if event.get("type") == "turn.completed":
            turn += 1
            if turn < len(users):
                norm.user(users[turn].text)
    return original.model_copy(
        update={
            "events": norm.events,
            "meta": original.meta
            | {
                "normalization_revision": 2,
                "evidence_limits": "Search bodies may be absent; this does not prove fabrication",
            },
        }
    )
