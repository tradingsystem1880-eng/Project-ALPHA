"""Layer B: run one scenario trial against a system under test and record its trajectory."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from alpha_eval.isolation import permission_args, preflight, sandbox_command
from alpha_eval.models import Scenario, Trajectory, Turn
from alpha_eval.platform import build_world, run_alpha, sandbox_env
from alpha_eval.sandbox import (
    TrialPaths,
    owner_state_fingerprint,
    owner_state_unchanged,
)
from alpha_eval.stream import stream_process
from alpha_eval.trajectory import Normalizer

WORLDS_DIR = Path(__file__).resolve().parents[2] / "worlds"
_VAR = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


def render(text: str, variables: dict[str, str]) -> str:
    return _VAR.sub(lambda m: variables.get(m.group(1), m.group(0)), text)


def setup_sandbox(
    scenario: Scenario, paths: TrialPaths, workspace: Path | None = None
) -> dict[str, Any]:
    """Build the world and run setup steps; returns variables + setup log (hidden from the SUT)."""
    truth_world: dict[str, Any] = {}
    if scenario.world:
        spec = json.loads((WORLDS_DIR / f"{scenario.world}.json").read_text(encoding="utf-8"))
        truth_world = build_world(
            spec, paths.sandbox, paths.truth, scenario.world_seed, workspace=workspace
        )
    # data_dir: the sandbox ALPHA_DATA_DIR, so prompts can name files a user would point at
    variables: dict[str, str] = {"data_dir": str(paths.sandbox)}
    log = []
    for step in scenario.setup:
        argv = [render(a, variables) for a in step.argv]
        res = run_alpha(paths.sandbox, argv, timeout=1800, workspace=workspace)
        entry = {
            "argv": argv,
            "rc": res.returncode,
            "stdout": res.stdout[-3000:],
            "stderr": res.stderr[-2000:],
        }
        log.append(entry)
        if step.expect_ok and res.returncode != 0:
            raise RuntimeError(f"setup step failed: {argv}\n{res.stderr[-2000:]}")
        if res.run_id:
            variables["run_id"] = res.run_id
            if step.save_run_as:
                variables[step.save_run_as] = res.run_id
        if step.save:
            payload = json.loads(res.stdout)
            for var, key in step.save.items():
                value: Any = payload
                for part in key.split("."):
                    value = value[int(part)] if isinstance(value, list) else value[part]
                variables[var] = str(value)
    (paths.root / "hidden" / "setup.json").write_text(
        json.dumps(
            {
                "canary": scenario.truth.canary,
                "variables": variables,
                "log": log,
                "world": truth_world,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"variables": variables, "world": truth_world}


def _mentioned(events: list[Any], patterns: list[str]) -> bool:
    text = "\n".join(e.text for e in events if e.kind in {"assistant_text", "final"}).lower()
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def should_send(turn: Turn, norm: Normalizer) -> bool:
    if turn.when == "always":
        return True
    hit = _mentioned(norm.events, turn.patterns)
    return hit if turn.when == "if_mentioned" else not hit


@dataclass
class SutConfig:
    agent: str  # "claude" | "codex"
    model: str
    workspace: Path
    effort: str | None = "medium"
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return f"{self.agent}:{self.model}"


def run_claude(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Historical adapters cannot initiate new Claude execution."""
    raise ValueError("New execution is Codex only")


def _codex_argv(cfg: SutConfig, paths: TrialPaths, session: str | None, prompt: str) -> list[str]:
    if cfg.agent != "codex":
        raise ValueError("New execution is Codex only")
    ws_bin = cfg.workspace / ".venv" / "bin"
    mcp = sandbox_command(cfg.workspace, paths.sandbox, [str(ws_bin / "alpha-mcp")])
    base = ["codex", "exec"]
    if session:
        base += ["resume", session]
    settings = {
        "approval_policy": "never",
        "web_search": "disabled",
        "model_reasoning_effort": cfg.effort or "medium",
        "shell_environment_policy.inherit": "none",
        "mcp_servers.alpha.command": mcp[0],
        "mcp_servers.alpha.args": mcp[1:],
        "mcp_servers.alpha.default_tools_approval_mode": "approve",
        "mcp_servers.alpha.required": True,
        "developer_instructions": (
            "You are working in an offline research workspace. Use the alpha MCP tools or "
            f"the public CLI at {ws_bin / 'alpha'}. Existing data and project state are in "
            f"ALPHA_DATA_DIR={paths.sandbox}; ALPHA_BULK_DATA_DIR={paths.sandbox / 'bulk'}. "
            "The platform export is read-only. Persist research using the public CLI/MCP. "
            "Network access is disabled. Do not infer unavailable data or results."
        ),
    }
    base += [
        "--json",
        "--skip-git-repo-check",
        "--ignore-user-config",
        "-m",
        cfg.model,
        *permission_args(cfg.workspace, paths.sandbox),
    ]
    base += ["--enable", "skip_host_skill_discovery"]
    for feature in (
        "plugins",
        "apps",
        "memories",
        "browser_use",
        "computer_use",
        "hooks",
        "image_generation",
        "multi_agent",
    ):
        base += ["--disable", feature]
    for key, value in settings.items():
        base += ["-c", f"{key}={json.dumps(value)}"]
    env = (
        f'{{ALPHA_DATA_DIR="{paths.sandbox}",'
        f'ALPHA_BULK_DATA_DIR="{paths.sandbox / "bulk"}",PATH="{ws_bin}:/usr/bin:/bin"}}'
    )
    base += ["-c", "mcp_servers.alpha.env=" + env, "-c", "shell_environment_policy.set=" + env]
    if not session:
        base += ["-C", str(cfg.workspace)]
    return [*base, prompt]


