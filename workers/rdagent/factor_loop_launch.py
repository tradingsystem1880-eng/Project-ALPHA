"""Launch one ALPHA-judged RD-Agent factor loop (ADR-0049): verify, freeze, gateway, loop, receipt.

Standard library only; run it with the repository's ``.venv/bin/python``. It verifies the pinned
RD-Agent source and the factor runtime profile, freezes ALPHA's panel, prepares RD-Agent's data
folders, starts the model gateway with its call cap, runs the loop in its own process group under
a wall-clock limit, always stops both, and writes a receipt. It is not the command line's native
job supervisor (no ControlStore job or reservation yet; see the backlog note
``docs/roadmap/backlog/rdagent-factor-loop-supervision.md``). Nothing it produces is evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

WORKER = Path(__file__).resolve().parent
REPO = WORKER.parents[1]
MAX_CALLS = 60
LABEL = "exploratory, not admitted, not yet confirmed"
AUTHORITY = dict.fromkeys(("admitted", "evidence", "approval", "promotion"), False)
SETUP_HINT = "bash scripts/setup_rdagent.sh --with-factor-runtime"


class LaunchError(Exception):
    """A refusal or failed step, with a plain message."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _inside_git(path: Path) -> bool:
    probe = path
    while not probe.exists():
        probe = probe.parent
    result = subprocess.run(
        ["git", "-C", str(probe), "rev-parse", "--is-inside-work-tree"],
        env={"PATH": "/usr/bin:/bin", "LANG": "C"},
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def validate(args: argparse.Namespace, environ: dict[str, str]) -> dict[str, Path]:
    if not 1 <= args.loop_n <= 3:
        raise LaunchError("--loop-n must be 1, 2 or 3")
    if not 1 <= args.run_max_calls <= MAX_CALLS:
        raise LaunchError(f"--run-max-calls must be between 1 and {MAX_CALLS}")
    if args.wall_seconds <= 0:
        raise LaunchError("--wall-seconds must be positive")
    for name in ("data_dir", "run_dir", "gateway_data_dir", "trial_ledger"):
        if not getattr(args, name).is_absolute():
            raise LaunchError(f"--{name.replace('_', '-')} must be an absolute path")
    if args.run_dir.exists():
        raise LaunchError(f"run directory already exists: {args.run_dir}")
    if not args.trial_ledger.parent.is_dir():
        raise LaunchError("the trial ledger's parent directory must exist")
    for name in ("run_dir", "gateway_data_dir", "trial_ledger"):
        if _inside_git(getattr(args, name)):
            raise LaunchError(f"--{name.replace('_', '-')} must be outside every git work tree")
    paths = {}
    for key in ("ALPHA_RDAGENT_SOURCE", "ALPHA_FACTOR_PYTHON"):
        value = environ.get(key, "")
        if not value or not Path(value).exists():
            raise LaunchError(f"{key} is not set or missing; run: {SETUP_HINT}")
        paths[key] = Path(value)
    return paths


def loop_environment(
    *, base_url: str, token: str, run: Path, factor_python: Path, ledger: Path, home: str
) -> dict[str, str]:
    """The loop's whole environment: exactly these keys and nothing inherited."""
    return {
        "HOME": home,
        "USER": os.environ.get("USER", "alpha"),
        "LANG": "C.UTF-8",
        "TERM": "dumb",
        "PATH": f"{factor_python.parent}:/usr/bin:/bin",
        "CHAT_MODEL": "lm_studio/alpha-chat",
        "EMBEDDING_MODEL": "lm_studio/alpha-embed",
        "LM_STUDIO_API_BASE": f"{base_url}/v1",
        "LM_STUDIO_API_KEY": token,
        "LITELLM_LOCAL_MODEL_COST_MAP": "True",
        "MAX_RETRY": "2",
        "CONDA_DEFAULT_ENV": "alpha-no-conda",
        "FACTOR_CoSTEER_python_bin": str(factor_python),
        "FACTOR_CoSTEER_max_loop": "1",
        "FACTOR_CoSTEER_data_folder": str(run / "factor_data" / "full"),
        "FACTOR_CoSTEER_data_folder_debug": str(run / "factor_data" / "debug"),
        "QLIB_FACTOR_SCEN": "alpha_factor_judge.AlphaFactorScenario",
        "QLIB_FACTOR_RUNNER": "alpha_factor_judge.AlphaFactorRunner",
        "QLIB_FACTOR_SUMMARIZER": "alpha_factor_judge.AlphaFactorFeedback",
        "QLIB_FACTOR_HYPOTHESIS_GEN": "alpha_factor_judge.AlphaFactorHypothesisGen",
        "QLIB_FACTOR_TRAIN_START": "2017-08-17",
        "QLIB_FACTOR_TRAIN_END": "2020-12-31",
        "QLIB_FACTOR_VALID_START": "2021-01-01",
        "QLIB_FACTOR_VALID_END": "2023-12-24",
        "QLIB_FACTOR_TEST_START": "2023-12-25",
        "QLIB_FACTOR_TEST_END": "2023-12-31",
        "LOG_TRACE_PATH": str(run / "work" / "log"),
        "ALPHA_FACTOR_RUN_DIR": str(run),
        "ALPHA_FACTOR_EVAL_PYTHON": str(REPO / ".venv" / "bin" / "python"),
        "ALPHA_FACTOR_TRIAL_LEDGER": str(ledger),
    }


class Launch:
    def __init__(self, args: argparse.Namespace, paths: dict[str, Path]) -> None:
        self.args = args
        self.run = args.run_dir
        self.source = paths["ALPHA_RDAGENT_SOURCE"]
        self.factor_python = paths["ALPHA_FACTOR_PYTHON"]
        self.bundle = self.factor_python.parents[2]
        self.repo_python = REPO / ".venv" / "bin" / "python"
        self.children: list[subprocess.Popen[bytes]] = []
        self.receipt: dict[str, Any] = {
            "schema": "AlphaRdagentFactorRunReceiptV1",
            "label": LABEL,
            "authority": AUTHORITY,
            "run_id": args.run_id,
            "loop_n": args.loop_n,
            "run_max_calls": args.run_max_calls,
            "started_at": _now(),
        }

    def log(self, step: str, **fields: Any) -> None:
        line = json.dumps({"ts": _now(), "step": step, **fields}, sort_keys=True)
        with (self.run / "launch.jsonl").open("a") as stream:
            stream.write(line + "\n")

    def check(self, step: str, command: Sequence[str], **kwargs: Any) -> str:
        result = subprocess.run(
            list(command), capture_output=True, text=True, check=False, **kwargs
        )
        if result.returncode:
            tail = (result.stderr or result.stdout).strip().splitlines()[-1:] or ["no output"]
            self.log(step, status="failed", exit=result.returncode, detail=tail[0][:300])
            raise LaunchError(f"{step} failed: {tail[0][:300]}")
        self.log(step, status="ok")
        return result.stdout.strip()

    def verify(self) -> None:
        self.receipt["factor_runtime_identity"] = self.check(
            "verify-runtime",
            [
                sys.executable,
                "-B",
                str(WORKER / "install_stock_profile.py"),
                "--profile",
                "factor",
                "--verify",
                str(self.bundle),
            ],
        )
        self.receipt["source_sha256"] = self.check(
            "verify-source",
            [
                sys.executable,
                "-B",
                "-c",
                "import sys; sys.path.insert(0, sys.argv[1]); from source_pin import verify_source;"
                " print(verify_source(__import__('pathlib').Path(sys.argv[2])))",
                str(WORKER),
                str(self.source),
            ],
        )

    def prepare(self) -> None:
        panel = self.run / "panel"
        self.check(
            "freeze",
            [
                str(self.repo_python),
                "-I",
                "-m",
                "alpha_cli.rdagent_factor_eval",
                "freeze",
                "--data-dir",
                str(self.args.data_dir),
                "--out",
                str(panel),
            ],
        )
        receipt = (panel / "panel-receipt.json").read_bytes()
        self.receipt["panel_sha256"] = json.loads(receipt)["panel_sha256"]
        self.receipt["panel_receipt_sha256"] = hashlib.sha256(receipt).hexdigest()
        self.check(
            "prepare",
            [
                str(self.factor_python),
                "-I",
                "-B",
                str(WORKER / "alpha_factor_data.py"),
                "prepare",
                "--panel",
                str(panel / "panel.parquet"),
                "--out",
                str(self.run / "factor_data"),
            ],
        )

    def spawn(self, command: Sequence[str], log: str, **kwargs: Any) -> subprocess.Popen[bytes]:
        with (
            (self.run / "logs" / f"{log}.stdout.log").open("ab") as out,
            (self.run / "logs" / f"{log}.stderr.log").open("ab") as err,
        ):
            child = subprocess.Popen(
                list(command), stdout=out, stderr=err, start_new_session=True, **kwargs
            )
        self.children.append(child)
        return child

    def gateway(self) -> tuple[str, str]:
        self.args.gateway_data_dir.mkdir(parents=True, exist_ok=True)
        state = self.args.gateway_data_dir / "model-gateway"
        command = [
            str(self.repo_python),
            "-B",
            str(WORKER / "model_gateway.py"),
            "serve",
            "--data-dir",
            str(self.args.gateway_data_dir),
            "--run-id",
            self.args.run_id,
            "--run-max-calls",
            str(self.args.run_max_calls),
            "--chat-route",
            self.args.chat_route,
            "--embedding-route",
            self.args.embedding_route,
        ]
        if self.args.accept_unhonoured:
            command += ["--accept-unhonoured", self.args.accept_unhonoured]
        child = self.spawn(command, "gateway")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise LaunchError(f"model gateway exited with {child.returncode}; see logs")
            try:
                session = json.loads((state / "session.json").read_text())
            except (OSError, ValueError):
                session = {}
            if session.get("pid") == child.pid:
                self.log("gateway", status="ok", base_url=session["base_url"])
                return str(session["base_url"]), str(session["token"])
            time.sleep(0.2)
        raise LaunchError("model gateway did not write its session within 30 s")

    def loop(self, base_url: str, token: str) -> int:
        work = self.run / "work"
        work.mkdir()
        environment = loop_environment(
            base_url=base_url,
            token=token,
            run=self.run,
            factor_python=self.factor_python,
            ledger=self.args.trial_ledger,
            home=str(self.run / "home"),
        )
        (self.run / "home").mkdir()
        self.log("loop", status="started", keys=sorted(environment))
        child = self.spawn(
            [
                str(self.factor_python),
                "-I",
                "-B",
                str(WORKER / "factor_loop_entry.py"),
                str(self.source),
                str(self.args.loop_n),
            ],
            "loop",
            cwd=work,
            env=environment,
        )
        try:
            return child.wait(timeout=self.args.wall_seconds)
        except subprocess.TimeoutExpired:
            self.log("loop", status="timeout", wall_seconds=self.args.wall_seconds)
            self.receipt["loop_reason"] = "wall-clock limit"
            return -1

    def stop(self) -> None:
        for child in reversed(self.children):
            if child.poll() is not None:
                continue
            for sig, wait in ((signal.SIGTERM, 10.0), (signal.SIGKILL, 5.0)):
                try:
                    os.killpg(child.pid, sig)
                except ProcessLookupError:
                    break
                try:
                    child.wait(timeout=wait)
                    break
                except subprocess.TimeoutExpired:
                    continue
        self.children.clear()

    def gateway_status(self) -> Any:
        result = subprocess.run(
            [
                str(self.repo_python),
                "-B",
                str(WORKER / "model_gateway.py"),
                "status",
                "--data-dir",
                str(self.args.gateway_data_dir),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            return json.loads(result.stdout)
        except ValueError:
            return {"error": (result.stderr or "no output").strip()[:300]}

    def finish(self, exit_status: int, reason: str) -> int:
        evaluations = self.run / "evaluations.jsonl"
        self.receipt.update(
            ended_at=_now(),
            exit_status=exit_status,
            loop_reason=self.receipt.get("loop_reason", reason),
            gateway_status=self.gateway_status(),
            evaluations_sha256=hashlib.sha256(evaluations.read_bytes()).hexdigest()
            if evaluations.exists()
            else None,
        )
        (self.run / "receipt.json").write_text(json.dumps(self.receipt, indent=2, sort_keys=True))
        return exit_status


def run(args: argparse.Namespace, environ: dict[str, str]) -> int:
    paths = validate(args, environ)
    args.run_dir.mkdir()
    (args.run_dir / "logs").mkdir()
    launch = Launch(args, paths)

    def interrupted(signum: int, frame: Any) -> None:
        raise KeyboardInterrupt

    previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
    status, reason = 1, "not started"
    try:
        launch.verify()
        launch.prepare()
        base_url, token = launch.gateway()
        code = launch.loop(base_url, token)
        status, reason = (0, "completed") if code == 0 else (1, f"loop exit {code}")
    except LaunchError as error:
        reason = str(error)
    except KeyboardInterrupt:
        launch.log("cancel", status="cancelled")
        reason = "cancelled"
    finally:
        launch.stop()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return launch.finish(status, reason)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run")
    r.add_argument("--data-dir", type=Path, required=True)
    r.add_argument("--run-dir", type=Path, required=True)
    r.add_argument("--gateway-data-dir", type=Path, required=True)
    r.add_argument("--trial-ledger", type=Path, required=True)
    r.add_argument("--run-id", required=True)
    r.add_argument("--loop-n", type=int, default=2)
    r.add_argument("--run-max-calls", type=int, default=MAX_CALLS)
    r.add_argument("--wall-seconds", type=float, default=5400)
    r.add_argument("--chat-route", choices=("codex", "fake"), default="codex")
    r.add_argument("--embedding-route", choices=("ollama", "fake"), default="ollama")
    r.add_argument("--accept-unhonoured", default="temperature")
    return p


def main(argv: Sequence[str] | None = None, *, runner: Callable[..., int] = run) -> int:
    args = parser().parse_args(argv)
    try:
        return runner(args, dict(os.environ))
    except LaunchError as error:
        print(f"factor-loop-launch: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
