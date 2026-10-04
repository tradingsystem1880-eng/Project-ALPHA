"""CLI-owned investigation workspaces; the browser supplies opaque IDs, never paths."""

from __future__ import annotations

import fcntl
import json
import os
import re
import stat
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alpha_cli.codex_session import Session
from alpha_cli.investigation_case import Case
from alpha_cli.investigation_lifecycle import InvestigationInterrupted
from alpha_cli.investigation_report import verify_report
from alpha_cli.investigation_workspace_contracts import (
    InvestigationCreate,
    InvestigationEligibility,
    InvestigationTurnRequest,
    InvestigationView,
)
from alpha_cli.research_suggestions import suggest_investigations
from alpha_core import DataError

MAX_WORKSPACES = 512
_REGISTRY_LOCK = ".registry.lock"


def _registry_entries(directory: Path) -> Iterator[Path]:
    """Bounded read-only scan; interrupted publication consumes the same quota."""
    count = 0
    for path in directory.iterdir():
        if path.name == _REGISTRY_LOCK:
            if path.is_symlink() or not path.is_file():
                raise DataError("Investigation registry lock is unsafe")
            continue
        count += 1
        if count > MAX_WORKSPACES:
            raise DataError("Investigation workspace limit exceeded")
        yield path


def _reserve_staging(target: Path) -> Path:
    """Serialize the global capacity check and durable staging-directory reservation."""
    directory = target.parent
    if directory.is_symlink():
        raise DataError("Investigation directory cannot be symlinked")
    directory.mkdir(parents=True, exist_ok=True)
    parent = os.open(directory.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)
    descriptor = os.open(
        directory / _REGISTRY_LOCK,
        os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
        0o600,
    )
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise DataError("Investigation registry lock must be a regular file")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        if sum(1 for _ in _registry_entries(directory)) >= MAX_WORKSPACES:
            raise DataError(f"Investigation workspace limit reached ({MAX_WORKSPACES})")
        staging = target.with_name(f".pending-{uuid.uuid4().hex}")
        staging.mkdir()
        parent = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
        return staging
    finally:
        os.close(descriptor)


