"""Frozen three-arm development comparison; no automated research-quality grade."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Literal

from alpha_eval.investigation_cases import digest
from alpha_eval.investigation_codex import CodexProposer
from alpha_eval.investigation_demo import run_case, write_once
from alpha_eval.investigation_runner import Worker, run_demo

MODES: tuple[Literal["legacy", "prechecked", "fixed"], ...] = ("legacy", "prechecked", "fixed")
TOKEN_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens")


def frozen_schedule() -> list[dict[str, str]]:
    return [
        dict(case=case, mode=MODES[(position + offset) % 3])
        for offset, case in enumerate(("conditional", "indicator_null", "accounting_defect"))
        for position in range(3)
    ]


def resource_record(trial: Path, report: dict[str, Any]) -> dict[str, Any]:
    totals = dict.fromkeys(TOKEN_KEYS, 0)
    valid = 0
    errors: list[str] = []
    transports = list(trial.glob("turn-*.transport.json"))
    for path in transports:
        try:
            payload = json.loads(path.read_text())
        except (ValueError, OSError) as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        entries = payload.get("usage", []) if isinstance(payload, dict) else []
        if not isinstance(entries, list):
            errors.append(f"{path.name}: invalid usage collection")
            continue
        if len(entries) != 1 or not isinstance(entries[0], dict):
            continue
        usage = entries[0]
        if any(type(usage.get(k)) is not int or usage[k] < 0 for k in TOKEN_KEYS):
            continue
        if usage["cached_input_tokens"] > usage["input_tokens"]:
            continue
        valid += 1
        for key in TOKEN_KEYS:
            totals[key] += usage[key]
    complete = valid == len(transports) == report["model_calls"]
    prompts = [
        json.loads(p.read_text())["prompt"]
        for p in trial.glob("turn-*.json")
        if p.name.count(".") == 1
    ]
    return dict(
        status=report["status"],
        model_calls=report["model_calls"],
        measurement_attempts=len(report["attempts"]),
        measurements=len(report["receipts"]),
        usage_complete=complete,
        usage_errors=errors,
        prompt_bytes=sum(len(p.encode()) for p in prompts),
        **{key: value if complete else None for key, value in totals.items()},
        **{f"observed_{key}": value for key, value in totals.items()},
    )


def run_comparison(base: Path, model: str, *, live: bool = False) -> dict[str, Any]:
    # Calibration owns exclusive output creation and actual worker-boundary preflight.
    calibration = run_demo(base, model, live=False)
    base = base.resolve()
    protocol: dict[str, Any] = dict(
        schema_version=1,
        schedule=frozen_schedule(),
        model=model,
        effort="medium",
        seconds_per_trial=360,
        max_measurements=4,
        max_calls=dict(legacy=5, prechecked=4, fixed=1),
        selection="All nine cells, one attempt each; no retries or selected replacement.",
        input_hashes={c["case"]: c["panel_sha256"] for c in calibration["cases"]},
        review=[
            "grounding",
            "integrity stopping",
            "unsupported causal or edge claims",
            "useful next tests",
            "missing evidence and failures",
        ],
        practical_target=(
            "Prechecked >=15% fewer total input tokens, usable finals and no critical regression."
        ),
        limits=(
            "Designed development panel; no significance, general uplift "
            "or production-suggest comparison."
        ),
    )
    write_once(base / "comparison-protocol.json", protocol)
    records = []
    if live:
        for item in protocol["schedule"]:
            case = next(c for c in calibration["cases"] if c["case"] == item["case"])
            root = base / case["directory"]
            mode = next(m for m in MODES if m == item["mode"])
            neutral = digest(mode.encode())[:12]
            worker = Worker(base / "runtime", root / "input", case["panel_sha256"])
            trial = root / neutral
            started = time.monotonic()
            write_once(root / f"{neutral}.reserved.json", dict(**item, status="reserved"))
            try:
                proposer = CodexProposer(root / f"reasoning-{neutral}", model)
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                trial.mkdir(exist_ok=False)
                report = dict(
                    status="incomplete",
                    model_calls=0,
                    attempts=[],
                    receipts=[],
                    final=None,
                    error=f"provider setup failed: {exc}",
                    controller_mode=mode,
                    synthetic=True,
                    admitted=False,
                )
                write_once(trial / "report.json", report)
            else:
                report = run_case(trial, proposer, worker, mode=mode)
            record = dict(
                **item,
                directory=str(trial.relative_to(base)),
                elapsed_seconds=time.monotonic() - started,
                resources=resource_record(trial, report),
                result=report,
            )
            write_once(root / f"{neutral}.comparison.json", record)
            records.append(record)
    summary = dict(
        protocol=protocol,
        live=live,
        records=records,
        quality="Independent review required; completed does not mean correct.",
        calibration_counted_in_trial_cost=False,
        calibration_measurements=sum(len(c["calibration"]) for c in calibration["cases"]),
    )
    write_once(base / "comparison.json", summary)
    return summary
