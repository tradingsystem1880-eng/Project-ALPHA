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
import mutation_fragment
from check_mutation_report import validate_report
from harness_quant import command_run as command_run

SCHEMA = 2


def inventory(
    root: Path, commit: str, run_id: str, mutants: dict[str, list[str]] | None = None
) -> dict[str, Any]:
    modules = gate.all_quant_source_modules(root)
    if not modules or len(modules) != len(set(modules)) or not commit or not run_id:
        raise ValueError("Empty or duplicate inventory / identity")
    baseline = gate.read_json(root / harness_quant.MUTATION_BASELINE_FILE) or {}
    floors = {
        module: harness_quant.mutation_required(module, baseline.get("kill_rates", {}))
        for module in modules
    }
    tools = {module: harness_quant.mutation_backend(root / module) for module in modules}
    jobs: list[dict[str, Any]] = [
        {"index": i, "module": module} for i, module in enumerate(modules)
    ]
    extra: dict[str, Any] = {}
    if mutants is not None:
        if set(mutants) != {module for module, tool in tools.items() if tool == "mutmut"}:
            raise ValueError("Complete functional module inventories required")
        if any(keys != sorted(keys) for keys in mutants.values()):
            raise ValueError("Canonical sorted mutant inventories required")
        jobs = []
        for module in modules:
            parts = mutation_fragment.partitions(mutants[module]) if module in mutants else [None]
            for fragment, names in enumerate(parts):
                jobs.append(
                    {"index": len(jobs), "module": module, "fragment": fragment, "mutants": names}
                )
            if module in mutants:
                tools[module] = mutation_fragment.TOOL
        if len(jobs) > 256:
            raise ValueError("Complete matrix exceeds hosted job limit")
        extra = {
            "mutants": mutants,
            "source_hashes": {
                m: hashlib.sha256((root / m).read_bytes()).hexdigest() for m in modules
            },
        }
    return {
        "floors": floors,
        "tools": tools,
        "schema_version": SCHEMA,
        "commit": commit,
        "run_id": run_id,
        "expected": modules,
        "jobs": jobs,
        **extra,
    }


