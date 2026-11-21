"""Link an RD-Agent journey and notes to an idea card."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_cli.spine import idea_card as cards
from tests.unit.test_idea_file import synthetic_home
from tests.unit.test_rdagent_journey import make_run

RUNNER = CliRunner()


def _cli(home: Path, *args: str) -> tuple[int, str]:
    result = RUNNER.invoke(app, list(args), env={"ALPHA_DATA_DIR": str(home)})
    return result.exit_code, result.output


def _journey(tmp_path: Path) -> tuple[Path, str, str]:
    """A synthetic stored journey. Returns (home, run/idea reference, idea id)."""
    run, rows = make_run(tmp_path)
    assert RUNNER.invoke(app, ["ledger", "journey", "--run-dir", str(run)]).exit_code == 0
    home = tmp_path / "data"
    home.mkdir()
    idea = f"1-{rows[1]['code_sha256']}-score"
    return home, f"{run.name}/{idea}", idea


def _facts(home: Path, card: str) -> dict[str, Any]:
    code, out = _cli(home, "idea", "file", card, "--json")
    assert code == 0, out
    facts: dict[str, Any] = json.loads(out)
    return facts


def test_link_unlink_and_missing_journey_refused(tmp_path: Path) -> None:
    home, ref, _ = _journey(tmp_path)
    card = synthetic_home(home, with_runs=False)
    code, out = _cli(home, "idea", "link", card, "--rdagent", ref)
    assert code == 0, out
    assert [r["kind"] for r in cards.link_rows(home, card)] == ["rdagent_journey"]
    assert cards.tested_ids(home) == set()
    assert len(_facts(home, card)["rdagent"]) == 1
    code, out = _cli(home, "idea", "link", card, "--rdagent", ref, "--unlink")
    assert code == 0, out
    assert "rdagent" not in _facts(home, card)
    assert _cli(home, "idea", "link", card, "--rdagent", ref, "--unlink")[0] != 0
    code, out = _cli(home, "idea", "link", card, "--rdagent", ref)
    assert code == 0 and len(_facts(home, card)["rdagent"]) == 1
    bad = ref.replace("score", "other")
    code, out = _cli(home, "idea", "link", card, "--rdagent", bad)
    assert code != 0 and "journey" in out.lower()
    assert _cli(home, "idea", "link", card, "--rdagent", "no-slash")[0] != 0
    assert _cli(home, "idea", "link", card, "--rdagent", "../x/" + ref.split("/")[1])[0] != 0


def test_card_from_an_rdagent_idea(tmp_path: Path) -> None:
    home, ref, _ = _journey(tmp_path)
    code, out = _cli(home, "idea", "new", "--from-rdagent", ref, "--json")
    assert code == 0, out
    card = json.loads(out)["id"]
    stored = cards.load(home, card)
    assert "Look for a recovery." in stored.claim
    assert "declared_direction" not in stored.claim
    assert stored.source == "RD-Agent proposal"
    assert stored.mechanism == "" and "mechanism" in " ".join(stored.not_stated())
    assert len(_facts(home, card)["rdagent"]) == 1
    assert _cli(home, "idea", "new", "--from-rdagent", ref, "--claim", "x")[0] != 0
    assert _cli(home, "idea", "new", "--from-rdagent", ref.replace("score", "zz"))[0] != 0
    assert cards.all_ids(home) == [card]


def test_the_file_returns_the_seven_steps_and_the_map_line(tmp_path: Path) -> None:
    home, ref, _ = _journey(tmp_path)
    card = synthetic_home(home, with_runs=False)
    _cli(home, "idea", "link", card, "--rdagent", ref)
    facts = _facts(home, card)
    entry = facts["rdagent"][0]
    assert entry["ref"] == ref and entry["problem"] is None
    assert len(entry["steps"]) == 7
    stored = json.loads(
        next((tmp_path / "runs" / "synthetic" / "journey").glob("1-*/journey.json")).read_text()
    )
    for got, want in zip(entry["steps"], stored["steps"], strict=True):
        assert got["title"] == want["title"] and got["text"] == want["text"]
        assert [n["value"] for n in got["numbers"]] == [n["value"] for n in want["numbers"]]
    assert {f["id"] for f in entry["figures"]} == set(stored["figures"])
    assert entry["exploratory"] is True
    assert any(s["exploratory"] for s in entry["steps"])
    steps = {row["step"]: row for row in facts["map"]}
    assert steps["worked on by RD-Agent"]["state"] == "done"
    assert steps["worked on by RD-Agent"]["evidence"] == [ref]
    text = _cli(home, "idea", "file", card)[1]
    assert "RD-Agent steps" in text and "exploratory" in text


def test_a_broken_journey_is_a_fault_not_a_gap(tmp_path: Path) -> None:
    home, ref, _ = _journey(tmp_path)
    card = synthetic_home(home, with_runs=False)
    _cli(home, "idea", "link", card, "--rdagent", ref)
    next((tmp_path / "runs" / "synthetic" / "journey").glob("1-*/journey.json")).unlink()
    entry = _facts(home, card)["rdagent"][0]
    assert entry["steps"] == [] and "journey" in entry["problem"]
    assert _facts(home, card)["map"][1]["state"] != "done"


def test_notes_are_append_only_and_newest_first(tmp_path: Path) -> None:
    home = tmp_path / "data"
    home.mkdir()
    card = synthetic_home(home, with_runs=False)
    assert "notes" not in _facts(home, card)
    assert _cli(home, "idea", "note", card, "first thought")[0] == 0
    assert _cli(home, "idea", "note", card, "keep it small", "--decision")[0] == 0
    assert _cli(home, "idea", "note", card, "  ")[0] != 0
    assert _cli(home, "idea", "note", "ffffffffffff", "x")[0] != 0
    notes = _facts(home, card)["notes"]
    assert [(n["text"], n["kind"]) for n in notes] == [
        ("keep it small", "decision"),
        ("first thought", "note"),
    ]
    assert all(n["at"] for n in notes)
    lines = (home / "ideas" / "notes" / f"{card}.jsonl").read_text().splitlines()
    assert [json.loads(x)["text"] for x in lines] == ["first thought", "keep it small"]
    assert "keep it small" in _cli(home, "idea", "file", card)[1]


def test_old_idea_files_are_unchanged_when_nothing_is_linked(tmp_path: Path) -> None:
    card = synthetic_home(tmp_path)
    facts = _facts(tmp_path, card)
    assert sorted(facts) == ["card", "counts", "map", "open_points", "readings"]
    assert "worked on by RD-Agent" not in {row["step"] for row in facts["map"]}


def test_next_names_link_and_note(tmp_path: Path) -> None:
    out = _cli(tmp_path, "next")[1]
    assert "alpha idea link" in out and "alpha idea note" in out


@pytest.mark.parametrize("bad", ["", "a/", "/b", "a/b/c"])
def test_malformed_references_are_refused(tmp_path: Path, bad: str) -> None:
    home = tmp_path / "data"
    home.mkdir()
    card = synthetic_home(home, with_runs=False)
    assert _cli(home, "idea", "link", card, "--rdagent", bad)[0] != 0
