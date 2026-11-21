"""The idea card: written before a test, linked by id, never part of any test identity."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_cli.spine.errors import SpineError
from alpha_cli.spine.run import run_idea
from alpha_cli.spine.spec import IdeaSpec, load_spec
from tests.fixtures.cli_fixtures import seed_store

RUNNER = CliRunner()
CLAIM = "Quiet weeks tend to be followed by a bigger move."
SETUP_SPEC = {
    "setup": {
        "name": "synthetic-reclaim",
        "idea": "a synthetic reclaim",
        "assets": ["SPY"],
        "timeframe": "1D",
        "event": "crosses_above(close, sma(close, 20))",
    },
}


def _cli(home: Path, *args: str) -> tuple[int, str]:
    result = RUNNER.invoke(app, ["idea", *args], env={"ALPHA_DATA_DIR": str(home)})
    return result.exit_code, result.output


def _new(home: Path, *extra: str, claim: str = CLAIM) -> str:
    code, output = _cli(home, "new", "--claim", claim, "--json", *extra)
    assert code == 0, output
    return str(json.loads(output)["id"])


def test_id_is_a_short_hash_of_normalised_text(tmp_path: Path) -> None:
    first = _new(tmp_path)
    again = _new(tmp_path, claim="  Quiet weeks   tend to be followed by a bigger move. ")
    assert first == again and len(first) == 12
    assert [p.name for p in (tmp_path / "ideas").glob("*.toml")] == [f"{first}.toml"]


def test_empty_fields_are_allowed_and_shown_as_not_stated(tmp_path: Path) -> None:
    card = _new(tmp_path, "--mechanism", "Traders under-react to calm.")
    code, output = _cli(tmp_path, "show", card)
    assert code == 0
    assert CLAIM in output and "Traders under-react to calm." in output
    assert "not stated" in output
    assert "Not stated yet: who is on the other side of the trade" in output
    assert "what would disprove it" in output
    assert "mechanism" not in output.split("Not stated yet:")[1]
    assert "profit" not in output.lower()


def test_empty_card_is_not_refused(tmp_path: Path) -> None:
    code, output = _cli(tmp_path, "new", "--json")
    assert code == 0, output
    _, shown = _cli(tmp_path, "show", json.loads(output)["id"])
    assert "Not stated yet:" in shown


def test_changed_card_is_new_card_with_supersedes(tmp_path: Path) -> None:
    old = _new(tmp_path)
    new = _new(tmp_path, "--disproved-by", "No move after ten quiet weeks.", "--supersedes", old)
    assert new != old
    assert (tmp_path / "ideas" / f"{old}.toml").is_file()
    _, shown = _cli(tmp_path, "show", new)
    assert f"Replaces card {old}" in shown
    _, shown_old = _cli(tmp_path, "show", old)
    assert f"Replaced by card {new}" in shown_old


def test_from_file_and_list(tmp_path: Path) -> None:
    card_file = tmp_path / "card.toml"
    card_file.write_text(f'claim = "{CLAIM}"\nbaseline = "Buy and hold."\nheld_for = "3 weeks"\n')
    code, output = _cli(tmp_path, "new", "--from", str(card_file), "--json")
    assert code == 0, output
    listing = json.loads(_cli(tmp_path, "list", "--json")[1])
    assert [c["id"] for c in listing["cards"]] == [json.loads(output)["id"]]
    assert listing["cards"][0]["tested"] is False
    assert listing["cards"][0]["tests_linked"] == 0
    saved = datetime.fromisoformat(listing["cards"][0]["saved_at"])
    assert saved.tzinfo is not None and saved.utcoffset() == timedelta(0)
    text = _cli(tmp_path, "list")[1]
    assert CLAIM in text and "no test yet" in text
    assert "no cards" in _cli(tmp_path / "other", "list")[1].lower()


def test_from_file_and_flags_cannot_mix(tmp_path: Path) -> None:
    card_file = tmp_path / "card.toml"
    card_file.write_text(f'claim = "{CLAIM}"\n')
    code, _ = _cli(tmp_path, "new", "--from", str(card_file), "--claim", "x")
    assert code != 0


def test_show_unknown_card_names_the_id(tmp_path: Path) -> None:
    code, output = _cli(tmp_path, "show", "deadbeef0000")
    assert code == 1 and "deadbeef0000" in output


def test_link_is_outside_every_identity() -> None:
    from alpha_study.setup.spec import SetupSpec

    base = load_spec(None, rule="ma_cross", param=["fast=5", "slow=20"], asset=["SPY"])
    linked = IdeaSpec.model_validate({**base.model_dump(mode="json"), "idea_card": "abc123abc123"})
    assert linked.idea_card == "abc123abc123"
    assert linked.spec_sha256 == base.spec_sha256
    assert linked.canonical() == base.canonical()
    setup = SetupSpec.load(SETUP_SPEC)
    setup_linked = SetupSpec.load({**SETUP_SPEC, "idea_card": "abc123abc123"})
    assert setup_linked.idea_card == "abc123abc123"
    assert setup_linked.spec_sha256 == setup.spec_sha256


def test_run_and_test_ids_do_not_change_with_the_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_data.store import ParquetStore

    results = {}
    for name, link in (("plain", False), ("linked", True)):
        home = tmp_path / name
        seed_store(home, n=400)
        ParquetStore(home / "store").write_provenance(
            "SPY", source="alpaca", adapter_version="1", parser_version="1"
        )
        monkeypatch.setenv("ALPHA_DATA_DIR", str(home))
        card = _new(home)
        spec = load_spec(None, rule="ma_cross", param=["fast=5", "slow=20"], asset=["SPY"])
        if link:
            spec = IdeaSpec.model_validate({**spec.model_dump(mode="json"), "idea_card": card})
        out = run_idea(spec, home=home, quick=True)
        results[name] = (out["test_id"], out["results"][0]["run_id"], home, card)
    assert results["plain"][:2] == results["linked"][:2]
    run_dir = results["linked"][2] / "runs" / results["linked"][1]
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["spine"]["idea_card"] == results["linked"][3]
    plain_dir = results["plain"][2] / "runs" / results["plain"][1]
    assert "idea_card" not in json.loads((plain_dir / "manifest.json").read_text())["spine"]
    listing = json.loads(_cli(results["linked"][2], "list", "--json")[1])
    assert listing["cards"][0]["tested"] is True


def test_unknown_card_in_a_spec_is_a_plain_error(tmp_path: Path) -> None:
    seed_store(tmp_path, n=400)
    spec = IdeaSpec.model_validate(
        {
            **load_spec(
                None, rule="ma_cross", param=["fast=5", "slow=20"], asset=["SPY"]
            ).model_dump(mode="json"),
            "idea_card": "feedfacefeed",
        }
    )
    with pytest.raises(SpineError, match="feedfacefeed"):
        run_idea(spec, home=tmp_path, quick=True)


def test_next_counts_cards_and_untested(tmp_path: Path) -> None:
    result = RUNNER.invoke(app, ["next", "--json"], env={"ALPHA_DATA_DIR": str(tmp_path)})
    assert json.loads(result.output)["ideas"] == {"cards": 0, "without_test": 0}
    _new(tmp_path)
    _new(tmp_path, claim="Another synthetic idea.")
    facts = RUNNER.invoke(app, ["next"], env={"ALPHA_DATA_DIR": str(tmp_path)})
    assert "2 idea cards, 2 with no test yet" in facts.output


def test_setup_find_keeps_its_id_and_records_the_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import setup_cmds as find
    from tests.unit.test_setup_find import spec_file, worked_store

    ids = {}
    for name, link in (("plain", False), ("linked", True)):
        home = tmp_path / name
        worked_store(home)
        monkeypatch.setattr(find, "draw_sheet", lambda *a, **k: b"png")
        path = spec_file(home, worked=True)
        card = _new(home)
        if link:
            path.write_text(path.read_text().replace("[setup]\n", f'idea_card="{card}"\n[setup]\n'))
        out = find.run_find(path, home=home)
        manifest = json.loads((Path(out["folder"]) / "manifest.json").read_text())
        ids[name] = (out["find_id"], manifest)
    assert ids["plain"][0] == ids["linked"][0]
    assert "idea_card" not in ids["plain"][1]
    assert ids["linked"][1]["idea_card"]
    bad = tmp_path / "plain" / "spec.toml"
    bad.write_text('idea_card="0123456789ab"\n' + bad.read_text())
    with pytest.raises(SpineError, match="0123456789ab"):
        find.run_find(bad, home=tmp_path / "plain")


def _linked_rule_spec(home: Path, card: str) -> IdeaSpec:
    from alpha_data.store import ParquetStore

    seed_store(home, n=400)
    ParquetStore(home / "store").write_provenance(
        "SPY", source="alpaca", adapter_version="1", parser_version="1"
    )
    spec = load_spec(None, rule="ma_cross", param=["fast=5", "slow=20"], asset=["SPY"])
    return IdeaSpec.model_validate({**spec.model_dump(mode="json"), "idea_card": card})


def test_adding_or_removing_the_link_is_a_repeat_not_a_new_trial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    card = _new(tmp_path)
    linked = _linked_rule_spec(tmp_path, card)
    plain = IdeaSpec.model_validate(linked.model_dump(mode="json"))
    outs = [run_idea(spec, home=tmp_path, quick=True) for spec in (plain, linked, plain)]
    assert len({out["test_id"] for out in outs}) == 1
    ledger = (tmp_path / "ledger" / "trials.jsonl").read_text().splitlines()
    rows = [json.loads(line) for line in ledger]
    assert [("repeat" in row["labels"]) for row in rows] == [False, True, True]
    # The link given on a repeat run is still recorded once, beside the stored run.
    links = (tmp_path / "ideas" / "links.jsonl").read_text().splitlines()
    assert [json.loads(line)["card"] for line in links] == [card]
    assert json.loads(_cli(tmp_path, "list", "--json")[1])["cards"][0]["tested"] is True


def test_a_run_that_fails_does_not_mark_the_card_tested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli.spine import run as spine_run

    def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError("synthetic failure while storing the run")

    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    card = _new(tmp_path)
    monkeypatch.setattr(spine_run, "write_validation_run", broken)
    out = run_idea(_linked_rule_spec(tmp_path, card), home=tmp_path, quick=True)
    assert out["results"][0]["error"]
    assert not (tmp_path / "ideas" / "links.jsonl").exists()
    assert json.loads(_cli(tmp_path, "list", "--json")[1])["cards"][0]["tested"] is False


def test_an_id_clash_is_an_error_not_an_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli.spine import idea_card as cards

    monkeypatch.setattr(cards, "card_id", lambda card: "0123456789ab")
    first, created = cards.save(tmp_path, cards.IdeaCard(claim="first"))
    assert created and first == "0123456789ab"
    with pytest.raises(SpineError, match="0123456789ab"):
        cards.save(tmp_path, cards.IdeaCard(claim="second"))
    assert cards.load(tmp_path, first).claim == "first"


def test_a_path_is_never_an_id(tmp_path: Path) -> None:
    _new(tmp_path)
    (tmp_path / "secret.toml").write_text('claim = "outside"\n')
    for wanted in ("../secret", "../../x", "*", "/etc/passwd"):
        code, output = _cli(tmp_path, "show", wanted)
        assert code != 0 and "outside" not in output
