"""The web research adapter stays a closed argv projection over the authoritative CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpha_web import _research


def test_research_projection_uses_only_the_bounded_cli_vocabulary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[list[str], Path, float]] = []

    def fake_run_json(args: list[str], *, data_dir: Path, timeout_seconds: float = 60.0) -> object:
        calls.append((args, data_dir, timeout_seconds))
        return {"ok": True}

    monkeypatch.setattr(_research, "_run_json", fake_run_json)
    answers = {
        "chart_construction": "spy_rth_60m_four_hour_window",
        "event_availability": "second_trough_confirmable",
        "primary_outcome": "four_trading_hour_return_25bp",
    }

    assert _research.capture(data_dir=tmp_path, idea="idea", name="case") == {"ok": True}
    assert _research.get("project", data_dir=tmp_path) == {"ok": True}
    assert _research.propose(
        "project", data_dir=tmp_path, source_pack_id="sp_pack", answers=answers
    ) == {"ok": True}
    assert _research.launch("project", data_dir=tmp_path, stage="pilot") == {"ok": True}
    assert _research.status("project", data_dir=tmp_path) == {"ok": True}
    assert _research.report("project", data_dir=tmp_path) == {"ok": True}

    assert calls == [
        (["research", "capture", "idea", "--json", "--name", "case"], tmp_path, 60.0),
        (["research", "status", "project", "--json"], tmp_path, 60.0),
        (
            [
                "research",
                "draft",
                "project",
                "--source-pack-id",
                "sp_pack",
                "--answer",
                "chart_construction=spy_rth_60m_four_hour_window",
                "--answer",
                "event_availability=second_trough_confirmable",
                "--answer",
                "primary_outcome=four_trading_hour_return_25bp",
                "--json",
            ],
            tmp_path,
            60.0,
        ),
        (["research", "run", "pilot", "project", "--json"], tmp_path, 120.0),
        (["research", "status", "project", "--json"], tmp_path, 60.0),
        (["research", "report", "project", "--json"], tmp_path, 60.0),
    ]


def test_research_projection_rejects_unavailable_stages_and_answer_axes(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must be pilot"):
        _research.launch("project", data_dir=tmp_path, stage="confirm")
    with pytest.raises(ValueError, match="exactly the three"):
        _research.propose(
            "project",
            data_dir=tmp_path,
            source_pack_id="sp_pack",
            answers={"chart_construction": "synthetic_only"},
        )
    with pytest.raises(ValueError, match="unsupported primary_outcome"):
        _research.propose(
            "project",
            data_dir=tmp_path,
            source_pack_id="sp_pack",
            answers={
                "chart_construction": "spy_rth_60m_four_hour_window",
                "event_availability": "second_trough_confirmable",
                "primary_outcome": "highest_backtest_return",
            },
        )


@pytest.mark.parametrize("payload", [[], {1: "not-a-string-key"}])
def test_research_projection_rejects_malformed_cli_output(
    payload: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run_json(args: list[str], *, data_dir: Path, timeout_seconds: float = 60.0) -> object:
        del args, data_dir, timeout_seconds
        return payload

    monkeypatch.setattr(_research, "_run_json", fake_run_json)
    with pytest.raises(RuntimeError, match="invalid research capture projection"):
        _research.capture(data_dir=tmp_path, idea="idea")