def _read(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise DataError("Investigation record is missing or unsafe")
    with path.open("rb") as stream:
        raw = stream.read(1_048_577)
    if len(raw) > 1_048_576:
        raise DataError("Investigation record exceeds size limit")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise DataError("Investigation record must be an object")
    return value


def _write(path: Path, value: dict[str, Any], *, immutable: bool = False) -> None:
    raw = json.dumps(value, sort_keys=True, allow_nan=False).encode()
    if len(raw) > 1_048_576:
        raise DataError("Investigation record exceeds size limit")
    temporary = path if immutable else path.with_name(f".workspace-{uuid.uuid4().hex}.tmp")
    with temporary.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if not immutable:
        os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _directory(root: Path, identifier: str) -> Path:
    if re.fullmatch(r"[0-9a-f]{32}", identifier) is None:
        raise ValueError("Invalid investigation identifier")
    directory = root.resolve() / "investigations" / identifier
    if any(p.is_symlink() for p in (directory, directory.parent)):
        raise DataError("Investigation directories cannot be symlinked")
    return directory


def _run(root: Path, run_id: str) -> Path:
    if re.fullmatch(r"[0-9a-f]{16}", run_id) is None:
        raise ValueError("Invalid run identifier")
    directory = root.resolve() / "runs" / run_id
    if any(p.is_symlink() for p in (directory, directory.parent)):
        raise DataError("Run directories cannot be symlinked")
    return directory


def eligibility(root: Path, run_id: str) -> InvestigationEligibility:
    directory = _run(root, run_id)
    try:
        manifest = _read(directory / "manifest.json")
        cutoff = manifest.get("research_cutoff")
        if not isinstance(cutoff, str):
            raise DataError("This run has no recorded research cutoff; create a new bounded run.")
        suggest_investigations(directory, cutoff=cutoff)
        return InvestigationEligibility(run_id=run_id, eligible=True, cutoff=cutoff)
    except (DataError, ValueError, OSError) as exc:
        return InvestigationEligibility(run_id=run_id, eligible=False, reason=str(exc)[:1000])


def create(root: Path, request: InvestigationCreate) -> InvestigationView:
    available = eligibility(root, request.run_id)
    if not available.eligible or available.cutoff is None:
        raise DataError(available.reason or "Run is not eligible")
    if request.parent_id is not None:
        raise DataError("Comparison revisions are created only from verified acquired evidence")
    identifier = uuid.uuid4().hex
    directory = _directory(root, identifier)
    staging = _reserve_staging(directory)
    case = Case.create(
        staging, _run(root, request.run_id), available.cutoff, request.question, "gpt-6-astra"
    )
    _register(case, identifier, request.run_id, parent_id=None)
    os.rename(staging, directory)
    descriptor = os.open(directory.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return show(root, identifier)


def _register(case: Case, identifier: str, run_id: str, parent_id: str | None) -> None:
    lock = os.open(case.path / "workspace.lock", os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
    os.close(lock)
    _write(
        case.path / "workspace.json",
        {
            "id": identifier,
            "run_id": run_id,
            "case_id": case.context()["case_id"],
            "parent_id": parent_id,
            "created_at": datetime.now(UTC).isoformat(),
        },
        immutable=True,
    )
    _write(case.path / "workspace-state.json", {"status": "ready", "error": None, "progress": []})


@contextmanager
def _lock(directory: Path) -> Iterator[None]:
    descriptor = os.open(directory / "workspace.lock", os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise DataError("An investigation operation is already running") from exc
        yield
    finally:
        os.close(descriptor)


def _busy(directory: Path) -> bool:
    try:
        with _lock(directory):
            return False
    except DataError:
        return True


def show(root: Path, identifier: str) -> InvestigationView:
    from alpha_cli.investigation_workspace_data import details

    directory = _directory(root, identifier)
    metadata = _read(directory / "workspace.json")
    case = Case.open(directory)
    context = case.context()
    if (metadata["id"], metadata["case_id"], metadata["run_id"]) != (
        identifier,
        context["case_id"],
        context["run_id"],
    ):
        raise DataError("Investigation workspace identity mismatch")
    state = _read(directory / "workspace-state.json")
    session = (
        Session.snapshot(directory, context["case_id"], context["model"])
        if (directory / "codex-session.json").exists()
        else None
    )
    turns = session["turns"] if session else []
    remaining = 4 - len(turns)
    busy = _busy(directory)
    status = state["status"]
    if not busy and turns and turns[-1]["status"] in {"reserved", "running"}:
        status = "blocked"
    elif not busy and status == "running":
        status = "interrupted"
    error = state["error"]
    if status == "blocked":
        error = "An earlier attempt is ambiguous; its reservation cannot be retried automatically."
    verified = None
    if session and session["latest_report"] is not None:
        cached = session["latest_report"]
        verified = verify_report(case, json.dumps(cached["report"]))
        receipts = {item["id"]: item for item in verified["receipts"]}
        if cached["case_id"] != verified["case_id"] or any(
            receipts.get(item["id"]) != item for item in cached["receipts"]
        ):
            raise DataError("Investigation report evidence changed")
    return InvestigationView(
        **details(root, identifier),
        id=identifier,
        run_id=context["run_id"],
        case_id=context["case_id"],
        question=context["question"],
        cutoff=context["cutoff"],
        parent_id=metadata["parent_id"],
        created_at=metadata["created_at"],
        status=status,
        error=error,
        progress=state["progress"],
        report=verified["report"] if verified else None,
        receipts=case.receipts(),
        requests_remaining=context["requests_remaining"],
        turns_remaining=remaining,
        can_resume=not busy and status in {"ready", "failed", "interrupted"} and remaining > 0,
        can_followup=not busy and status == "completed" and remaining > 0 and verified is not None,
    )


def list_cases(root: Path, run_id: str) -> list[InvestigationView]:
    _run(root, run_id)
    directory = root.resolve() / "investigations"
    if directory.is_symlink():
        raise DataError("Investigation directory cannot be symlinked")
    if not directory.exists():
        return []
    found = []
    for path in _registry_entries(directory):
        if re.fullmatch(r"\.pending-[0-9a-f]{32}", path.name):
            continue
        metadata = _read(_directory(root, path.name) / "workspace.json")
        if metadata["run_id"] == run_id:
            found.append(metadata)
    return [
        show(root, item["id"])
        for item in sorted(found, key=lambda item: (item["created_at"], item["id"]), reverse=True)[
            :20
        ]
    ]


def _execute(
    case: Case, request: InvestigationTurnRequest, callback: Callable[[dict[str, Any]], None]
) -> dict[str, Any]:
    from alpha_cli.investigation_lifecycle import run as execute

    return execute(case, followup=request.followup, on_event=callback)


def run(root: Path, identifier: str, request: InvestigationTurnRequest) -> InvestigationView:
    before = show(root, identifier)
    if not (before.can_followup if request.followup else before.can_resume):
        raise DataError("This investigation cannot start that turn; inspect its status and budget.")
    directory = _directory(root, identifier)
    with _lock(directory):
        state: dict[str, Any] = {
            "status": "running",
            "error": None,
            "progress": [
                {"stage": "preparing", "message": "Checking evidence and Codex isolation."}
            ],
        }
        _write(directory / "workspace-state.json", state)

        def progress(event: dict[str, Any]) -> None:
            item = event.get("params", {}).get("item", {})
            method = event.get("method")
            if item.get("type") != "mcpToolCall" or method not in {
                "item/started",
                "item/completed",
            }:
                return
            labels = {
                "inspect_execution": "Inspect execution",
                "inspect_losses": "Inspect losses",
                "suggest_followups": "Propose further tests",
            }
            tool = item.get("tool")
            if tool not in labels:
                raise DataError("Unknown investigation progress tool")
            state["progress"].append(
                {
                    "stage": "tool_started" if method == "item/started" else "tool_completed",
                    "message": labels[tool]
                    + (" started." if method == "item/started" else " finished."),
                }
            )
            state["progress"] = state["progress"][-32:]
            _write(directory / "workspace-state.json", state)

        try:
            _execute(Case.open(directory), request, progress)
            state["status"] = "completed"
            state["progress"].append({"stage": "verifying", "message": "Report evidence verified."})
        except (KeyboardInterrupt, InvestigationInterrupted):
            state.update(
                status="interrupted", error="Investigation cancelled; spent budgets are retained."
            )
        except (DataError, RuntimeError, ValueError, OSError) as exc:
            state.update(status="failed", error=str(exc)[:2000])
        _write(directory / "workspace-state.json", state)
    return show(root, identifier)
