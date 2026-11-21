"""Read-only Setup Lab routes, using the bounded stored-artifact reader."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path
from polars.exceptions import PolarsError

from alpha_web import _setup_runs
from alpha_web.api._common import data_dir
from alpha_web.api.models.setup_runs import SetupFigure, SetupRunDetail, SetupRunList

router = APIRouter(prefix="/api/setup/runs", tags=["setup"])


def _read[Result](action: Callable[[], Result]) -> Result:
    try:
        return action()
    except FileNotFoundError as exc:
        raise HTTPException(404, "The recorded setup run was not found.") from exc
    except (OSError, ValueError, TypeError, KeyError, PolarsError) as exc:
        raise HTTPException(
            422, "The setup records could not be read safely. Check the recorded files."
        ) from exc


@router.get("", response_model=SetupRunList)
def list_runs() -> SetupRunList:
    """List completed setup finds, newest recorded date first."""
    return _read(lambda: _setup_runs.list_runs(data_dir()))


@router.get("/{find_id}", response_model=SetupRunDetail)
def run_detail(
    find_id: Annotated[str, Path(pattern=r"^[0-9a-f]{16}$", max_length=16)],
) -> SetupRunDetail:
    """Relay one find and all study/trade records linked by its stored identity."""
    return _read(lambda: _setup_runs.read_run(data_dir(), find_id))


@router.get("/{find_id}/sheets/{kind}/{number}", response_model=SetupFigure)
def sheet(
    find_id: Annotated[str, Path(pattern=r"^[0-9a-f]{16}$", max_length=16)],
    kind: Annotated[str, Path(pattern=r"^(accepted|rejected)$")],
    number: Annotated[str, Path(pattern=r"^\d{3}$")],
) -> SetupFigure:
    """Read one recorded match sheet; the detail carries only the first, to stay small."""
    return _read(lambda: _setup_runs.read_sheet(data_dir(), find_id, f"sheets/{kind}-{number}.png"))
