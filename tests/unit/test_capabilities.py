"""docs/roadmap/capabilities.toml follows its schema and every checkable claim in it is true."""

from __future__ import annotations

from pathlib import Path

import capabilities
import pytest

ROOT = Path(__file__).parents[2]
_NO_SMOKE = capabilities.NO_SMOKE_YET


def test_committed_capability_map_is_valid() -> None:
    cmap = capabilities.load(ROOT)
    assert len(cmap.capabilities) >= 20
    assert capabilities.main([]) == 0


def test_map_and_triage_sheet_list_the_same_cards_and_recommendations() -> None:
    sheet = (ROOT / "docs/roadmap/triage-2026-11.md").read_text(encoding="utf-8")
    table = sheet.split("## Your decisions", 1)[1].split("\n---", 1)[0]
    rows = [line.split("|") for line in table.splitlines() if line.startswith("| ")][2:]
    on_sheet = {cells[1].strip(): cells[3].strip().upper() for cells in rows}
    in_map = {t.card: t.recommendation.upper() for _, t in capabilities.load(ROOT).triage_items()}
    assert set(on_sheet) == set(in_map)
    for card, recommendation in in_map.items():
        assert on_sheet[card].startswith(recommendation.split(" ")[0]), card


# --- schema checks on a minimal synthetic tree --------------------------------------------


_TEST = "def test_round_trip() -> None:\n    pass\n"
_SMOKE = """import pytest


def test_end_to_end() -> None:
    pass


def test_skipped_in_body() -> None:
    pytest.skip("needs the network")


@pytest.mark.skip(reason="by design")
def test_skipped_by_mark() -> None:
    pass
"""
_DEFECT = """import pytest


@pytest.mark.xfail(strict=True, reason="known defect")
def test_strict_defect() -> None:
    assert False


@pytest.mark.xfail(reason="loose")
def test_loose_defect() -> None:
    assert False
"""
_MAIN = '("data", "alpha_cli.data_cmds", "data_app"),\n'
_API = 'router = APIRouter(prefix="/api")\n@router.get("/runs")\n'
_SCRIPTS = '[project.scripts]\nalpha = "alpha_cli.main:main"\n'

_CAP = """
[[capability]]
id = "{id}"
name = "Download data"
what = "Download prices."
see_it = ["uv run alpha data pull SPY"]
entry_points = {entries}
proof_synthetic = {proof}
proof_smoke = {smoke}
real_data = "not yet confirmed (to check on the Mac later)"
needs = {needs}
state = "{state}"
{extra}
"""


def _tree(tmp_path: Path, toml: str, *, defects: bool = False) -> Path:
    files = {
        "tests/integration/test_x.py": _TEST,
        "tests/smoke/test_s.py": _SMOKE,
        "apps/alpha-cli/src/alpha_cli/main.py": _MAIN,
        "apps/alpha-web/src/alpha_web/api/runs.py": _API,
        "apps/alpha-cli/pyproject.toml": _SCRIPTS,
        "docs/roadmap/capabilities.toml": toml,
    }
    if defects:
        files["tests/smoke/test_defects.py"] = _DEFECT
    for rel, text in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return tmp_path


def _cap(**overrides: str) -> str:
    fields = {
        "id": "data-download",
        "entries": '["cli: alpha data pull", "api: GET /api/runs", "script: alpha"]',
        "proof": '["tests/integration/test_x.py::test_round_trip"]',
        "smoke": '["tests/smoke/test_s.py::test_end_to_end"]',
        "needs": "[]",
        "state": "Working",
        "extra": "",
    }
    fields.update(overrides)
    return _CAP.format(**fields)


def test_minimal_valid_map_loads(tmp_path: Path) -> None:
    cmap = capabilities.load(_tree(tmp_path, _cap()))
    assert [c.id for c in cmap.capabilities] == ["data-download"]


