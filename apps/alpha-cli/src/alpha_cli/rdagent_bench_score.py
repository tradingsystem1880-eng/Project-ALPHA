"""Readings for the replay bench, from checks that already exist. No model judges another model.

R1 refusal: the proposal falls in a closed idea family or repeats a dropped idea. The family rule is
`workers/rdagent/idea_families.py` (standard library only); it runs in a child process, so no ALPHA
package imports the worker. R3 buildability: parse and schema checks only. R4 prefix (no future
data) needs the factor runtime and a frozen panel, so the bench names it as not run, with why.
A missing value is shown with its reason and never counts as zero.
"""

from __future__ import annotations

import ast
import json
import re
import statistics
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from alpha_cli.rdagent_bench_model import BenchError, StoredPrompt, output_path

WORKER = Path(__file__).resolve().parents[4] / "workers" / "rdagent"
HELPER = """
import json, sys
sys.path.insert(0, sys.argv[1])
import idea_families as f
out = []
for item in json.loads(sys.stdin.read()):
    try:
        f.declaration(item["description"]); ok = True
    except ValueError:
        ok = False
    out.append({"family": f.idea_family(item["name"], item["description"]), "declared": ok})
print(json.dumps(out))
"""
PREFIX_REASON = (
    "not run: it needs the factor runtime and a frozen price panel, and none is budgeted"
)
FENCE = re.compile(r"```(?:python)?\n(.*?)```", re.S)


@dataclass
class Reading:
    prompts: int = 0
    outputs: int = 0
    refusal: float | None = None
    refusal_reason: str | None = None
    buildable: float | None = None
    buildable_reason: str | None = None
    cost_per_call: float | None = None
    cost_reason: str | None = None
    latency_ms: float | None = None
    latency_reason: str | None = None
    prefix_reason: str = PREFIX_REASON
    by_prompt: dict[str, float] = field(default_factory=dict)


@dataclass
class Pair:
    count: int
    buildable_diff: float | None


@dataclass
class Scored:
    models: dict[str, Reading]
    pairs: dict[tuple[str, str], Pair]

    def text(self) -> str:
        return render(self)


def families(items: list[dict[str, str]]) -> list[dict[str, Any]]:
    if not items:
        return []
    done = subprocess.run(
        [sys.executable, "-I", "-c", HELPER, str(WORKER)],
        input=json.dumps(items),
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        raise BenchError(f"The family check failed: {done.stderr.strip()[-300:]}")
    result: list[dict[str, Any]] = json.loads(done.stdout)
    return result


def _proposal(text: str) -> dict[str, Any] | None:
    try:
        raw = json.loads(text)
    except ValueError:
        return None
    ok = (
        isinstance(raw, dict)
        and isinstance(raw.get("name"), str)
        and isinstance(raw.get("description"), str)
    )
    return raw if ok else None


def _code_builds(text: str) -> bool:
    match = FENCE.search(text)
    try:
        ast.parse(match.group(1) if match else text)
    except SyntaxError:
        return False
    return bool(text.strip())


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _load(store: Path, model: str, prompt: StoredPrompt, samples: int) -> list[dict[str, Any]]:
    rows = []
    for sample in range(samples):
        path = output_path(store, model, prompt.id, sample)
        if path.exists():
            rows.append(json.loads(path.read_text(encoding="utf-8")))
    return rows


def _reading(
    prompts: list[StoredPrompt],
    rows: dict[str, list[dict[str, Any]]],
    closed: set[str],
    dropped: set[str],
) -> Reading:
    flat = [(p, r) for p in prompts for r in rows[p.id]]
    reading = Reading(prompts=sum(1 for p in prompts if rows[p.id]), outputs=len(flat))
    parsed = {i: _proposal(r["text"]) for i, (p, r) in enumerate(flat) if p.stage == "proposal"}
    known = {i: x for i, x in parsed.items() if x is not None}
    info = dict(
        zip(
            known,
            families(
                [{"name": x["name"], "description": x["description"]} for x in known.values()]
            ),
            strict=True,
        )
    )
    refused = [
        bool(set(info[i]["family"].split("; ")) & closed) or x["name"].strip().lower() in dropped
        for i, x in known.items()
    ]
    if refused:
        reading.refusal = sum(refused) / len(refused)
    else:
        reading.refusal_reason = "no proposal output that parsed"
    builds: dict[str, list[float]] = {}
    for i, (p, r) in enumerate(flat):
        if p.stage == "proposal":
            ok = i in known and bool(info[i]["declared"])
        elif p.stage == "code":
            ok = _code_builds(r["text"])
        else:
            ok = _proposal(r["text"]) is not None
        builds.setdefault(p.id, []).append(1.0 if ok else 0.0)
    reading.by_prompt = {k: statistics.fmean(v) for k, v in builds.items()}
    reading.buildable = _mean([v for vs in builds.values() for v in vs])
    if reading.buildable is None:
        reading.buildable_reason = "no output stored"
    costs = [r["usd"] for _, r in flat if r["usd"] is not None]
    reading.cost_per_call = _mean(costs)
    reading.cost_reason = None if costs else "no call reported token counts"
    lat = [r["latency_ms"] for _, r in flat if r["latency_ms"] is not None]
    reading.latency_ms = statistics.median(lat) if lat else None
    reading.latency_reason = None if lat else "no call reported latency"
    return reading


def score_store(
    prompts: list[StoredPrompt],
    models: list[str],
    store: Path,
    closed: set[str],
    dropped: set[str],
    samples: int = 10,
) -> Scored:
    readings: dict[str, Reading] = {}
    for model in models:
        rows = {p.id: _load(store, model, p, samples) for p in prompts}
        readings[model] = _reading(prompts, rows, closed, dropped)
    pairs: dict[tuple[str, str], Pair] = {}
    for i, a in enumerate(models):
        for b in models[i + 1 :]:
            shared = set(readings[a].by_prompt) & set(readings[b].by_prompt)
            diffs = [readings[a].by_prompt[k] - readings[b].by_prompt[k] for k in sorted(shared)]
            pairs[(a, b)] = Pair(count=len(diffs), buildable_diff=_mean(diffs))
    return Scored(models=readings, pairs=pairs)


def _num(value: float | None, reason: str | None, fmt: str) -> str:
    return format(value, fmt) if value is not None else f"unknown ({reason})"


def render(scored: Scored) -> str:
    lines = ["Readings for each model. Each is a measurement, not a verdict."]
    for model, r in scored.models.items():
        lines += [
            f"{model}: {r.prompts} prompts, {r.outputs} outputs",
            f"  refusal rate: {_num(r.refusal, r.refusal_reason, '.2f')}",
            f"  buildable (parse and schema only): {_num(r.buildable, r.buildable_reason, '.2f')}",
            f"  no-future-data prefix check: {r.prefix_reason}",
            f"  cost per call, USD: {_num(r.cost_per_call, r.cost_reason, '.4f')}",
            f"  median latency, ms: {_num(r.latency_ms, r.latency_reason, '.0f')}",
        ]
    for (a, b), pair in scored.pairs.items():
        lines.append(
            f"{a} minus {b}, buildable, same prompts: "
            f"{_num(pair.buildable_diff, 'no shared prompt', '+.2f')} over {pair.count} prompts"
        )
    lines.append(
        "What this shows: the same prompt went to every model, so each difference is within one "
        "prompt. 30 pairs can show a large gap, about 3 prompts in 10 or more. They cannot show a "
        "small gap, and they say nothing about trading results."
    )
    return "\n".join(lines)
