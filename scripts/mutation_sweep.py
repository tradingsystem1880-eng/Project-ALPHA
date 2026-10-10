"""Identity-bound, checkpointed hosted mutation sweep; scores remain report-only."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import gate
import harness_quant
from check_mutation_report import validate_report
from harness_quant import command_run as command_run

SCHEMA = 1


def inventory(root: Path, commit: str, run_id: str) -> dict[str, Any]:
    modules = gate.all_quant_source_modules(root)
    if not modules or len(modules) != len(set(modules)) or not commit or not run_id:
        raise ValueError("Empty or duplicate inventory / identity")
    baseline = gate.read_json(root / harness_quant.MUTATION_BASELINE_FILE) or {}
    floors = {
        module: harness_quant.mutation_required(module, baseline.get("kill_rates", {}))
        for module in modules
    }
    return {
        "floors": floors,
        "tools": {module: harness_quant.mutation_backend(root / module) for module in modules},
        "schema_version": SCHEMA,
        "commit": commit,
        "run_id": run_id,
        "expected": modules,
        "jobs": [{"index": i, "module": module} for i, module in enumerate(modules)],
    }


def validate_inventory(root: Path, plan: dict[str, Any], commit: str, run_id: str) -> None:
    if (
        type(plan.get("schema_version")) is not int
        or plan != inventory(root, commit, run_id)
        or any(type(job.get("index")) is not int for job in plan["jobs"])
    ):
        raise ValueError("Inventory or commit/run identity mismatch")


def module_key(module: str) -> str:
    return hashlib.sha256(module.encode()).hexdigest()[:16]


def run_module(
    root: Path,
    plan: dict[str, Any],
    index: int,
    output: Path,
    *,
    timeout: float = 5400,
    budget: float = 11100,
    workers: int = 2,
    runner: gate.EnvRunner | None = None,
) -> int:
    if timeout <= 0 or budget <= 5 or workers < 1:
        raise ValueError("Positive timeout, budget and workers required")
    module = plan["jobs"][index]["module"]
    output.mkdir(parents=True, exist_ok=True)
    checkpoint = output / f"module-{index}-{module_key(module)}.json"
    # Exclusive creation prevents accidental reuse of measurements or competing writers.
    with checkpoint.open("x") as stream:
        stream.write("{}\n")
    started = time.monotonic()
    record: dict[str, Any] = {
        "schema_version": SCHEMA,
        "commit": plan["commit"],
        "run_id": plan["run_id"],
        "expected": plan["expected"],
        "index": index,
        "module": module,
        "state": "running",
        "phase": "staging",
        "timings": [],
        "report": None,
        "workers": workers,
    }

    def save() -> None:
        record["elapsed_seconds"] = round(time.monotonic() - started, 3)
        gate.write_json_atomic(checkpoint, record)

    save()

    def execute(cmd: list[str], **kwargs: Any) -> tuple[bool, float, str]:
        phase = (
            "export"
            if cmd[-1] == "export-cicd-stats"
            or any(Path(arg).name == "mutation_legacy.py" for arg in cmd)
            else ("mutation" if "mutmut" in cmd else "preflight")
        )
        record["phase"] = phase
        log = output / f"{checkpoint.stem}-{phase}.log"
        save()
        remaining = budget - (time.monotonic() - started) - 5
        if remaining <= 0:
            log.write_text("Deadline exhausted before command\n")
            result = (False, 0.0, "deadline exhausted")
        else:
            kwargs["timeout"] = min(float(kwargs["timeout"]), remaining)
            if runner is None:
                result = command_run(cmd, log=log, **kwargs)
            else:
                result = runner(cmd, **kwargs)
                log.write_text(result[2])
        record["timings"].append(
            {"phase": phase, "ok": result[0], "seconds": result[1], "log": log.name}
        )
        save()
        return result

    try:
        _, report = harness_quant.mutate(
            root, [module], timeout=timeout, workers=workers, runner=execute
        )
        record["report"] = report
        validate_report(report, module)
        record["state"] = "complete"
        record["phase"] = "finished"
        return 0  # measured floor failures are report-only in the hosted lane
    except (OSError, ValueError, TypeError, KeyError, subprocess.CalledProcessError) as exc:
        record["state"] = "error"
        record["error"] = f"{type(exc).__name__}: {exc}"
        return 1
    except BaseException as exc:
        record["state"] = "interrupted"
        record["error"] = type(exc).__name__
        raise
    finally:
        save()


def load_json(path: Path) -> dict[str, Any]:
    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    payload = json.loads(path.read_text(), object_pairs_hook=unique_pairs)
    if not isinstance(payload, dict):
        raise ValueError("JSON must be an object")
    return payload


def aggregate(plan: dict[str, Any], directory: Path) -> dict[str, Any]:
    reports: dict[str, Any] = {}
    for path in sorted(directory.rglob("*.json")):
        if path.name == "mutation-summary.json":
            continue
        record = load_json(path)
        index = record.get("index")
        if type(index) is not int or not 0 <= index < len(plan["jobs"]):
            raise ValueError("Unexpected job index")
        module = plan["jobs"][index]["module"]
        expected = {
            "schema_version": SCHEMA,
            "commit": plan["commit"],
            "run_id": plan["run_id"],
            "expected": plan["expected"],
            "index": index,
            "module": module,
            "state": "complete",
            "phase": "finished",
        }
        if any(record.get(k) != v for k, v in expected.items()):
            raise ValueError(f"Stale, mismatched or unfinished record: {path}")
        if module in reports:
            raise ValueError(f"Duplicate result: {module}")
        if type(record.get("schema_version")) is not int:
            raise ValueError("Invalid checkpoint schema")
        workers = record.get("workers")
        elapsed = record.get("elapsed_seconds")
        if type(workers) is not int or not 1 <= workers <= 2:
            raise ValueError("Invalid worker bound")
        if (
            not isinstance(elapsed, (int, float))
            or isinstance(elapsed, bool)
            or not math.isfinite(elapsed)
            or elapsed < 0
        ):
            raise ValueError("Invalid checkpoint elapsed time")
        timings = record.get("timings")
        phases = ["preflight", "mutation", "export"]
        if not isinstance(timings, list) or len(timings) != len(phases):
            raise ValueError("Missing command timings")
        for timing, phase in zip(timings, phases, strict=True):
            if not isinstance(timing, dict) or timing.get("phase") != phase:
                raise ValueError("Malformed command timing")
            seconds = timing.get("seconds")
            if (
                not isinstance(seconds, (int, float))
                or isinstance(seconds, bool)
                or not math.isfinite(seconds)
                or seconds < 0
            ):
                raise ValueError("Invalid command duration")
            if type(timing.get("ok")) is not bool or (phase != "preflight" and not timing["ok"]):
                raise ValueError("Unfinished measurement command")
            log = timing.get("log")
            if (
                not isinstance(log, str)
                or Path(log).name != log
                or not (path.parent / log).is_file()
            ):
                raise ValueError("Missing command log")
        validate_report(record.get("report"), module)
        entry = record["report"]["modules"][module]
        if entry.get("tool") != plan["tools"][module]:
            raise ValueError("Mutation backend mismatched with frozen inventory")
        floor = plan["floors"][module]
        denominator = entry["total"] - entry.get("skipped", 0)
        rate = entry["killed"] / denominator if denominator > 0 else 0.0
        status = "fail" if rate + harness_quant.MUTATION_TOLERANCE < floor else "pass"
        if entry["required"] != round(floor, 4) or entry["status"] != status:
            raise ValueError("Mutation floor or verdict mismatched with frozen baseline")
        reports[module] = entry
    if set(reports) != set(plan["expected"]):
        raise ValueError(f"Missing results: {sorted(set(plan['expected']) - set(reports))}")
    return {
        "schema_version": SCHEMA,
        "commit": plan["commit"],
        "run_id": plan["run_id"],
        "expected": plan["expected"],
        "infrastructure_complete": True,
        "min_kill": harness_quant.MUTATION_MIN_KILL,
        "modules": reports,
        "score_failures": [m for m, e in reports.items() if e["status"] == "fail"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "run", "aggregate"])
    parser.add_argument("--commit", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--plan", type=Path, default=Path("mutation-inventory.json"))
    parser.add_argument("--output", type=Path, default=Path("mutation-results"))
    parser.add_argument("--index", type=int)
    args = parser.parse_args()
    root = gate.repo_root()
    if args.action == "plan":
        plan = inventory(root, args.commit, args.run_id)
        gate.write_json_atomic(args.plan, plan)
        print(json.dumps(plan["jobs"]))
        return 0
    if args.action == "run":
        plan = load_json(args.plan)
        validate_inventory(root, plan, args.commit, args.run_id)

        def interrupted(signum: int, frame: object) -> None:
            raise KeyboardInterrupt(f"signal {signum}")

        signal.signal(signal.SIGTERM, interrupted)
        if args.index is None or not 0 <= args.index < len(plan["jobs"]):
            parser.error("valid --index required")
        return run_module(root, plan, args.index, args.output)
    args.output.mkdir(parents=True, exist_ok=True)
    summary = args.output / "mutation-summary.json"
    try:
        plan = load_json(args.plan)
        validate_inventory(root, plan, args.commit, args.run_id)
        report = aggregate(plan, args.output)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        gate.write_json_atomic(
            summary,
            {
                "infrastructure_complete": False,
                "error": str(exc),
                "commit": args.commit,
                "run_id": args.run_id,
            },
        )
        print(str(exc), file=sys.stderr)
        return 1
    gate.write_json_atomic(summary, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
