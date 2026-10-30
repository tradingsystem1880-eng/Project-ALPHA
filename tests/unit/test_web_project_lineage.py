"""Project history projection preserves tails, upstream limits and error precedence."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpha_web import _development


def _project() -> dict[str, object]:
    return {
        "truncated": {},
        **dict.fromkeys(
            (
                "versions",
                "experiments",
                "stage_states",
                "stage_run_links",
                "attempts",
                "holdouts",
                "holdout_audit",
                "decision_packets",
                "monte_carlo_reviews",
                "research_gate_overrides",
            ),
            [],
        ),
    }


@pytest.mark.parametrize("key", ["stage_run_links", "stage_states"])
@pytest.mark.parametrize("length,upstream", [(0, False), (2, False), (3, False), (1, True)])
def test_nested_history_keeps_latest_rows_and_upstream_truncation(
    key: str, length: int, upstream: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    history = [{"sequence": number} for number in range(length)]
    row = {"state_history": history, "state_history_truncated": upstream}
    project = _project()
    project[key] = [row]
    calls: list[list[str]] = []

    def run(args: list[str], *, data_dir: Path) -> object:
        assert data_dir == tmp_path
        calls.append(args)
        return project

    monkeypatch.setattr(_development, "_run_json", run)
    result = _development.project_detail("project", data_dir=tmp_path, lineage_limit=2)
    assert result[key] == [
        {"state_history": history[-2:], "state_history_truncated": upstream or length > 2}
    ]
    assert calls == [["project", "show", "project", "--lineage-limit", "2", "--json"]]


@pytest.mark.parametrize(
    "key,label",
    [
        ("stage_run_links", "stage state history"),
        ("stage_states", "experiment stage state history"),
    ],
)
@pytest.mark.parametrize("history", [None, {}, [None], [{1: "invalid key"}]])
def test_nested_history_rejects_malformed_rows_with_existing_label(
    key: str, label: str, history: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project()
    project[key] = [{"state_history": history}]
    monkeypatch.setattr(_development, "_run_json", lambda *args, **kwargs: project)
    with pytest.raises(RuntimeError, match=f"^alpha returned an invalid {label} projection$"):
        _development.project_detail("project", data_dir=tmp_path, lineage_limit=2)


def test_stage_link_error_precedes_stage_state_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project()
    project.update(stage_run_links=[{}], stage_states=[{}])
    monkeypatch.setattr(_development, "_run_json", lambda *args, **kwargs: project)
    with pytest.raises(
        RuntimeError, match="^alpha returned an invalid stage state history projection$"
    ):
        _development.project_detail("project", data_dir=tmp_path, lineage_limit=2)
