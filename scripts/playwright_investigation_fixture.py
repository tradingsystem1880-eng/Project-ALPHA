"""Test-server-only inference/provider doubles; production routes still execute the real CLI."""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI


def install(app: FastAPI, data_dir: Path) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import shutil

    from alpha_web import _invoke
    from tests.unit.test_comparison_acquisition import parent_case

    @app.post("/__fixture/investigations", include_in_schema=False)
    def seed() -> dict[str, str]:
        if not (data_dir / "runs/1234567890abcdef").exists():
            temporary = data_dir / "fixture-source"
            temporary.mkdir()
            parent_case(temporary)
            (data_dir / "runs").mkdir(exist_ok=True)
            shutil.copytree(temporary / "1234567890abcdef", data_dir / "runs/1234567890abcdef")
        return {"run_id": "1234567890abcdef"}

    original = _invoke._command

    def command(args: list[str]) -> list[str]:
        if args[:3] in (
            ["research", "investigations", "run"],
            ["research", "investigations", "acquire"],
        ):
            return [sys.executable, str(Path(__file__).resolve()), *args]
        return original(args)

    _invoke._command = command


def main() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from alpha_cli import (
        comparison_acquisition,
        comparison_acquisition_worker,
        investigation_workspace,
    )
    from alpha_cli.codex_session import Session
    from alpha_cli.investigation_case import Case
    from alpha_cli.investigation_report import verify_report
    from alpha_cli.investigation_workspace_contracts import InvestigationTurnRequest
    from alpha_cli.investigation_workspace_data import _interruptible
    from alpha_cli.main import main as cli
    from tests.unit.test_comparison_acquisition import fixture_dispatch, provider_result

    def inference(
        case: Case, request: InvestigationTurnRequest, callback: Callable[[dict[str, Any]], None]
    ) -> dict[str, Any]:
        context = case.context()
        with _interruptible(), Session(case.path, context["case_id"], context["model"]) as session:
            session.bind_thread("playwright-fixture")
            number = session.reserve_turn(prompt={"followup": request.followup})
            session.start_turn(f"fixture-{number}")
            if request.followup == "pause for cancellation test":
                time.sleep(30)
            receipt = case.call("inspect_execution")
            case.call("inspect_losses")
            report = verify_report(
                case,
                json.dumps(
                    {
                        "findings": [
                            {
                                "observation": "Synthetic fixture has a concentrated drawdown.",
                                "receipt_ids": [receipt["id"]],
                            }
                        ],
                        "hypotheses": ["Market exposure is an untested explanation."],
                        "next_tests": ["Compare explicit market proxies over the loss window."],
                        "limitations": [
                            "Synthetic browser acceptance; model and provider are test doubles."
                        ],
                    }
                ),
            )
            session.finish_turn("completed", report=report)
            return report

    investigation_workspace._execute = inference
    comparison_acquisition_worker._fetch = provider_result
    comparison_acquisition._dispatch = fixture_dispatch
    os.environ["ALPHA_TIINGO_API_KEY"] = "playwright-fixture-only"
    cli()


if __name__ == "__main__":
    main()