def validate_inventory(root: Path, plan: dict[str, Any], commit: str, run_id: str) -> None:
    if (
        type(plan.get("schema_version")) is not int
        or plan != inventory(root, commit, run_id, plan.get("mutants"))
        or any(type(job.get("index")) is not int for job in plan["jobs"])
        or any("fragment" in job and type(job["fragment"]) is not int for job in plan["jobs"])
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
    job = plan["jobs"][index]
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
        **({"fragment": job["fragment"], "mutants": job["mutants"]} if "fragment" in job else {}),
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
            or (any(Path(arg).name == "mutation_fragment.py" for arg in cmd) and "export" in cmd)
            else (
                "mutation"
                if "mutmut" in cmd or any(Path(arg).name == "mutation_fragment.py" for arg in cmd)
                else "preflight"
            )
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
        fragment_args = (
            {"mutant_inventory": plan["mutants"][module], "mutant_names": job["mutants"]}
            if job.get("mutants") is not None
            else {}
        )
        _, report = harness_quant.mutate(
            root, [module], timeout=timeout, workers=workers, runner=execute, **fragment_args
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
    fragments: dict[str, list[dict[str, Any]]] = {}
    seen: set[int] = set()
    for path in sorted(directory.rglob("*.json")):
        if path.name == "mutation-summary.json":
            continue
        record = load_json(path)
        index = record.get("index")
        if type(index) is not int or not 0 <= index < len(plan["jobs"]):
            raise ValueError("Unexpected job index")
        module = plan["jobs"][index]["module"]
        job = plan["jobs"][index]
        expected = {
            "schema_version": SCHEMA,
            "commit": plan["commit"],
            "run_id": plan["run_id"],
            "expected": plan["expected"],
            "index": index,
            "module": module,
            "state": "complete",
            "phase": "finished",
            **(
                {"fragment": job["fragment"], "mutants": job["mutants"]}
                if "fragment" in job
                else {}
            ),
        }
        if any(record.get(k) != v for k, v in expected.items()):
            raise ValueError(f"Stale, mismatched or unfinished record: {path}")
        if "fragment" in job and type(record.get("fragment")) is not int:
            raise ValueError("Invalid fragment identity")
        if index in seen:
            raise ValueError(f"Duplicate result: {module}")
        seen.add(index)
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
        if job.get("mutants") is not None:
            results = entry.get("mutant_results")
            if (
                entry.get("mutant_inventory") != plan["mutants"][module]
                or not isinstance(results, dict)
                or set(results) != set(job["mutants"])
            ):
                raise ValueError("Fragment mutant identities mismatch")
            if any(status not in mutation_fragment.COUNTS for status in results.values()):
                raise ValueError("Unknown fragment verdict")
            if "no_tests_proof" in entry:
                mutation_fragment.validate_no_tests_proof(
                    entry["no_tests_proof"],
                    plan["source_hashes"][module],
                    plan["mutants"][module],
                    entry.get("mutation_config_sha256", ""),
                    module.partition("/src/")[2].removesuffix(".py").replace("/", "."),
                )
                if any(value != "no_tests" for value in results.values()):
                    raise ValueError("Certified no-tests fragment contains other verdicts")
            if entry["total"] != len(results) or any(
                entry.get(name, 0) != sum(v == name for v in results.values())
                for name in mutation_fragment.COUNTS
            ):
                raise ValueError("Fragment counts differ from measured verdicts")
            fragments.setdefault(module, []).append(entry)
        else:
            reports[module] = entry
    if seen != set(range(len(plan["jobs"]))):
        raise ValueError(f"Missing results: jobs {sorted(set(range(len(plan['jobs']))) - seen)}")
    for module, entries in fragments.items():
        results = {
            key: status for entry in entries for key, status in entry["mutant_results"].items()
        }
        if len(results) != sum(len(entry["mutant_results"]) for entry in entries) or set(
            results
        ) != set(plan["mutants"][module]):
            raise ValueError("Duplicated or missing complete mutant coverage")
        exclusions = entries[0].get("excluded_tests", [])
        if any(entry.get("excluded_tests", []) != exclusions for entry in entries):
            raise ValueError("Fragment test exclusion audit differs")
        merged = {
            **{
                name: sum(status == name for status in results.values())
                for name in mutation_fragment.COUNTS
            },
            "total": len(results),
            "check_was_interrupted_by_user": 0,
            "seconds": round(sum(entry["seconds"] for entry in entries), 1),
            "required": round(plan["floors"][module], 4),
            "tool": plan["tools"][module],
            "excluded_tests": exclusions,
            "mutant_results": results,
            "no_tests_proofs": [
                entry["no_tests_proof"] for entry in entries if "no_tests_proof" in entry
            ],
        }
        rate = harness_quant.mutation_kill_rate(merged)
        merged["kill_rate"] = round(rate, 4)
        merged["status"] = (
            "fail" if rate + harness_quant.MUTATION_TOLERANCE < plan["floors"][module] else "pass"
        )
        reports[module] = merged
    if set(reports) != set(plan["expected"]):
        raise ValueError(f"Missing results: {sorted(set(plan['expected']) - set(reports))}")
    reports = {module: reports[module] for module in plan["expected"]}
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
    parser.add_argument("--mutants", type=Path)
    args = parser.parse_args()
    root = gate.repo_root()
    if args.action == "plan":
        plan = inventory(
            root, args.commit, args.run_id, load_json(args.mutants) if args.mutants else None
        )
        gate.write_json_atomic(args.plan, plan)
        print(
            json.dumps([{k: v for k, v in job.items() if k != "mutants"} for job in plan["jobs"]])
        )
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