def run_codex(
    scenario: Scenario,
    cfg: SutConfig,
    paths: TrialPaths,
    variables: dict[str, str],
    norm: Normalizer,
    raw: Any,
) -> dict[str, Any]:
    deadline = time.monotonic() + scenario.timeout_s
    meta: dict[str, Any] = {"sessions": [], "stop": "completed", "usage": []}
    session: str | None = None
    for turn in scenario.turns:
        if not should_send(turn, norm):
            continue
        if turn.new_session and session is not None:
            session = None
            norm.system("--- new SUT session (no conversational memory) ---")
        text = render(turn.text, variables)
        norm.user(text)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            meta["stop"] = "timeout"
            break

        turn_completed = False
        turn_failed = False

        def consume(line: str) -> bool:
            nonlocal session
            nonlocal turn_completed, turn_failed
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                norm.system("Malformed raw event: " + line[:2000])
                turn_failed = True
                return True
            if ev.get("type") == "thread.started":
                session = ev.get("thread_id") or session
                meta["sessions"].append(session)
            if ev.get("type") == "turn.completed":
                turn_completed = True
                meta["usage"].append(ev.get("usage"))
            if ev.get("type") in {"error", "turn.failed"}:
                turn_failed = True
            norm.codex(ev)
            return sum(e.kind == "tool_call" for e in norm.events) < scenario.max_tool_calls

        result = stream_process(
            _codex_argv(cfg, paths, session, text),
            cfg.workspace,
            sandbox_env(paths.sandbox, cfg.workspace),
            remaining,
            raw,
            consume,
        )
        meta.update(result)
        if (
            turn_failed
            or str(result["stop"]).startswith("exit:")
            or (result["stop"] == "completed" and not turn_completed)
        ):
            meta["stop"] = "harness_invalid"
            meta["error"] = "Codex turn failed or ended without turn.completed"
            break
        if result["stop"] != "completed":
            break
    meta["tool_calls"] = sum(1 for e in norm.events if e.kind == "tool_call")
    return meta


def run_trial(
    scenario: Scenario, cfg: SutConfig, base: Path, trial: int, *, retry: bool = False
) -> Trajectory:
    if cfg.agent != "codex":
        raise ValueError("New execution is Codex only")
    paths = TrialPaths.create(base, scenario.id, cfg.label, trial, retry=retry)
    before = owner_state_fingerprint()
    started = time.time()
    norm = Normalizer()
    integrity: dict[str, Any] = {"owner_state_before": before}
    try:
        integrity["isolation"] = preflight(cfg.workspace, paths.sandbox)
        setup = setup_sandbox(scenario, paths, cfg.workspace)
    except Exception as exc:
        meta = {"stop": "harness_invalid", "error": f"{type(exc).__name__}: {exc}"[:3000]}
        return _finish(scenario, cfg, trial, paths, norm, meta, integrity, started)
    try:
        with paths.raw.open("x", encoding="utf-8") as raw:
            meta = run_codex(scenario, cfg, paths, setup["variables"], norm, raw)
    except (OSError, ValueError, RuntimeError) as exc:
        meta = {"stop": "harness_invalid", "error": f"{type(exc).__name__}: {exc}"[:3000]}
    except KeyboardInterrupt:
        meta = {"stop": "cancelled"}
    meta["variables"] = setup["variables"]
    return _finish(scenario, cfg, trial, paths, norm, meta, integrity, started)


def _finish(
    scenario: Scenario,
    cfg: SutConfig,
    trial: int,
    paths: TrialPaths,
    norm: Normalizer,
    meta: dict[str, Any],
    integrity: dict[str, Any],
    started: float,
) -> Trajectory:
    after = owner_state_fingerprint()
    integrity["owner_state_after"] = after
    integrity["owner_state_unchanged"] = owner_state_unchanged(integrity)
    raw_text = paths.raw.read_text(encoding="utf-8") if paths.raw.exists() else ""
    canary = scenario.truth.canary
    integrity["canary_leaked"] = bool(canary) and canary in raw_text
    meta["seconds"] = round(time.time() - started, 1)
    meta["trajectory_path"] = str(paths.trajectory)
    meta["model"] = cfg.model
    meta["effort"] = cfg.effort
    traj = Trajectory(
        scenario_id=scenario.id,
        trial=trial,
        sut=cfg.label,
        events=norm.events,
        meta=json.loads(json.dumps(meta, default=str)),
        integrity=integrity,
    )
    paths.trajectory.write_text(traj.model_dump_json(indent=1), encoding="utf-8")
    return traj
