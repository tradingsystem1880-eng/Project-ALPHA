"""Setup for a distinct, frozen judgment cohort, reusing isolated measurement semantics."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from alpha_eval.investigation_cases import digest, export_panel
from alpha_eval.investigation_demo import ACTIONS, write_once
from alpha_eval.investigation_isolation import preflight
from alpha_eval.investigation_judgment_cases import CASES, judgment_panel
from alpha_eval.investigation_runner import Worker
from alpha_eval.platform import tool_root


def judgment_schedule() -> list[dict[str, str]]:
    modes = ("prechecked", "fixed")
    return [
        dict(case=case, mode=modes[(offset + position) % 2])
        for offset, case in enumerate(CASES)
        for position in range(2)
    ]


def measure_action(
    worker: Callable[[str], dict[str, Any]], action: str, injected_failure: str | None
) -> dict[str, Any]:
    if action == injected_failure:
        raise RuntimeError("injected measurement outage: local context service unavailable")
    return worker(action)


def prepare_judgment(base: Path) -> dict[str, Any]:
    base = base.resolve()
    base.mkdir(parents=True, exist_ok=False)
    runtime = base / "runtime"
    runtime.mkdir()
    script = tool_root() / "worlds/investigation_worker.py"
    shutil.copyfile(script, runtime / "worker.py")
    sources = sorted((tool_root() / "src/alpha_eval").glob("investigation_*.py")) + [script]
    write_once(
        base / "implementation.json",
        {str(p.relative_to(tool_root())): digest(p.read_bytes()) for p in sources},
    )
    cases = []
    for kind in CASES:
        root = base / digest(kind.encode())[:12]
        root.mkdir()
        panel = judgment_panel(kind)
        hashes = export_panel(panel, root / "input", panel["cutoff"])
        write_once(root / "boundary.json", preflight(runtime, root / "input"))
        worker = Worker(runtime, root / "input", hashes["panel_sha256"])
        calibration = {action: worker(action) for action in ACTIONS}
        if not calibration["inspect_run"]["integrity_ok"]:
            raise RuntimeError("judgment fixture accounting must reconcile")
        loss = calibration["loss_episodes"]["episodes"][0]
        if kind == "divergent_benchmark" and loss["benchmark_total_return"] <= 0:
            raise RuntimeError("divergent benchmark did not calibrate")
        if kind == "missing_evidence" and (
            loss["benchmark_total_return"] is not None
            or calibration["conditional_diagnostic"].get("status") != "unavailable"
        ):
            raise RuntimeError("missingness control did not calibrate")
        if kind == "hindsight_indicator" and (
            calibration["conditional_diagnostic"]["indicator_provenance"]["kind"]
            != "post_outcome_label"
        ):
            raise RuntimeError("retrospective label control did not calibrate")
        write_once(root / "evaluator-calibration.json", calibration)
        cases.append(
            dict(
                case=kind,
                directory=root.name,
                **hashes,
                calibration=calibration,
                injected_failure="historical_context" if kind == "context_failure" else None,
            )
        )
        write_once(root / "case-record.json", cases[-1])
    summary = dict(cases=cases, synthetic=True, model_invoked=False)
    write_once(base / "summary.json", summary)
    return summary