@pytest.mark.parametrize(
    ("toml", "message"),
    [
        (_cap(id="Data_Download"), "kebab-case"),
        (_cap() + _cap(), "duplicate"),
        (_cap(state="Done"), "state must be one of"),
        (_cap(smoke="[]"), "Working needs proof_smoke"),
        (_cap(needs='["a GPU"]'), "Working needs proof_smoke"),
        (
            _cap(smoke='["tests/smoke/test_s.py::test_skipped_in_body"]'),
            "not skipped or xfailed by design",
        ),
        (
            _cap(smoke='["tests/smoke/test_s.py::test_skipped_by_mark"]'),
            "not skipped or xfailed by design",
        ),
        (_cap(smoke='["tests/integration/test_x.py::test_round_trip"]'), "tests/smoke/"),
        (_cap(smoke='["tests/smoke/test_gone.py::test_end_to_end"]'), "does not exist"),
        (_cap(smoke='["tests/smoke/test_s.py::test_absent"]'), "not found"),
        (
            _cap(state="Partial", extra=f'missing = "tested in-process only; {_NO_SMOKE}"'),
            "but lists proof_smoke",
        ),
        (_cap(state="Partial"), "must say what is 'missing'"),
        (_cap(proof='["tests/integration/test_missing.py::test_round_trip"]'), "file"),
        (_cap(proof='["tests/integration/test_x.py::test_absent"]'), "not found"),
        (_cap(entries='["cli: alpha nonsense run"]'), "registered alpha command"),
        (_cap(entries='["api: GET /api/nowhere"]'), "not a route"),
        (_cap(entries='["panel: apps/x/Missing.tsx"]'), "does not exist"),
        (_cap(entries='["script: alpha-nothing"]'), "console script"),
        (_cap(extra='docs = ["docs/nowhere.md"]'), "not a Markdown file"),
        (
            _cap(extra='triage = {card = "1", recommendation = "MAYBE", owner_decision = "no"}'),
            "recommendation must be one of",
        ),
        (
            _cap(
                extra='triage = { card = "1", recommendation = "KEEP", owner_decision = "later" }'
            ),
            "owner_decision must be one of",
        ),
        (_cap() + "\n[surprise]\nkey = 1\n", "unknown top-level"),
    ],
)
def test_map_violations_are_rejected(tmp_path: Path, toml: str, message: str) -> None:
    with pytest.raises(capabilities.CapabilityError, match=message):
        capabilities.load(_tree(tmp_path, toml))


def test_hidden_tests_cannot_be_named_as_proof(tmp_path: Path) -> None:
    root = _tree(tmp_path, _cap(proof='["tests/holdout/test_x.py::test_round_trip"]'))
    with pytest.raises(capabilities.CapabilityError, match="hidden test"):
        capabilities.load(root)


def test_working_requires_a_smoke_check_not_just_in_process_tests(tmp_path: Path) -> None:
    in_process_only = _cap(smoke="[]", state="Partial", extra=f'missing = "tested; {_NO_SMOKE}"')
    cap = capabilities.load(_tree(tmp_path, in_process_only)).capabilities[0]
    assert cap.state == "Partial"
    assert cap.proof_synthetic
    assert cap.proof_smoke == ()


def test_working_counts_only_smoke_checks_that_really_run(tmp_path: Path) -> None:
    smoke = (
        '["tests/smoke/test_s.py::test_skipped_in_body", "tests/smoke/test_s.py::test_end_to_end"]'
    )
    cap = capabilities.load(_tree(tmp_path, _cap(smoke=smoke))).capabilities[0]
    assert cap.state == "Working"


_STRICT = "tests/smoke/test_defects.py::test_strict_defect"
_LOOSE = "tests/smoke/test_defects.py::test_loose_defect"


def _defect(node: str) -> str:
    return f'\n[[known_defect]]\ntitle = "Broken"\nnode = "{node}"\nhow_to_reproduce = "run it"\n'


def test_known_defects_load_when_each_xfail_smoke_check_is_listed(tmp_path: Path) -> None:
    toml = _cap() + _defect(_STRICT)
    with pytest.raises(capabilities.CapabilityError, match="test_loose_defect is not listed"):
        capabilities.load(_tree(tmp_path, toml, defects=True))
    (tmp_path / "tests/smoke/test_defects.py").write_text(
        _DEFECT.split("\n\n\n@pytest.mark.xfail(reason")[0] + "\n", encoding="utf-8"
    )
    cmap = capabilities.load(tmp_path)
    assert [(d.title, d.node) for d in cmap.known_defects] == [("Broken", _STRICT)]


@pytest.mark.parametrize(
    ("node", "message"),
    [
        (_LOOSE, "not marked pytest.mark.xfail\\(strict=True\\)"),
        ("tests/smoke/test_s.py::test_end_to_end", "not marked pytest.mark.xfail"),
        ("tests/smoke/test_defects.py::test_absent", "not found"),
        ("tests/smoke/test_nowhere.py::test_strict_defect", "does not exist"),
        ("tests/integration/test_x.py::test_round_trip", "tests/smoke/"),
    ],
)
def test_known_defect_must_be_a_strict_xfail_smoke_check(
    tmp_path: Path, node: str, message: str
) -> None:
    toml = _cap() + _defect(node)
    with pytest.raises(capabilities.CapabilityError, match=message):
        capabilities.load(_tree(tmp_path, toml, defects=True))
