"""Read existing approval records for one fixed synthetic rule admission."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from alpha_cli._native_rule_protocol import require_rule_confirmation, validate_rule_contract
from alpha_cli.control_store import ControlStore
from alpha_core import DataError


@dataclass(frozen=True)
class RuleAuthority:
    root: Path
    project_id: str
    contract_id: str

    def verify(self) -> dict[str, object]:
        store = ControlStore(self.root)
        with store._transaction(write=False) as connection:
            row = store._require_research_contract(connection, self.project_id, self.contract_id)
            payload = store._validate_research_contract_for_approval(connection, row)
            validate_rule_contract(payload)
            review = store._latest_research_review(connection, self.contract_id)
            if review is None or review["decision"] != "approve" or review["actor_kind"] != "human":
                raise DataError("rule admission requires the exact owner-approved contract")
            require_rule_confirmation(
                connection, self.project_id, self.contract_id, str(review["actor"])
            )
        return payload

    def reopen_daily_inputs(self) -> None:
        """Reverify consumed owner authority, exact storage and frozen query before effects."""
        from alpha_cli._native_daily_rule_protocol import (
            contract_is_daily,
            reopen_daily_study,
            study_from_contract,
        )

        payload = self.verify()
        if contract_is_daily(payload):
            reopen_daily_study(self.root, study_from_contract(payload))
