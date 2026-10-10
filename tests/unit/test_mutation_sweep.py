"""Exhaustive hosted execution is separate from report-only mutation scores."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from typing import Any

import gate
import harness_quant
import mutation_sweep as sweep
import pytest

MODULE = "packages/alpha-validation/src/alpha_validation/dsr.py"


def repo(tmp_path: Path) -> Path:
    path = tmp_path / MODULE
    path.parent.mkdir(parents=True)
    path.write_text("def f(): return 1\n")
    (path.parent / "__init__.py").write_text("")
    (tmp_path / "tests").mkdir()
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\nmarkers=[]\n")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def stats_runner(cmd: list[str], **kwargs: Any) -> tuple[bool, float, str]:
    if "--max-children" in cmd:
        stats = Path(kwargs["cwd"]) / "mutants" / "mutmut-cicd-stats.json"
        stats.parent.mkdir()
        stats.write_text(
            json.dumps({"killed": 1, "survived": 3, "total": 10, "no_tests": 5, "timeout": 1})
        )
        assert cmd[-2:] == ["--max-children", "2"]
        assert kwargs["env"]["VECLIB_MAXIMUM_THREADS"] == "1"
    return True, 0.1, "test log"


def test_inventory_is_exhaustive_deterministic_unique() -> None:
    root = Path(__file__).resolve().parents[2]
    plan = sweep.inventory(root, "commit", "run-1")
    assert plan == sweep.inventory(root, "commit", "run-1")
    assert [job["module"] for job in plan["jobs"]] == gate.all_quant_source_modules(root)
    assert len(plan["expected"]) == len(set(plan["expected"]))
    assert len({sweep.module_key(module) for module in plan["expected"]}) == len(plan["jobs"])
    with pytest.raises(ValueError):
        sweep.validate_inventory(root, plan, "other", "run-1")


def test_scores_report_only_and_checkpoints_are_complete(tmp_path: Path) -> None:
    root = repo(tmp_path)
    plan = sweep.inventory(root, "commit", "run")
    output = tmp_path / "output"
    assert sweep.run_module(root, plan, 0, output, runner=stats_runner) == 0
    summary = sweep.aggregate(plan, output)
    assert summary["infrastructure_complete"]
    assert summary["score_failures"] == [MODULE]
    entry = summary["modules"][MODULE]
    assert entry["kill_rate"] == 0.1 and entry["required"] == 0.9
    record = sweep.load_json(next(output.glob("module-*.json")))
    assert [t["phase"] for t in record["timings"]] == ["preflight", "mutation", "export"]
    assert all((output / t["log"]).read_text() == "test log" for t in record["timings"])
    with pytest.raises(FileExistsError):
        sweep.run_module(root, plan, 0, output, runner=stats_runner)


def test_interrupt_leaves_valid_unfinished_checkpoint(tmp_path: Path) -> None:
    root = repo(tmp_path)
    plan = sweep.inventory(root, "commit", "run")
    output = tmp_path / "output"

    def interrupted(cmd: list[str], **kwargs: Any) -> tuple[bool, float, str]:
        record = sweep.load_json(next(output.glob("module-*.json")))
        assert record["phase"] == "preflight" and record["state"] == "running"
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        sweep.run_module(root, plan, 0, output, runner=interrupted)
    assert sweep.load_json(next(output.glob("module-*.json")))["state"] == "interrupted"
    with pytest.raises(ValueError, match="unfinished"):
        sweep.aggregate(plan, output)


@pytest.mark.parametrize(
    "field,value",
    [
        ("commit", "old"),
        ("run_id", "old"),
        ("expected", []),
        ("module", "wrong.py"),
        ("index", True),
        ("state", "running"),
        ("phase", "mutation"),
        ("report", {}),
        ("schema_version", True),
        ("timings", None),
        ("workers", 3),
        ("elapsed_seconds", float("nan")),
    ],
)
def test_aggregate_rejects_mismatched_records(tmp_path: Path, field: str, value: Any) -> None:
    root = repo(tmp_path)
    plan = sweep.inventory(root, "commit", "run")
    output = tmp_path / "output"
    sweep.run_module(root, plan, 0, output, runner=stats_runner)
    path = next(output.glob("module-*.json"))
    record = sweep.load_json(path)
    record[field] = value
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        sweep.aggregate(plan, output)


def test_aggregate_rejects_missing_duplicate_and_malformed(tmp_path: Path) -> None:
    root = repo(tmp_path)
    plan = sweep.inventory(root, "commit", "run")
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="Missing"):
        sweep.aggregate(plan, output)
    sweep.run_module(root, plan, 0, output, runner=stats_runner)
    path = next(output.glob("module-*.json"))
    duplicate = output / "module-duplicate.json"
    duplicate.write_text(path.read_text())
    with pytest.raises(ValueError, match="Duplicate"):
        sweep.aggregate(plan, output)
    duplicate.write_text('{"state":"complete","state":"running"}')
    with pytest.raises(ValueError, match="Duplicate JSON"):
        sweep.aggregate(plan, output)
    duplicate.write_text("{")
    with pytest.raises(ValueError):
        sweep.aggregate(plan, output)


def test_local_unavailable_unchanged_hosted_unavailable_fails(tmp_path: Path) -> None:
    root = repo(tmp_path)
    plan = sweep.inventory(root, "commit", "run")

    def unavailable(cmd: list[str], **kwargs: Any) -> tuple[bool, float, str]:
        return False, 0, "tool missing"

    assert harness_quant.mutate(root, [MODULE], runner=unavailable)[0] == 0
    assert sweep.run_module(root, plan, 0, tmp_path / "output", runner=unavailable) == 1
    with pytest.raises(ValueError):
        sweep.aggregate(plan, tmp_path / "output")


def test_staging_is_unique_even_for_same_module(tmp_path: Path) -> None:
    root = repo(tmp_path)
    paths: list[Path] = []

    def runner(cmd: list[str], **kwargs: Any) -> tuple[bool, float, str]:
        paths.append(kwargs["cwd"])
        return False, 0, "missing"

    for _ in range(2):
        harness_quant.mutate(root, [MODULE], runner=runner)
    assert paths[0] != paths[2]
    assert not any(path.exists() for path in paths)


def test_timeout_cleans_descendants(tmp_path: Path) -> None:
    heartbeat = tmp_path / "heartbeat"
    code = (
        "import os,time,signal; "
        "pid=os.fork(); "
        "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
        "\nwhile True:\n open('heartbeat','a').write(str(os.getpid())+'\\n'); time.sleep(.02)"
    )
    ok, seconds, output = sweep.command_run(
        [sys.executable, "-c", code], cwd=tmp_path, timeout=0.3, log=tmp_path / "run.log"
    )
    assert not ok and seconds < 4 and "TimeoutExpired" in output
    size = heartbeat.stat().st_size
    time.sleep(0.1)
    assert heartbeat.stat().st_size == size


def test_total_budget_limits_each_phase(tmp_path: Path) -> None:
    root = repo(tmp_path)
    plan = sweep.inventory(root, "commit", "run")
    timeouts: list[float] = []

    def runner(cmd: list[str], **kwargs: Any) -> tuple[bool, float, str]:
        timeouts.append(kwargs["timeout"])
        return False, 0, "missing"

    sweep.run_module(root, plan, 0, tmp_path / "output", timeout=5400, budget=10, runner=runner)
    assert all(0 < value <= 5 for value in timeouts)


@pytest.mark.parametrize(
    "field,value",
    [
        ("total", 11),
        ("skipped", True),
        ("check_was_interrupted_by_user", 1),
        ("kill_rate", 0.9),
        ("required", 0),
        ("status", "pass"),
    ],
)
def test_unfinished_or_inconsistent_counts_rejected(tmp_path: Path, field: str, value: Any) -> None:
    root = repo(tmp_path)
    plan = sweep.inventory(root, "commit", "run")
    output = tmp_path / "output"
    sweep.run_module(root, plan, 0, output, runner=stats_runner)
    path = next(output.glob("module-*.json"))
    record = sweep.load_json(path)
    record["report"]["modules"][MODULE][field] = value
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        sweep.aggregate(plan, output)


def test_aggregate_cli_always_writes_failure_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repo(tmp_path)
    output = tmp_path / "output"
    monkeypatch.setattr(gate, "repo_root", lambda: root)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mutation_sweep.py",
            "aggregate",
            "--commit",
            "commit",
            "--run-id",
            "run",
            "--plan",
            str(tmp_path / "missing.json"),
            "--output",
            str(output),
        ],
    )
    assert sweep.main() == 1
    assert sweep.load_json(output / "mutation-summary.json")["infrastructure_complete"] is False


def test_workflow_bounds_isolation_and_failure_artifacts() -> None:
    text = (
        Path(__file__).resolve().parents[2] / ".github/workflows/mutation-weekly.yml"
    ).read_text()
    assert "fail-fast: false" in text and "max-parallel: 8" in text
    assert "timeout-minutes: 200" in text and "cancel-in-progress: false" in text
    assert "include: ${{ fromJSON(needs.modules.outputs.list) }}" in text
    assert "--index '${{ matrix.index }}'" in text
    assert "needs: [modules, mutate]\n    if: always()" in text
    assert "|| echo" not in text
    assert text.count("if-no-files-found: error") == 3
    assert "mutation-result-${{ env.SWEEP_RUN_ID }}-${{ matrix.index }}" in text
    assert "mutation-summary-${{ env.SWEEP_RUN_ID }}" in text
    assert text.count("if: always()") >= 5


def test_concurrent_same_module_has_independent_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repo(tmp_path)
    paths: list[Path] = []
    barrier = Barrier(2)
    monkeypatch.setattr(gate, "append_audit", lambda *args, **kwargs: None)

    def runner(cmd: list[str], **kwargs: Any) -> tuple[bool, float, str]:
        if "pytest" in cmd:
            staging = Path(kwargs["cwd"])
            paths.append(staging)
            (staging / "sentinel").write_text(str(staging))
            barrier.wait(timeout=5)
            assert (staging / "sentinel").read_text() == str(staging)
            assert len(set(paths)) == 2
        return False, 0, "tool unavailable"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            pool.submit(harness_quant.mutate, root, [MODULE], runner=runner) for _ in range(2)
        ]
        assert all(result.result()[0] == 0 for result in results)
    assert not any(path.exists() for path in paths)


def test_existing_dispatcher_can_verify_new_sweep_before_merge() -> None:
    root = Path(__file__).resolve().parents[2]
    nightly = (root / ".github/workflows/nightly.yml").read_text()
    weekly = (root / ".github/workflows/mutation-weekly.yml").read_text()
    assert "workflow_call:" in weekly
    assert "type: boolean\n        default: false" in nightly
    assert "github.event_name == 'workflow_dispatch' && inputs.mutation_sweep" in nightly
    assert "uses: ./.github/workflows/mutation-weekly.yml" in nightly
    assert "cancel-in-progress: ${{ !inputs.mutation_sweep }}" in nightly
    assert "github.ref" in nightly and "inputs.mutation_sweep || false" in nightly
    assert 'cron: "17 3 * * *"' in nightly
    assert 'cron: "17 4 * * 0"' in weekly
