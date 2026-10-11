"""Synthetic development campaign; no owner data access or historical result mutation."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from alpha_eval.investigation_cases import CaseKind, digest, export_panel, synthetic_panel
from alpha_eval.investigation_codex import CodexProposer
from alpha_eval.investigation_demo import ACTIONS, run_case, write_once
from alpha_eval.investigation_isolation import command, preflight, worker_env
from alpha_eval.platform import repo_root, tool_root


class Worker:
    def __init__(self, runtime: Path, inputs: Path, expected: str) -> None:
        self.runtime, self.inputs, self.expected = runtime, inputs, expected
        self.script = runtime / "worker.py"
        self.code_hash = digest(self.script.read_bytes())

    def __call__(self, action: str) -> dict[str, Any]:
        if action not in ACTIONS:
            raise ValueError("unregistered action")
        if digest(self.script.read_bytes()) != self.code_hash:
            raise ValueError("worker code changed")
        if digest((self.inputs / "panel.json").read_bytes()) != self.expected:
            raise ValueError("export changed")
        try:
            proc = subprocess.run(
                command(
                    self.runtime,
                    self.inputs,
                    [
                        str(repo_root() / ".venv/bin/python"),
                        str(self.script),
                        str(self.inputs),
                        action,
                    ],
                ),
                cwd=self.runtime,
                env=worker_env(self.runtime),
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("measurement deadline exceeded") from exc
        if proc.returncode:
            raise RuntimeError("measurement failed: " + proc.stderr[-1500:])
        result: dict[str, Any] = json.loads(proc.stdout)
        if result.get("input_sha256") != self.expected:
            raise ValueError("measurement input mismatch")
        if digest((self.inputs / "panel.json").read_bytes()) != self.expected:
            raise ValueError("export mutated during measurement")
        return result


def run_demo(base: Path, model: str, *, live: bool = False) -> dict[str, Any]:
    """Calibration is default. Explicit --live adds actual bounded Codex reasoning."""
    base = base.resolve()
    base.mkdir(parents=True, exist_ok=False)
    runtime = base / "runtime"
    runtime.mkdir()
    script = tool_root() / "worlds/investigation_worker.py"
    shutil.copyfile(script, runtime / "worker.py")
    source_files = sorted((tool_root() / "src/alpha_eval").glob("investigation_*.py")) + [script]
    write_once(
        base / "implementation.json",
        {str(p.relative_to(tool_root())): digest(p.read_bytes()) for p in source_files},
    )
    cases: list[dict[str, Any]] = []
    kinds: tuple[CaseKind, ...] = ("conditional", "indicator_null", "accounting_defect")
    for kind in kinds:
        neutral = digest(kind.encode())[:12]
        root = base / neutral
        root.mkdir()
        inputs = root / "input"
        panel = synthetic_panel(kind)
        hashes = export_panel(panel, inputs, panel["cutoff"])
        boundary = preflight(runtime, inputs)
        write_once(root / "boundary.json", boundary)
        worker = Worker(runtime, inputs, hashes["panel_sha256"])
        calibration = {"inspect_run": worker("inspect_run")}
        if calibration["inspect_run"]["integrity_ok"]:
            for action in ACTIONS[1:]:
                calibration[action] = worker(action)
        write_once(root / "evaluator-calibration.json", calibration)
        # Fail loudly if the designed controls stop exercising the intended behaviors.
        if calibration["inspect_run"]["integrity_ok"] != (kind != "accounting_defect"):
            raise RuntimeError("accounting control calibration failed")
        if kind != "accounting_defect":
            difference = calibration["conditional_diagnostic"]["mean_difference_1_minus_0"]
            if (kind == "conditional" and difference >= -0.01) or (
                kind == "indicator_null" and abs(difference) >= 0.0001
            ):
                raise RuntimeError("descriptive control calibration failed")
        outcome = None
        if live:
            proposer = CodexProposer(root / "reasoning", model)
            outcome = run_case(root / "trial", proposer, worker)
        cases.append(
            dict(case=kind, directory=neutral, **hashes, calibration=calibration, model_run=outcome)
        )
        write_once(root / "case-record.json", cases[-1])
    report: dict[str, Any] = dict(
        schema_version=1,
        synthetic=True,
        live_model_invoked=live,
        model=model if live else None,
        cases=cases,
        inference="Development controls only; no baseline comparison or general uplift claim.",
    )
    write_once(base / "summary.json", report)
    with (base / "report.md").open("x") as handle:
        handle.write(render_report(report))
    return report


def render_report(report: dict[str, Any]) -> str:
    cases = report["cases"]
    lines: list[str] = [
        "# Synthetic investigation development demo",
        "",
        report["inference"],
        "",
        "| Designed case | Accounting | Final received (not graded) | Actions executed |",
        "|---|---|---|---|",
    ]
    for case in cases:
        run = case["model_run"]
        completed = run["status"] if run else "not invoked"
        actions = ", ".join(r["action"] for r in run["receipts"]) if run else "calibration only"
        lines.append(
            f"| {case['case']} | {case['calibration']['inspect_run']['integrity_ok']} "
            f"| {completed} | {actions} |"
        )
    for case in cases:
        run = case["model_run"]
        if run and run["final"]:
            lines += [
                "",
                f"## {case['case']}",
                "",
                run["final"]["conclusion"],
                "",
                "Proposed next tests: " + "; ".join(run["final"]["next_tests"]),
            ]
    return "\n".join(lines) + "\n"
