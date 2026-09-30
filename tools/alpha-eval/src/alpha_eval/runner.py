"""Benchmark orchestration: trials -> trajectories -> judged score cards."""

from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from alpha_eval.harness import SutConfig, run_trial
from alpha_eval.judge import SCHEMA, build_prompt, codex_judge
from alpha_eval.models import Scenario, Trajectory
from alpha_eval.platform import repo_root
from alpha_eval.provenance import bind_manifest, digest, revision_path, write_once
from alpha_eval.replay import replay_codex
from alpha_eval.sandbox import file_hash, head_sha, prepare_workspace, trial_tag
from alpha_eval.score import infra_limited, score_trial

DEFAULT_HOME = Path(os.environ.get("ALPHA_EVAL_HOME", Path.home() / ".alpha-bench"))


def parse_sut(spec: str, workspace: Path) -> SutConfig:
    agent, _, model = spec.partition(":")
    if agent != "codex" or not model.startswith("gpt-"):
        raise ValueError(f"New execution is Codex only: codex:gpt-<model>, got {spec!r}")
    return SutConfig(agent=agent, model=model, workspace=workspace, effort="medium")


def run_trials(
    scenarios: list[Scenario],
    suts: list[str],
    trials: int,
    base: Path,
    parallel: int,
    log: Any = print,
    resume: bool = False,
) -> list[Path]:
    """Run every (scenario, sut, trial). With ``resume``, keep existing valid trajectories and
    re-run only missing or harness-invalid ones. An account/infra limit stops the batch (the
    remaining jobs would all fail the same way); resume later."""
    if parallel < 1 or trials < 1:
        raise ValueError("parallel and trials must be positive")
    configs = [parse_sut(s, Path(".")) for s in suts]  # reject before any writes
    if base.exists() and not (base / "run-manifest.json").exists():
        raise FileExistsError("Existing or legacy run directory; choose a new run name")
    src = Path(__file__).parent
    worlds = src.parents[1] / "worlds"
    manifest = {
        "schema_version": 2,
        "platform_sha": head_sha(),
        "scenarios": [sc.model_dump(mode="json") for sc in scenarios],
        "suts": suts,
        "trials": trials,
        "effort": "medium",
        "harness": {p.name: file_hash(p) for p in sorted(src.glob("*.py"))},
        "worlds": {p.name: file_hash(p) for p in sorted(worlds.glob("*")) if p.is_file()},
        "client_version": __import__("subprocess")
        .check_output(["codex", "--version"], text=True)
        .strip(),
    }
    bind_manifest(base / "run-manifest.json", manifest, resume=resume)
    # A separate, read-only export; never reuse a historically mutable workspace.
    workspace = DEFAULT_HOME / f"workspace-v2-{head_sha()[:12]}-{digest(manifest)[:12]}"
    workspace_info = prepare_workspace(workspace)
    if not (base / "workspace-info.json").exists():
        write_once(base / "workspace-info.json", workspace_info)
    configs = [parse_sut(s, workspace) for s in suts]
    jobs = [(sc, cfg, t) for sc in scenarios for cfg in configs for t in range(1, trials + 1)]
    if resume:
        jobs = [
            j
            for j in jobs
            if not _valid_existing(_trajectory_path(base, j[0].id, j[1].label, j[2]))
        ]
        log(f"resume: {len(jobs)} trials to (re)run")
    out: list[Path] = []
    halted = threading.Event()

    def one(job: tuple[Scenario, SutConfig, int]) -> Path | None:
        sc, cfg, t = job
        if halted.is_set():
            return None
        started = time.time()
        traj = run_trial(sc, cfg, base, t, retry=resume)
        if infra_limited(traj) or traj.meta.get("stop") == "harness_invalid":
            halted.set()
            log(f"INFRA LIMIT hit on {sc.id} {cfg.label} t{t}: halting batch; resume with --resume")
        cost = traj.meta.get("cost_usd")
        cost_label = "unknown" if cost is None else f"${cost:.2f}"
        log(
            f"[{time.strftime('%H:%M:%S')}] {sc.id} {cfg.label} t{t}: stop={traj.meta.get('stop')} "
            f"events={len(traj.events)} cost={cost_label} "
            f"{time.time() - started:.0f}s owner_ok={traj.integrity.get('owner_state_unchanged')}"
        )
        return Path(str(traj.meta["trajectory_path"]))

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        futures = [pool.submit(one, j) for j in jobs]
        for fut in as_completed(futures):
            path = fut.result()
            if path is not None:
                out.append(path)
    return out


