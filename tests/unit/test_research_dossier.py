"""Generated research Markdown is a deterministic projection, never mutable authority."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from alpha_cli.research_dossier import (
    export_research_dossier,
    render_research_dossier,
    verify_research_dossier,
)
from alpha_core import DataError


def _contract() -> dict[str, object]:
    return {
        "schema": "ResearchContractV1",
        "raw_idea": "SPY may bounce after a point-in-time double bottom.",
        "thesis": {
            "mechanism": "Conditional short-horizon mean reversion.",
            "prediction": "Event return exceeds matched control.",
        },
        "primary_claim": {"direction": "positive", "minimum_effect_return": 0.0025},
        "required_falsifiers": ["weekday-only", "shuffled-event"],
        "blocking_questions": [],
    }


def test_dossier_render_is_byte_deterministic_and_embeds_authority_hashes() -> None:
    contract_id = "rc_" + "a" * 64
    summary = {
        "phase": "exploration_review",
        "execution_state": "idle",
        "next_action": "Owner approves or rejects the exploration contract.",
        "responsibility": "owner",
    }
    first = render_research_dossier(
        project_id="11111111-1111-4111-8111-111111111111",
        contract_id=contract_id,
        contract=_contract(),
        summary=summary,
    )
    second = render_research_dossier(
        project_id="11111111-1111-4111-8111-111111111111",
        contract_id=contract_id,
        contract=dict(reversed(_contract().items())),
        summary=dict(reversed(summary.items())),
    )

    assert first == second
    text = first.decode("utf-8")
    assert "GENERATED PROJECTION — DO NOT EDIT" in text
    assert contract_id in text
    assert "Owner approves or rejects" in text
    assert "Canonical Contract (reference only)" in text


def test_export_is_content_addressed_and_manual_edit_fails_verification(tmp_path: Path) -> None:
    contract_id = "rc_" + "b" * 64
    summary = {
        "phase": "triage",
        "execution_state": "idle",
        "next_action": "Codex drafts the contract.",
        "responsibility": "codex",
    }
    receipt = export_research_dossier(
        tmp_path,
        project_id="11111111-1111-4111-8111-111111111111",
        contract_id=contract_id,
        contract=_contract(),
        summary=summary,
    )

    assert receipt.path.name == f"research-contract-{contract_id}.md"
    assert (
        verify_research_dossier(
            receipt.path,
            project_id="11111111-1111-4111-8111-111111111111",
            contract_id=contract_id,
            contract=_contract(),
            summary=summary,
        )
        == receipt
    )

    receipt.path.write_text(receipt.path.read_text(encoding="utf-8") + "manual edit\n")
    with pytest.raises(DataError, match="does not match its deterministic projection"):
        verify_research_dossier(
            receipt.path,
            project_id="11111111-1111-4111-8111-111111111111",
            contract_id=contract_id,
            contract=_contract(),
            summary=summary,
        )


def test_export_rejects_symlink_target(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)

    with pytest.raises(DataError, match="symlink"):
        export_research_dossier(
            linked,
            project_id="11111111-1111-4111-8111-111111111111",
            contract_id="rc_" + "c" * 64,
            contract=_contract(),
            summary={"phase": "captured"},
        )


def test_render_rejects_invalid_ids_and_nonfinite_authority_values() -> None:
    valid_project = "11111111-1111-4111-8111-111111111111"
    valid_contract = "rc_" + "d" * 64
    with pytest.raises(DataError, match="invalid project_id"):
        render_research_dossier(
            project_id="not-a-project",
            contract_id=valid_contract,
            contract=_contract(),
            summary={"phase": "captured"},
        )
    with pytest.raises(DataError, match="invalid contract_id"):
        render_research_dossier(
            project_id=valid_project,
            contract_id="caller-label",
            contract=_contract(),
            summary={"phase": "captured"},
        )
    with pytest.raises(DataError, match="finite JSON"):
        render_research_dossier(
            project_id=valid_project,
            contract_id=valid_contract,
            contract={"schema": "ResearchContractV1", "effect": float("nan")},
            summary={"phase": "captured"},
        )


def test_render_uses_safe_fallbacks_for_wrong_nested_projection_shapes() -> None:
    rendered = render_research_dossier(
        project_id="11111111-1111-4111-8111-111111111111",
        contract_id="rc_" + "e" * 64,
        contract={
            "schema": "ResearchContractV1",
            "thesis": ["not", "an", "object"],
            "primary_claim": ["not", "an", "object"],
        },
        summary={},
    ).decode("utf-8")
    assert "Mechanism: Not yet defined." in rendered
    assert "Not yet defined." in rendered


def test_export_rejects_existing_target_symlink(tmp_path: Path) -> None:
    contract_id = "rc_" + "f" * 64
    real = tmp_path / "real.md"
    real.write_text("owner file", encoding="utf-8")
    target = tmp_path / f"research-contract-{contract_id}.md"
    target.symlink_to(real)
    with pytest.raises(DataError, match="target must not be a symlink"):
        export_research_dossier(
            tmp_path,
            project_id="11111111-1111-4111-8111-111111111111",
            contract_id=contract_id,
            contract=_contract(),
            summary={"phase": "captured"},
        )


def test_export_failure_removes_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "output"

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("simulated atomic replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(DataError, match="export failed"):
        export_research_dossier(
            output,
            project_id="11111111-1111-4111-8111-111111111111",
            contract_id="rc_" + "1" * 64,
            contract=_contract(),
            summary={"phase": "captured"},
        )
    assert list(output.iterdir()) == []


def test_verify_requires_readable_regular_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(DataError, match="regular file"):
        verify_research_dossier(
            tmp_path / "missing.md",
            project_id="11111111-1111-4111-8111-111111111111",
            contract_id="rc_" + "2" * 64,
            contract=_contract(),
            summary={"phase": "captured"},
        )
    path = tmp_path / "dossier.md"
    path.write_text("placeholder", encoding="utf-8")

    def fail_read(_path: Path) -> bytes:
        raise OSError("simulated read failure")

    monkeypatch.setattr(Path, "read_bytes", fail_read)
    with pytest.raises(DataError, match="could not be read"):
        verify_research_dossier(
            path,
            project_id="11111111-1111-4111-8111-111111111111",
            contract_id="rc_" + "2" * 64,
            contract=_contract(),
            summary={"phase": "captured"},
        )
