"""Explicit comparison drafts and linked revisions for managed investigation cases."""

from __future__ import annotations

import hashlib
import json
import signal
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import FrameType
from typing import Any

from alpha_cli.comparison_acquisition import (
    AcquisitionPlan,
    AcquisitionSeries,
    _scope,
    acquire_comparisons,
    draft_acquisition,
)
from alpha_cli.investigation_case import Case
from alpha_cli.investigation_comparisons import ComparisonPlan
from alpha_cli.investigation_workspace import (
    _directory,
    _lock,
    _read,
    _register,
    _reserve_staging,
    _run,
    _write,
)
from alpha_cli.investigation_workspace_contracts import (
    ComparisonAcquireRequest,
    ComparisonDraft,
    ComparisonDraftRequest,
    InvestigationView,
)
from alpha_core import DataError


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _draft(directory: Path, digest: str) -> AcquisitionPlan:
    import re

    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise DataError("Invalid comparison draft hash")
    value = _read(directory / f"comparison-draft-{digest}.json")
    if _digest(value) != digest:
        raise DataError("Comparison draft changed")
    return AcquisitionPlan.model_validate_json(json.dumps(value))


def _projection(plan: AcquisitionPlan) -> ComparisonDraft:
    return ComparisonDraft(
        plan_sha256=_digest(plan.model_dump(mode="json")),
        start=plan.start.isoformat(),
        end=plan.end.isoformat(),
        series=[
            {key: item.model_dump()[key] for key in ("symbol", "asset_class", "role")}
            for item in plan.series
        ],
    )


def draft(root: Path, identifier: str, request: ComparisonDraftRequest) -> ComparisonDraft:
    directory = _directory(root, identifier)
    _read(directory / "workspace.json")
    with _lock(directory):
        plan = draft_acquisition(
            Case.open(directory),
            [AcquisitionSeries(**item.model_dump()) for item in request.series],
        )
        body = plan.model_dump(mode="json")
        digest = _digest(body)
        path = directory / f"comparison-draft-{digest}.json"
        if not path.exists():
            if len(list(directory.glob("comparison-draft-" + "[0-9a-f]" * 64 + ".json"))) >= 8:
                raise DataError("Comparison draft limit reached (8)")
            _write(path, body, immutable=True)
        else:
            _draft(directory, digest)
        _write(directory / "comparison-draft-current.json", {"plan_sha256": digest})
    return _projection(plan)


@contextmanager
def _interruptible() -> Iterator[None]:
    def interrupted(signum: int, frame: FrameType | None) -> None:
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def acquire(root: Path, identifier: str, request: ComparisonAcquireRequest) -> InvestigationView:
    from alpha_cli.investigation_workspace import show

    directory = _directory(root, identifier)
    before = show(root, identifier)
    with _lock(directory), _interruptible():
        plan = _draft(directory, request.plan_sha256)
        pointer = _read(directory / "comparison-draft-current.json")
        if pointer["plan_sha256"] != request.plan_sha256:
            raise DataError("Preview changed; review the latest comparison request")
        state = _read(directory / "workspace-state.json")
        previous_status = state["status"]
        state.update(
            status="running",
            error=None,
            progress=[
                {
                    "stage": "acquiring",
                    "message": "Acquiring and checking explicit comparison data.",
                }
            ],
        )
        _write(directory / "workspace-state.json", state)
        try:
            result = acquire_comparisons(Case.open(directory), plan)
            if result["status"] == "succeeded":
                link = directory / "comparison-child.json"
                if link.exists():
                    child_id = _read(link)["id"]
                    show(root, child_id)
                else:
                    reservation = directory / "comparison-child-reservation.json"
                    if not reservation.exists():
                        _write(
                            reservation,
                            {"id": uuid.uuid4().hex, "plan_sha256": request.plan_sha256},
                            immutable=True,
                        )
                    reserved = _read(reservation)
                    if reserved["plan_sha256"] != request.plan_sha256:
                        raise DataError("Comparison child belongs to another frozen request")
                    child_id = reserved["id"]
                    target = _directory(root, child_id)
                    if not target.exists():
                        staging = _reserve_staging(target)
                        child = Case.create(
                            staging,
                            _run(root, before.run_id),
                            before.cutoff,
                            before.question,
                            "gpt-6-astra",
                            comparisons=ComparisonPlan.model_validate(result["comparisons"]),
                            data_dir=Path(result["data_root"]),
                        )
                        _register(child, child_id, before.run_id, parent_id=identifier)
                        import os

                        os.rename(staging, target)
                        fd = os.open(target.parent, os.O_RDONLY)
                        try:
                            os.fsync(fd)
                        finally:
                            os.close(fd)
                    child_view = show(root, child_id)
                    if child_view.parent_id != identifier:
                        raise DataError("Comparison child lineage mismatch")
                    _write(link, reserved, immutable=True)
                state.update(status=previous_status, error=None)
            else:
                state.update(
                    status=previous_status,
                    error="Comparison acquisition failed; retained batch will not retry.",
                )
        except KeyboardInterrupt:
            state.update(
                status=previous_status,
                error="Comparison acquisition interrupted; ambiguous requests cannot retry.",
            )
        except (DataError, RuntimeError, ValueError, OSError) as exc:
            state.update(status=previous_status, error=str(exc)[:2000])
        _write(directory / "workspace-state.json", state)
    return show(root, identifier)


def details(root: Path, identifier: str) -> dict[str, Any]:
    directory = _directory(root, identifier)
    result: dict[str, Any] = {}
    pointer = directory / "comparison-draft-current.json"
    if pointer.exists():
        result["comparison_draft"] = _projection(_draft(directory, _read(pointer)["plan_sha256"]))
    acquired = directory / "comparison-acquisition"
    if acquired.is_symlink():
        raise DataError("Acquisition directory cannot be symlinked")
    if acquired.exists():
        result["acquisition_status"] = "incomplete"
        if (acquired / "result.json").exists():
            request = _read(acquired / "request.json")
            plan = AcquisitionPlan.model_validate_json(json.dumps(request["plan"]))
            from alpha_cli.comparison_acquisition_evidence import verify_batch

            scope = _scope(Case.open(directory), plan)
            if request != scope:
                raise DataError("Acquisition request no longer matches its frozen scope")
            receipt = verify_batch(acquired, scope)
            result["acquisition_status"] = receipt["status"]
    link = directory / "comparison-child.json"
    if link.exists():
        child_id = _read(link)["id"]
        metadata = _read(_directory(root, child_id) / "workspace.json")
        if metadata["parent_id"] != identifier:
            raise DataError("Comparison child lineage mismatch")
        result["comparison_child_id"] = child_id
    return result
