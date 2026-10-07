import argparse
import json
from pathlib import Path

import pytest

from alpha_eval import cli, regression
from alpha_eval.scenarios import load_all


def test_revision_uses_frozen_scenarios(tmp_path: Path) -> None:
    s = load_all()[0].model_copy(update={"title": "Frozen original"})
    revision = tmp_path / "scoring" / "v2"
    revision.mkdir(parents=True)
    (revision / "manifest.json").write_text(json.dumps({"scenarios": {s.id: s.model_dump()}}))
    assert cli.revision_scenarios(tmp_path, "v2")[s.id].title == "Frozen original"


def test_regress_reads_v2_only_cards(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    revision = tmp_path / "scoring" / "v2"
    revision.mkdir(parents=True)
    (revision / "scorecards.jsonl").write_text('{"scenario_id":"S"}\n')
    seen = []
    monkeypatch.setattr(regression, "evaluate", lambda m, cards, p: seen.extend(cards) or [])
    args = argparse.Namespace(base=str(tmp_path), name="unused", revision="v2", probes="", out="")
    cli._cmd_regress(args)
    assert seen == [{"scenario_id": "S"}]


def test_legacy_report_does_not_invent_scoring_provenance(tmp_path: Path) -> None:
    from alpha_eval.report import compare, fingerprint

    fp = fingerprint(tmp_path, tmp_path)
    assert fp.get("scorer_sha256") is None
    assert fp.get("suite_sha256") is None
    summary = {"fingerprint": fp, "suts": {}}
    assert compare(summary, summary)["compatible"] is False
