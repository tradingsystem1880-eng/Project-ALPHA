"""Daily approval bindings cover logic and tolerate comments in the nine added guards."""

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from alpha_cli import _native_rule_environment as environment
from alpha_cli._native_daily_rule_study import DailyRuleStudyV1
from alpha_cli._structural_digest import file_binding

ROOT = Path(environment.__file__).parent
EDITS = {
    "_control_schema.py": ("sign_count >= 0", "sign_count > 0"),
    "_native_daily_rule_history.py": (
        "_MAX_HISTORY_RECORDS = 10_000",
        "_MAX_HISTORY_RECORDS = 9_999",
    ),
    "_ml_observation_store.py": ("_MAX_EVENTS = 1026", "_MAX_EVENTS = 1025"),
    "_native_rule_economics.py": ("len(fills) != 4", "len(fills) != 3"),
    "_native_rule_study.py": (
        "hashlib.sha256(raw).hexdigest() != _DATA_SHA256",
        "hashlib.sha256(raw).hexdigest() == _DATA_SHA256",
    ),
    "job_capacity.py": ("index + 1 < len(args)", "index + 1 <= len(args)"),
    "paper_resources.py": ("len(raw_links) > 64", "len(raw_links) > 63"),
    "run_store.py": (
        "_RUN_ID_RE.fullmatch(run_id) is not None",
        "_RUN_ID_RE.fullmatch(run_id) is None",
    ),
    "run_context.py": ('context.get("schema_version") != 1', 'context.get("schema_version") != 2'),
}


@pytest.mark.parametrize("name", EDITS)
def test_added_guard_logic_changes_approval_but_layout_does_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    for guard in environment.DAILY_GUARD_FILES:
        (tmp_path / guard).write_bytes((ROOT / guard).read_bytes())
    monkeypatch.setattr(environment, "__file__", str(tmp_path / "_native_rule_environment.py"))
    monkeypatch.setattr(environment, "measure_rule_environment", lambda _: "e" * 64)
    study = cast(DailyRuleStudyV1, SimpleNamespace(query_sha256="a" * 64))

    def fingerprint() -> str | None:
        return environment.rule_implementation_fingerprints(True, daily_study=study)["code"]

    original = fingerprint()
    source = (ROOT / name).read_text()
    before, after = EDITS[name]
    assert source.count(before) == 1
    (tmp_path / name).write_text(source.replace(before, after, 1))
    assert fingerprint() != original
    (tmp_path / name).write_text("\n" + source + "\n# A comment has no runtime effect.\n")
    assert fingerprint() == original


@pytest.mark.parametrize("name", EDITS)
def test_added_guards_bind_by_structure(name: str) -> None:
    assert file_binding(ROOT / name)["mode"] in {"structure", "structure-with-docstrings"}


def test_environment_binds_its_own_bytes() -> None:
    assert file_binding(ROOT / "_native_rule_environment.py")["mode"] == "bytes"
