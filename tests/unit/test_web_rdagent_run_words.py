"""The web run words name every recorded status; the run files refuse linked record paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpha_web import _rdagent_run_files as files
from alpha_web import _rdagent_run_words as words


def test_status_sentence_names_known_states_and_fails_loud_on_new_ones() -> None:
    assert frozenset({"refused_closed_family", "no_admissible_idea"}) == words.REFUSED_STATUSES
    assert words.status_sentence("refused_closed_family", None)
    reason = next(iter(words.STATUS_SENTENCES))
    assert words.status_sentence("FAILED", reason) == words.STATUS_SENTENCES[reason]
    with pytest.raises(ValueError, match="status"):
        words.status_sentence("NEW_UNMAPPED_STATUS", None)


def test_record_path_refuses_symbolic_links(tmp_path: Path) -> None:
    (tmp_path / "real").mkdir()
    assert files._record_path(tmp_path, "real/file.json") == tmp_path / "real" / "file.json"
    (tmp_path / "link").symlink_to(tmp_path / "real")
    with pytest.raises(ValueError, match="symbolic"):
        files._record_path(tmp_path, "link/file.json")
