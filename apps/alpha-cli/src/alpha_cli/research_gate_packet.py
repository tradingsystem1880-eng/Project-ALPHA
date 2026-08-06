"""CLI-owned ResearchGatePacket projection over public control-store reads."""

from __future__ import annotations

from typing import Protocol

from alpha_research import build_research_gate_packet


class ResearchPacketStore(Protocol):
    def research_case_summary(self, project_id: str) -> dict[str, object]: ...

    def research_gate_packet_inputs(
        self, project_id: str, *, ledger_limit: int = 10_000
    ) -> dict[str, object]: ...


def research_report_projection(store: ResearchPacketStore, project_id: str) -> dict[str, object]:
    """Return the legacy progress report or one strict terminal packet."""
    summary = store.research_case_summary(project_id)
    if summary.get("phase") != "closed":
        return {
            "report_schema": "ResearchProgressReportV1",
            "terminal": False,
            "case": summary,
            "warning": "This is a progress report, not a terminal ResearchGatePacket.",
        }
    return build_research_gate_packet(store.research_gate_packet_inputs(project_id)).to_dict()


__all__ = ["ResearchPacketStore", "research_report_projection"]
