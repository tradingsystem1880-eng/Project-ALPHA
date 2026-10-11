"""Advisory Codex findings require real successful receipts; binding is not truth."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from alpha_cli.investigation_case import Case


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observation: str = Field(min_length=1, max_length=2000)
    receipt_ids: list[str] = Field(min_length=1, max_length=3)


class InvestigationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    findings: list[Finding] = Field(min_length=1, max_length=6)
    hypotheses: list[str] = Field(max_length=6)
    next_tests: list[str] = Field(max_length=6)
    limitations: list[str] = Field(min_length=1, max_length=6)


def verify_report(case: Case, text: str) -> dict[str, Any]:
    case.verify()
    report = InvestigationReport.model_validate_json(text)
    receipts = {r["id"]: r for r in case.receipts() if r["status"] == "succeeded"}
    if not any(r["action"] == "inspect_execution" for r in receipts.values()):
        raise ValueError("Report requires successful execution inspection")
    for finding in report.findings:
        if any(identity not in receipts for identity in finding.receipt_ids):
            raise ValueError("Report cites nonexistent or unsuccessful evidence")
    return {
        "schema_version": 1,
        "authority": "none",
        "admitted": False,
        "claim_verification": "binding_only",
        "case_id": case.context()["case_id"],
        "report": report.model_dump(),
        "receipts": list(receipts.values()),
    }