def _valid_existing(path: Path) -> bool:
    if not path.exists():
        return False
    traj = Trajectory.model_validate_json(path.read_text(encoding="utf-8"))
    return traj.meta.get("stop") in {"completed", "timeout", "tool_call_cap"} and not infra_limited(
        traj
    )


def _trajectory_path(base: Path, scenario_id: str, sut: str, trial: int) -> Path:
    root = base / "trials" / trial_tag(scenario_id, sut, trial)
    attempts = sorted((root / "attempts").glob("*/trajectory.jsonl"))
    return attempts[-1] if attempts else root / "trajectory.jsonl"


def all_trajectories(base: Path) -> list[Path]:
    """One latest completed attempt per slot; originals remain on disk for audit."""
    paths = []
    for root in sorted((base / "trials").iterdir()):
        if not root.is_dir():
            continue
        attempts = sorted((root / "attempts").glob("*/trajectory.jsonl"))
        path = attempts[-1] if attempts else root / "trajectory.jsonl"
        if path.exists():
            paths.append(path)
    return paths


def _cached(path: Path) -> dict[str, Any] | None:
    """A cached judgement, or None when absent or when the cached call had failed."""
    if not path.exists():
        return None
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data if data.get("available") else None


def score_all(
    base: Path,
    scenarios: dict[str, Scenario],
    parallel: int,
    second_judge_tiers: set[str],
    judge_model: str,
    log: Any = print,
    *,
    revision: str,
    effort: str = "medium",
    resume: bool = False,
    reuse_revision: str = "",
) -> Path:
    """Score into a new immutable revision, never into a historical trial directory."""
    parse_sut(f"codex:{judge_model}", base)
    out = revision_path(base, revision)
    paths = all_trajectories(base)
    manifest = {
        "schema_version": 2,
        "judge_model": judge_model,
        "effort": effort,
        "second_judge_tiers": sorted(second_judge_tiers),
        "inputs": {
            str(p.relative_to(base)): {
                "trajectory": file_hash(p),
                "raw": file_hash(p.parent / "raw.jsonl"),
                "setup": file_hash(p.parent / "hidden/setup.json"),
            }
            for p in paths
        },
        "scenarios": {k: s.model_dump(mode="json") for k, s in sorted(scenarios.items())},
        "schema": SCHEMA,
        "bridge_sha256": file_hash(repo_root() / "scripts/codex_bridge.py"),
        "bridge_schema_sha256": file_hash(repo_root() / "scripts/schemas/codex_judge.json"),
        "client_version": __import__("subprocess")
        .check_output(["codex", "--version"], text=True)
        .strip(),
        "scorer": {p.name: file_hash(p) for p in Path(__file__).parent.glob("*.py")},
        "provenance": "legacy inputs may lack acquisition-time fingerprints",
    }
    reusable: dict[str, Path] = {}
    if reuse_revision:
        source = revision_path(base, reuse_revision)
        previous = json.loads((source / "manifest.json").read_text())
        for field in (
            "judge_model",
            "effort",
            "schema",
            "bridge_sha256",
            "bridge_schema_sha256",
            "client_version",
        ):
            if previous.get(field) != manifest.get(field):
                raise ValueError(f"Incompatible judgment reuse: {field}")
        reusable = {p.parent.name: p for p in source.glob("judgments/*/primary.json")}
        manifest["reuse"] = {
            "revision": reuse_revision,
            "manifest_sha256": digest(previous),
            "judgments": {key: file_hash(path) for key, path in sorted(reusable.items())},
        }
    if (out / "scorecards.jsonl").exists():
        raise FileExistsError(f"Completed scoring revision already exists: {out}")
    bind_manifest(out / "manifest.json", manifest, resume=resume)
    halted = threading.Event()

    def one(path: Path) -> dict[str, Any]:
        traj = Trajectory.model_validate_json(path.read_text(encoding="utf-8"))
        traj = replay_codex(traj, path.parent / "raw.jsonl")
        normalized = out / "normalized" / (digest(str(path.relative_to(base))) + ".json")
        if not normalized.exists():
            write_once(normalized, traj.model_dump(mode="json"))
        sc = scenarios[traj.scenario_id]
        setup = path.parent / "hidden" / "setup.json"
        world = json.loads(setup.read_text()).get("world", {}) if setup.exists() else {}
        judged: dict[str, Any] | None = None
        second: dict[str, Any] | None = None
        if traj.meta.get("stop") != "harness_invalid" and traj.events and not infra_limited(traj):
            prompt = build_prompt(sc, traj, world)
            key = digest(
                {
                    "prompt": prompt,
                    "schema": SCHEMA,
                    "model": judge_model,
                    "effort": effort,
                    "trajectory": file_hash(path),
                }
            )
            work = out / "judgments" / key
            work.mkdir(parents=True, exist_ok=True)
            cache = work / "primary.json"
            judged = _cached(cache)
            if judged is None and key in reusable:
                source_cache = reusable[key]
                if file_hash(source_cache) != manifest["reuse"]["judgments"][key]:
                    raise ValueError("Reused judgment changed after manifest binding")
                judged = _cached(source_cache)
                if judged is not None:
                    write_once(cache, judged)
            if judged is None and not halted.is_set():
                judged = codex_judge(prompt, work, model=judge_model, effort=effort)
                if judged.get("available"):
                    write_once(cache, judged)
                else:
                    if judged.get("error_kind") != "evidence_limit":
                        halted.set()
                    write_once(work / f"error-{time.time_ns()}.json", judged)
            if (
                sc.tier in second_judge_tiers
                and not halted.is_set()
                and judged is not None
                and judged.get("available")
            ):
                cache2 = work / "review.json"
                second = _cached(cache2)
                if second is None:
                    review_dir = work / "review"
                    review_dir.mkdir(exist_ok=True)
                    second = codex_judge(prompt, review_dir, model=judge_model, effort=effort)
                    if second.get("available"):
                        write_once(cache2, second)
                    else:
                        halted.set()
        card = score_trial(sc, traj, judged, second)
        data = card.model_dump(mode="json")
        data["meta"].update(
            {
                "scoring_revision": revision,
                "source_sha256": file_hash(path),
                "same_model_review": bool(second),
                "seconds": traj.meta.get("seconds"),
                "usage": traj.meta.get("usage"),
                "cost_usd": traj.meta.get("cost_usd"),
                "tool_calls": traj.meta.get("tool_calls"),
            }
        )
        log(f"scored {sc.id} {traj.sut} t{traj.trial}: {card.outcome} verdict={card.verdict}")
        return data

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        cards = list(pool.map(one, paths))
    cards.sort(key=lambda c: (c["scenario_id"], c["sut"], c["trial"]))
    # A failed judge leaves resumable caches; partial cards remain explicitly partial.
    out_path = out / ("partial-scorecards.jsonl" if halted.is_set() else "scorecards.jsonl")
    if out_path.exists():
        out_path = out / f"partial-scorecards-{time.time_ns()}.jsonl"
    with out_path.open("x", encoding="utf-8") as fh:
        for c in cards:
            fh.write(json.dumps(c) + "\n")
    if not halted.is_set():
        write_once(
            out / "scoring-meta.json",
            {
                "judge_model": judge_model,
                "effort": effort,
                "revision": revision,
                "manifest_sha256": digest(manifest),
                "repo_head": head_sha(),
                "same_model_review": any(c["meta"]["same_model_review"] for c in cards),
                "complete": True,
            },
        )
    return out_path
