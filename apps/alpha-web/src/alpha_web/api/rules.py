"""``/api/rules`` — the owner's saved rule strategies (Strategy Builder) via ``alpha rules``."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from alpha_web import _rules
from alpha_web.api._common import data_dir
from alpha_web.api.models import (
    RuleDeleted,
    RuleList,
    RuleRecord,
    RuleSaveRequest,
    RuleValidateRequest,
    RuleValidation,
)

router = APIRouter(prefix="/api", tags=["rules"])


@router.get("/rules", response_model=RuleList)
def list_rules() -> dict[str, Any]:
    """Every saved rule set (a hand-edited invalid file is listed with its error, never hidden)."""
    return _rules.list_rules(data_dir=data_dir())


@router.post("/rules/validate", response_model=RuleValidation)
def validate_rule(body: RuleValidateRequest) -> dict[str, Any]:
    """Strict parse without saving — the builder's live check; invalid is a report, not a 4xx."""
    return _rules.validate(body.spec, data_dir=data_dir())


@router.get("/rules/{name}", response_model=RuleRecord)
def show_rule(name: str) -> dict[str, Any]:
    try:
        return _rules.show(name, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/rules", response_model=RuleRecord)
def save_rule(body: RuleSaveRequest) -> dict[str, Any]:
    """Validate and save (or overwrite) ``data_dir/rules/<name>.json`` through the CLI."""
    try:
        return _rules.save(body.name, body.spec, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/rules/{name}", response_model=RuleDeleted)
def delete_rule(name: str) -> dict[str, Any]:
    try:
        return _rules.delete(name, data_dir=data_dir())
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
