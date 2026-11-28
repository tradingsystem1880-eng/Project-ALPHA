"""The web run words name every recorded status; the run files refuse linked record paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpha_web import _rdagent_run_files as files
from alpha_web import _rdagent_run_words as words
from alpha_web.api import rdagent


def test_status_sentences_name_each_refusal_and_refuse_an_unmapped_status() -> None:
    assert frozenset({"refused_closed_family", "no_admissible_idea"}) == words.REFUSED_STATUSES
    assert words.status_sentence("refused_closed_family", None)
    reason = next(iter(words.STATUS_SENTENCES))
    assert words.status_sentence("FAILED", reason) == words.STATUS_SENTENCES[reason]
    with pytest.raises(ValueError, match="status"):
        words.status_sentence("NEW_UNMAPPED_STATUS", None)


def test_a_record_path_refuses_a_linked_folder(tmp_path: Path) -> None:
    (tmp_path / "real").mkdir()
    assert files._record_path(tmp_path, "real/file.json") == tmp_path / "real" / "file.json"
    (tmp_path / "link").symlink_to(tmp_path / "real")
    with pytest.raises(ValueError, match="symbolic"):
        files._record_path(tmp_path, "link/file.json")


def test_the_run_reader_routes_are_served() -> None:
    paths = {getattr(route, "path", None) for route in rdagent.router.routes}
    assert {
        "/api/rdagent/runs",
        "/api/rdagent/runs/{run_id}",
        "/api/rdagent/runs/{run_id}/journeys/{idea_id}",
        "/api/rdagent/runs/{run_id}/journeys/{idea_id}/figures/{filename}",
    } <= paths
