"""Immutable discovery diagnostics. These outputs cannot advance governed research cases."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import timedelta
from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import exchange_calendars as xcals  # type: ignore[import-untyped]
import typer

from alpha_cli import _artifacts, _identity, _runner
from alpha_core import DataError
from alpha_core.config import AlphaSettings
from alpha_research.weekly_diagnostic import VERSION, weekly_diagnostic

diagnostic_app = typer.Typer(
    help="Non-admitted discovery measurements; no gate or deployment authority."
)


@diagnostic_app.command("investigation-tool", hidden=True)
def investigation_tool(case: Path, action: str) -> None:
    """Fixed-case diagnostic seam used by the restricted MCP service."""
    from alpha_cli.investigation_case import Case

    try:
        result = Case.open(case).call(action)
    except (DataError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(result, sort_keys=True, allow_nan=False))


@diagnostic_app.command("investigate")
def investigate(
    case: Path,
    run_id: str | None = None,
    as_of: str | None = None,
    question: str | None = None,
    model: str = "gpt-6-astra",
    resume: bool = False,
) -> None:
    """Investigate one verified recorded run with Codex; persists budget and evidence.

    New case requires --run-id, --as-of and --question. --resume uses the frozen case.
    Only diagnostic research-cutoff runs are supported; never grants research authority.
    """
    import asyncio

    from alpha_cli.codex_investigation import run_investigation
    from alpha_cli.investigation_case import Case

    try:
        if resume:
            if any(value is not None for value in (run_id, as_of, question)):
                raise ValueError("Resume uses frozen context; create a new case for revisions")
            investigation = Case.open(case)
        else:
            if not run_id or re.fullmatch(r"[0-9a-f]{16}", run_id) is None:
                raise ValueError("New case requires --run-id (16 hex characters)")
            if as_of is None or question is None:
                raise ValueError("New case requires --as-of and --question")
            if (case / "case.sqlite3").exists():
                raise ValueError("Case exists; use --resume or choose a new case directory")
            investigation = Case.create(
                case, AlphaSettings().data_dir / "runs" / run_id, as_of, question, model
            )
        result = asyncio.run(run_investigation(investigation))
    except (DataError, OSError, ValueError, RuntimeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(result, sort_keys=True, allow_nan=False))


@diagnostic_app.command("run-plan")
def run_plan(path: Path) -> None:
    """Run a frozen momentum baseline and validation; always read the terminal receipt.

    Non-admitted discovery. Bounds its own operations, not the surrounding agent's data access.
    Repeating the same plan returns verified evidence; interrupted attempts are not retried.
    """
    from alpha_cli.research_execution import BaselineExecutionPlan, execute_plan

    try:
        plan = BaselineExecutionPlan.model_validate_json(path.read_text())
        result = execute_plan(plan, data_dir=AlphaSettings().data_dir)
    except (DataError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(result, sort_keys=True, allow_nan=False))


@diagnostic_app.command("execution-digest")
def digest_run(run_id: str, as_of: str = typer.Option(...)) -> None:
    """Verify existing baseline/validation execution, including fills and denied orders."""
    from alpha_cli.research_execution_digest import execution_digest

    try:
        if re.fullmatch(r"[0-9a-f]{16}", run_id) is None:
            raise ValueError("expected a 16-hex run ID")
        result = execution_digest(AlphaSettings().data_dir / "runs" / run_id, cutoff=as_of)
    except (DataError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(result, sort_keys=True, allow_nan=False))


@diagnostic_app.command("weekly-classifier")
def weekly_classifier(
    symbol: str,
    snapshot: str = typer.Option(..., help="Immutable snapshot ID"),
    as_of: str = typer.Option(..., help="Inclusive knowledge cutoff YYYY-MM-DD"),
    calendar: str = typer.Option("XNYS", help="Explicit exchange calendar"),
    cost_bps_per_side: float = 2.0,
) -> None:
    """Measure next-week close direction versus majority and momentum baselines.

    Fixed research diagnostic, not a Qlib recipe or an admitted research operator.
    Prints JSON and writes content-bound immutable evidence under diagnostics/.
    """
    settings = AlphaSettings()
    try:
        cutoff = _runner.parse_as_of(as_of)
        bars, _ = _runner.load_bars(
            symbol, data_dir=settings.data_dir, snapshot_id=snapshot, as_of=cutoff
        )
        first, last = bars[0].ts.date(), bars[-1].ts.date()
        cal = xcals.get_calendar(
            calendar,
            start=(first - timedelta(days=10)).isoformat(),
            end=(last + timedelta(days=20)).isoformat(),
        )
        sessions = [
            s.date()
            for s in cal.sessions_in_range(
                first.isoformat(), (last + timedelta(days=10)).isoformat()
            )
        ]
        report = weekly_diagnostic(bars, sessions=sessions, cost_bps_per_side=cost_bps_per_side)
        identity = dict(
            version=VERSION,
            execution_fingerprint=_identity.execution_fingerprint(),
            research_source_sha256=hashlib.sha256(
                Path(weekly_diagnostic.__code__.co_filename).read_bytes()
            ).hexdigest(),
            runtime_versions={
                name: version(name) for name in ("numpy", "scipy", "exchange-calendars")
            },
            python_version=sys.version,
            symbol=symbol,
            snapshot=snapshot,
            as_of=as_of,
            calendar=calendar,
            cost_bps_per_side=cost_bps_per_side,
            snapshot_hash=_runner.verified_snapshot_hash(settings.data_dir, snapshot),
            source_hash=_runner.source_fingerprint(bars),
            calendar_hash=hashlib.sha256(
                json.dumps([s.isoformat() for s in sessions]).encode()
            ).hexdigest(),
        )
        serialized = json.dumps(
            {"identity": identity, "report": report}, sort_keys=True, allow_nan=False
        )
        digest = hashlib.sha256(serialized.encode()).hexdigest()
        directory = settings.data_dir / "diagnostics" / digest
        _artifacts.publish_artifact(
            directory / "evidence.json", lambda p: p.write_text(serialized, encoding="utf-8")
        )
        completion = json.dumps(
            dict(
                schema_version=1,
                admitted=False,
                evidence_sha256=digest,
                evidence_file="evidence.json",
            ),
            sort_keys=True,
        )
        _artifacts.publish_artifact(
            directory / "manifest.json", lambda p: p.write_text(completion, encoding="utf-8")
        )
    except (DataError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(
        json.dumps(
            dict(
                status="completed_evidence",
                admitted=False,
                evidence=str(directory / "evidence.json"),
                sha256=digest,
                metrics=report["metrics"],
            ),
            sort_keys=True,
            allow_nan=False,
        )
    )


@diagnostic_app.command("check-review")
def check_review(path: str) -> None:
    """Check a typed advisory review and its local JSON evidence hashes/selectors.

    This checks content binding, not the truth or sufficiency of a model's claims.
    """
    from alpha_cli.research_workflow_contract import SpecialistReview

    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON object key")
            result[key] = value
        return result

    try:
        review = SpecialistReview.model_validate_json(Path(path).read_text(encoding="utf-8"))
        for evidence in review.evidence:
            raw = Path(evidence.artifact).read_bytes()
            if hashlib.sha256(raw).hexdigest() != evidence.sha256:
                raise ValueError(f"evidence hash mismatch: {evidence.artifact}")
            value = json.loads(raw, object_pairs_hook=unique_object)
            if evidence.pointer:
                for part in evidence.pointer[1:].split("/"):
                    key = part.replace("~1", "/").replace("~0", "~")
                    if isinstance(value, list):
                        if re.fullmatch(r"0|[1-9][0-9]*", key) is None:
                            raise ValueError("non-canonical JSON pointer array index")
                        value = value[int(key)]
                    else:
                        value = value[key]
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(
        json.dumps(
            dict(
                schema_valid=True,
                evidence_resolved=True,
                advisory_only=True,
                claim_truth="not_verified",
                review=review.model_dump(mode="json"),
            )
        )
    )


@diagnostic_app.command("suggest")
def suggest_run(
    run_id: str,
    as_of: str = typer.Option(...),
    proposals: Annotated[
        Path | None, typer.Option(help="Optional typed, basis-bound advisory proposals")
    ] = None,
) -> None:
    """Act as a research teammate: suggest useful next tests over verified existing evidence.

    Read-only retrospective advice. Does not invoke a model, run proposed tests or grant authority.
    """
    from alpha_cli.research_suggestions import suggest_investigations
    from alpha_cli.research_workflow_contract import InvestigationProposals

    try:
        if re.fullmatch(r"[0-9a-f]{16}", run_id) is None:
            raise ValueError("expected a 16-hex run ID")
        extra = None
        if proposals is not None:
            with proposals.open("rb") as source:
                raw = source.read(65_537)
            if len(raw) > 65_536:
                raise ValueError("proposal file exceeds 64 KiB")
            extra = InvestigationProposals.model_validate_json(raw)
        result = suggest_investigations(
            AlphaSettings().data_dir / "runs" / run_id,
            cutoff=as_of,
            proposals=extra.proposals if extra else (),
            basis_sha256=extra.basis_sha256 if extra else None,
        )
    except (DataError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(result, sort_keys=True, allow_nan=False))
