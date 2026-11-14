"""Offline contracts of the ALPHA-judged factor-loop launcher (ADR-0049)."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import pytest

WORKER = Path(__file__).resolve().parents[2] / "workers/rdagent"
spec = importlib.util.spec_from_file_location(
    "factor_loop_launch", WORKER / "factor_loop_launch.py"
)
assert spec is not None and spec.loader is not None
launch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launch)


def args(tmp_path: Path, *extra: str) -> argparse.Namespace:
    (tmp_path / "ledger").mkdir(exist_ok=True)
    parsed: argparse.Namespace = launch.parser().parse_args(
        [
            "run",
            "--data-dir",
            str(tmp_path / "data"),
            "--run-dir",
            str(tmp_path / "run"),
            "--gateway-data-dir",
            str(tmp_path / "gateway"),
            "--trial-ledger",
            str(tmp_path / "ledger" / "trials.jsonl"),
            "--run-id",
            "test-run",
            *extra,
        ]
    )
    return parsed


def environ(tmp_path: Path) -> dict[str, str]:
    python = tmp_path / "bundle/venv/bin/python"
    python.parent.mkdir(parents=True, exist_ok=True)
    python.touch()
    (tmp_path / "source").mkdir(exist_ok=True)
    return {"ALPHA_RDAGENT_SOURCE": str(tmp_path / "source"), "ALPHA_FACTOR_PYTHON": str(python)}


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (["--run-max-calls", "61"], "between 1 and 60"),
        (["--loop-n", "4"], "--loop-n"),
        (["--wall-seconds", "0"], "positive"),
    ],
)
def test_refuses_bad_arguments(tmp_path: Path, extra: list[str], message: str) -> None:
    with pytest.raises(launch.LaunchError, match=message):
        launch.validate(args(tmp_path, *extra), environ(tmp_path))


def test_refuses_existing_run_dir_git_tree_and_missing_runtime(tmp_path: Path) -> None:
    (tmp_path / "run").mkdir()
    with pytest.raises(launch.LaunchError, match="already exists"):
        launch.validate(args(tmp_path), environ(tmp_path))
    (tmp_path / "run").rmdir()
    with pytest.raises(launch.LaunchError, match="setup_rdagent.sh --with-factor-runtime"):
        launch.validate(args(tmp_path), {})
    inside = args(tmp_path)
    inside.run_dir = Path(__file__).resolve().parent / "never-created-run"
    with pytest.raises(launch.LaunchError, match="outside every git work tree"):
        launch.validate(inside, environ(tmp_path))


def test_main_reports_refusal_plainly(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    argv = ["run", "--data-dir", "/d", "--run-dir", "/r", "--gateway-data-dir", "/g"]
    argv += ["--trial-ledger", "/nonexistent-parent/x.jsonl", "--run-id", "r"]

    def refuse(parsed: argparse.Namespace, env: dict[str, str]) -> int:
        raise launch.LaunchError("refused for test")

    assert launch.main(argv, runner=refuse) == 2
    assert "refused for test" in capsys.readouterr().err


def test_loop_environment_is_exact_and_names_alpha_classes(tmp_path: Path) -> None:
    env = launch.loop_environment(
        base_url="http://127.0.0.1:1",
        token="secret-token",
        run=tmp_path,
        factor_python=tmp_path / "py/bin/python",
        ledger=tmp_path / "trials.jsonl",
        home=str(tmp_path),
    )
    assert env["QLIB_FACTOR_RUNNER"] == "alpha_factor_judge.AlphaFactorRunner"
    assert env["QLIB_FACTOR_SUMMARIZER"] == "alpha_factor_judge.AlphaFactorFeedback"
    assert env["QLIB_FACTOR_SCEN"] == "alpha_factor_judge.AlphaFactorScenario"
    assert env["QLIB_FACTOR_HYPOTHESIS_GEN"] == "alpha_factor_judge.AlphaFactorHypothesisGen"
    assert env["FACTOR_CoSTEER_max_loop"] == "1"
    assert env["CONDA_DEFAULT_ENV"] == "alpha-no-conda"
    assert not any(k.startswith(("OPENAI", "ALPHA_GATEWAY", "MODEL_CoSTEER")) for k in env)
    assert len(env) == 31
    assert env["FACTOR_CoSTEER_python_bin"].startswith(
        "env -u LM_STUDIO_API_KEY -u LM_STUDIO_API_BASE "
    )
    assert env["ALPHA_FACTOR_CODE_PYTHON"] == str(tmp_path / "py/bin/python")


def test_stop_kills_the_whole_process_group(tmp_path: Path) -> None:
    run = tmp_path / "run"
    (run / "logs").mkdir(parents=True)
    job = launch.Launch(
        args(tmp_path),
        {"ALPHA_RDAGENT_SOURCE": tmp_path, "ALPHA_FACTOR_PYTHON": tmp_path / "a/b/c/python"},
    )
    job.run = run
    child = job.spawn(
        [
            sys.executable,
            "-c",
            "import subprocess,time; subprocess.Popen(['sleep','300']); time.sleep(300)",
        ],
        "stand-in",
    )
    time.sleep(0.5)
    group = child.pid
    job.stop()
    assert child.poll() is not None
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.killpg(group, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        raise AssertionError("a process of the stopped group is still alive")


def test_gateway_starts_with_fake_routes_and_token_stays_out_of_logs(tmp_path: Path) -> None:
    run = tmp_path / "run"
    (run / "logs").mkdir(parents=True)
    parsed = args(
        tmp_path, "--chat-route", "fake", "--embedding-route", "fake", "--run-max-calls", "3"
    )
    job = launch.Launch(
        parsed, {"ALPHA_RDAGENT_SOURCE": tmp_path, "ALPHA_FACTOR_PYTHON": tmp_path / "a/b/c/python"}
    )
    job.run = run
    job.repo_python = Path(sys.executable)
    try:
        base_url, token = job.gateway()
        assert base_url.startswith("http://127.0.0.1:")
    finally:
        job.stop()
    status = job.gateway_status()
    assert "error" not in status
    logged = (run / "launch.jsonl").read_text() + "".join(
        p.read_text() for p in (run / "logs").iterdir()
    )
    assert token not in logged
    receipt_exit = job.finish(0, "test")
    assert receipt_exit == 0
    receipt = json.loads((run / "receipt.json").read_text())
    assert token not in json.dumps(receipt)
    assert receipt["label"] == launch.LABEL
    assert not any(receipt["authority"].values())


def test_api_route_needs_model_prices_and_keys(tmp_path: Path) -> None:
    with pytest.raises(launch.LaunchError, match="--api-model"):
        launch.validate(args(tmp_path, "--chat-route", "api"), environ(tmp_path))
    priced = args(
        tmp_path,
        "--chat-route",
        "api",
        "--api-model",
        "deepseek/x",
        "--api-price-in-per-mtok",
        "0.1",
        "--api-price-out-per-mtok",
        "0.5",
    )
    with pytest.raises(launch.LaunchError, match="ALPHA_GATEWAY_API_KEY"):
        launch.validate(priced, environ(tmp_path))
    keyed = {
        **environ(tmp_path),
        "ALPHA_GATEWAY_API_BASE": "https://x",
        "ALPHA_GATEWAY_API_KEY": "k",
    }
    assert launch.validate(priced, keyed)


def test_only_the_gateway_inherits_the_paid_route_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_GATEWAY_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("ALPHA_GATEWAY_API_BASE", "https://example.com/v1")
    assert "ALPHA_GATEWAY_API_KEY" not in launch._without_secrets()
    run = tmp_path / "run"
    (run / "logs").mkdir(parents=True)
    job = launch.Launch(
        args(tmp_path),
        {"ALPHA_RDAGENT_SOURCE": tmp_path, "ALPHA_FACTOR_PYTHON": tmp_path / "a/b/c/python"},
    )
    job.run = run
    probe = [sys.executable, "-c", "import os; print('ALPHA_GATEWAY_API_KEY' in os.environ)"]
    assert job.check("probe", probe) == "False"
    child = job.spawn(probe, "probe")
    child.wait(timeout=10)
    assert (run / "logs/probe.stdout.log").read_text().strip() == "False"


@pytest.mark.parametrize(("route", "waived"), [("codex", True), ("api", False), ("fake", False)])
def test_codex_route_alone_waives_temperature_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, route: str, waived: bool
) -> None:
    extra = ["--chat-route", route]
    if route == "api":
        extra += [
            "--api-model",
            "m",
            "--api-price-in-per-mtok",
            "1",
            "--api-price-out-per-mtok",
            "1",
        ]
    run = tmp_path / "run"
    (run / "logs").mkdir(parents=True)
    job = launch.Launch(
        args(tmp_path, *extra),
        {"ALPHA_RDAGENT_SOURCE": tmp_path, "ALPHA_FACTOR_PYTHON": tmp_path / "a/b/c/python"},
    )
    job.run = run
    commands: list[list[str]] = []

    def capture(command: list[str], log: str, **kwargs: object) -> object:
        commands.append(list(command))
        raise launch.LaunchError("stop after building the command")

    monkeypatch.setattr(job, "spawn", capture)
    with pytest.raises(launch.LaunchError):
        job.gateway()
    gateway_command = commands[0]
    assert ("--accept-unhonoured" in gateway_command) is waived
    if waived:
        assert gateway_command[gateway_command.index("--accept-unhonoured") + 1] == "temperature"
    assert ("--api-model" in gateway_command) is (route == "api")


def test_step_wrapper_records_success_failure_and_unset_run_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio

    sys.path.insert(0, str(WORKER))
    try:
        entry = importlib.import_module("factor_loop_entry")
    finally:
        sys.path.remove(str(WORKER))

    class FakeLoop:
        step_idx = {7: 0}
        steps = ["coding"]

        async def _run_step(self, li: int, force_subproc: bool = False) -> str:
            assert li == 7
            if force_subproc:
                raise ValueError("step failed")
            self.step_idx[li] = 1
            return "done"

    original = FakeLoop._run_step
    monkeypatch.delenv("ALPHA_FACTOR_RUN_DIR", raising=False)
    entry.record_steps(FakeLoop)
    assert FakeLoop._run_step is original
    monkeypatch.setenv("ALPHA_FACTOR_RUN_DIR", str(tmp_path))
    entry.record_steps(FakeLoop)
    loop = FakeLoop()
    assert asyncio.run(loop._run_step(7)) == "done"
    loop.step_idx[7] = 0
    with pytest.raises(ValueError, match="step failed"):
        asyncio.run(loop._run_step(7, force_subproc=True))
    rows = [json.loads(line) for line in (tmp_path / "steps.jsonl").read_text().splitlines()]
    assert [r["event"] for r in rows] == ["start", "end", "start", "end"]
    assert all(
        r["schema"] == "AlphaRdagentStepV1"
        and r["loop"] == 7
        and r["step_index"] == 0
        and r["step"] == "coding"
        for r in rows
    )
    assert rows[1]["status"] == "ok" and rows[1]["error_type"] is None
    assert rows[3]["status"] == "error" and rows[3]["error_type"] == "ValueError"
    from datetime import datetime

    for row in rows:
        offset = datetime.fromisoformat(row["ts"]).utcoffset()
        assert offset is not None
        assert offset.total_seconds() == 0


def test_label_calls_inside_outside_overlap_and_boundaries() -> None:
    def step(event: str, loop: int, name: str, stamp: str) -> dict[str, object]:
        return {
            "event": event,
            "loop": loop,
            "step_index": loop,
            "step": name,
            "ts": f"2026-11-15T00:{stamp}+00:00",
        }

    steps = [
        step("start", 0, "propose", "00:00"),
        step("start", 1, "coding", "01:00"),
        step("end", 1, "coding", "02:00"),
        step("end", 0, "propose", "03:00"),
    ]
    calls = [
        {"id": i, "ts": f"2026-11-15T00:{stamp}+00:00"}
        for i, stamp in enumerate(["00:00", "01:30", "02:00", "02:30", "04:00"])
    ]
    original = json.dumps(calls)
    rows = launch.label_calls(calls, steps)
    assert [(r["loop"], r["step"]) for r in rows] == [
        (0, "propose"),
        (1, "coding"),
        (1, "coding"),
        (0, "propose"),
        (None, "outside-step"),
    ]
    assert all(r["schema"] == "AlphaRdagentCallLabelV1" for r in rows)
    assert json.dumps(calls) == original
    assert [r["id"] for r in rows] == list(range(5))


def test_finish_labels_only_this_run_and_handles_missing_or_bad_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = launch.Launch(
        args(tmp_path),
        {"ALPHA_RDAGENT_SOURCE": tmp_path, "ALPHA_FACTOR_PYTHON": tmp_path / "a/b/c/python"},
    )
    job.run.mkdir()
    monkeypatch.setattr(job, "gateway_status", lambda: {})
    assert job.finish(0, "test") == 0
    assert (job.run / "calls-labelled.jsonl").read_bytes() == b""
    assert job.receipt["calls_labelled"]["calls"] == 0
    assert "missing" in job.receipt["calls_labelled"]["reason"]
    state = job.args.gateway_data_dir / "model-gateway"
    state.mkdir(parents=True)
    calls = [
        {"run_id": rid, "ts": "2026-11-15T00:00:00+00:00", "payload": "unchanged"}
        for rid in ["test-run", "other"]
    ]
    (state / "calls.jsonl").write_text("".join(json.dumps(r) + "\n" for r in calls))
    (job.run / "steps.jsonl").write_text("")
    job.finish(0, "test")
    rows = [
        json.loads(line) for line in (job.run / "calls-labelled.jsonl").read_text().splitlines()
    ]
    assert len(rows) == 1 and rows[0]["run_id"] == "test-run"
    assert rows[0]["payload"] == "unchanged" and rows[0]["step"] == "outside-step"
    (job.run / "steps.jsonl").write_text("invalid json\n")
    assert job.finish(0, "test") == 0
    assert job.receipt["calls_labelled"]["calls"] == 0
    assert "error" in job.receipt["calls_labelled"]["reason"].lower()


@pytest.mark.parametrize("method", ["verify", "prepare", "gateway", "loop"])
def test_launcher_logs_start_before_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    job = launch.Launch(
        args(tmp_path),
        {"ALPHA_RDAGENT_SOURCE": tmp_path, "ALPHA_FACTOR_PYTHON": tmp_path / "a/b/c/python"},
    )
    job.run.mkdir()

    def refuse(*args: object, **kwargs: object) -> None:
        raise launch.LaunchError("stop at first work")

    monkeypatch.setattr(job, "check", refuse)
    monkeypatch.setattr(job, "spawn", refuse)
    with pytest.raises(launch.LaunchError):
        getattr(job, method)(*(["http://unused", "token"] if method == "loop" else []))
    row = json.loads((job.run / "launch.jsonl").read_text().splitlines()[0])
    assert row["step"] == method and row["event"] == "start"
