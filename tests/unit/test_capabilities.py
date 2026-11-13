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


def test_every_live_plan_is_assigned_exactly_once() -> None:
    cmap = capabilities.load(ROOT)
    owned = [plan for cap in cmap.capabilities for plan in cap.plans] + list(cmap.unassigned_plans)
    assert sorted(owned) == sorted(plan.name for plan in cmap.live_plans)


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


_PLAN = "# Live plan\n\n**Delivery state:** In progress — evidence\n"
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
plans = {plans}
"""

_SUMMARY = """
[[plan_summary]]
plan = "2026-11-01-live.md"
title = "Live work"
line = "One line."
"""


def _tree(tmp_path: Path, toml: str, *, defects: bool = False) -> Path:
    files = {
        "docs/superpowers/plans/2026-11-01-live.md": _PLAN,
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
    (tmp_path / "docs/superpowers/plans/archive").mkdir(parents=True, exist_ok=True)
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
        "plans": '["2026-11-01-live.md"]',
    }
    fields.update(overrides)
    return _CAP.format(**fields)


def test_minimal_valid_map_loads(tmp_path: Path) -> None:
    cmap = capabilities.load(_tree(tmp_path, _cap() + _SUMMARY))
    assert [c.id for c in cmap.capabilities] == ["data-download"]
    assert cmap.plan_summaries["2026-11-01-live.md"].title == "Live work"


@pytest.mark.parametrize(
    ("toml", "message"),
    [
        (_cap(id="Data_Download") + _SUMMARY, "kebab-case"),
        (_cap() + _cap() + _SUMMARY, "assigned 2 times|duplicate"),
        (_cap(state="Done") + _SUMMARY, "state must be one of"),
        (_cap(smoke="[]") + _SUMMARY, "Working needs proof_smoke"),
        (_cap(needs='["a GPU"]') + _SUMMARY, "Working needs proof_smoke"),
        (
            _cap(smoke='["tests/smoke/test_s.py::test_skipped_in_body"]') + _SUMMARY,
            "not skipped or xfailed by design",
        ),
        (
            _cap(smoke='["tests/smoke/test_s.py::test_skipped_by_mark"]') + _SUMMARY,
            "not skipped or xfailed by design",
        ),
        (_cap(smoke='["tests/integration/test_x.py::test_round_trip"]') + _SUMMARY, "tests/smoke/"),
        (_cap(smoke='["tests/smoke/test_gone.py::test_end_to_end"]') + _SUMMARY, "does not exist"),
        (_cap(smoke='["tests/smoke/test_s.py::test_absent"]') + _SUMMARY, "not found"),
        (
            _cap(state="Partial", extra=f'missing = "tested in-process only; {_NO_SMOKE}"')
            + _SUMMARY,
            "but lists proof_smoke",
        ),
        (_cap(state="Partial") + _SUMMARY, "must say what is 'missing'"),
        (_cap(proof='["tests/integration/test_missing.py::test_round_trip"]') + _SUMMARY, "file"),
        (_cap(proof='["tests/integration/test_x.py::test_absent"]') + _SUMMARY, "not found"),
        (_cap(entries='["cli: alpha nonsense run"]') + _SUMMARY, "registered alpha command"),
        (_cap(entries='["api: GET /api/nowhere"]') + _SUMMARY, "not a route"),
        (_cap(entries='["panel: apps/x/Missing.tsx"]') + _SUMMARY, "does not exist"),
        (_cap(entries='["script: alpha-nothing"]') + _SUMMARY, "console script"),
        (_cap(plans='["2026-01-01-gone.md"]') + _SUMMARY, "not a live plan"),
        (_cap(plans="[]") + _SUMMARY, "assigned to no capability"),
        (_cap(), "plan_summary"),
        (
            _cap(extra='triage = {card = "1", recommendation = "MAYBE", owner_decision = "no"}')
            + _SUMMARY,
            "recommendation must be one of",
        ),
        (
            _cap(extra='triage = { card = "1", recommendation = "KEEP", owner_decision = "later" }')
            + _SUMMARY,
            "owner_decision must be one of",
        ),
        (_cap() + _SUMMARY + "\n[surprise]\nkey = 1\n", "unknown top-level"),
    ],
)
def test_map_violations_are_rejected(tmp_path: Path, toml: str, message: str) -> None:
    with pytest.raises(capabilities.CapabilityError, match=message):
        capabilities.load(_tree(tmp_path, toml))


def test_unassigned_plan_counts_as_assigned(tmp_path: Path) -> None:
    toml = (
        _cap(plans="[]")
        + _SUMMARY
        + '\n[[unassigned_plan]]\nplan = "2026-11-01-live.md"\nreason = "Clean-up only."\n'
    )
    cmap = capabilities.load(_tree(tmp_path, toml))
    assert cmap.unassigned_plans == {"2026-11-01-live.md": "Clean-up only."}


def test_hidden_tests_cannot_be_named_as_proof(tmp_path: Path) -> None:
    root = _tree(tmp_path, _cap(proof='["tests/holdout/test_x.py::test_round_trip"]') + _SUMMARY)
    with pytest.raises(capabilities.CapabilityError, match="hidden test"):
        capabilities.load(root)


def test_working_requires_a_smoke_check_not_just_in_process_tests(tmp_path: Path) -> None:
    in_process_only = _cap(smoke="[]", state="Partial", extra=f'missing = "tested; {_NO_SMOKE}"')
    cap = capabilities.load(_tree(tmp_path, in_process_only + _SUMMARY)).capabilities[0]
    assert cap.state == "Partial"
    assert cap.proof_synthetic
    assert cap.proof_smoke == ()


def test_working_counts_only_smoke_checks_that_really_run(tmp_path: Path) -> None:
    smoke = (
        '["tests/smoke/test_s.py::test_skipped_in_body", "tests/smoke/test_s.py::test_end_to_end"]'
    )
    cap = capabilities.load(_tree(tmp_path, _cap(smoke=smoke) + _SUMMARY)).capabilities[0]
    assert cap.state == "Working"


_STRICT = "tests/smoke/test_defects.py::test_strict_defect"
_LOOSE = "tests/smoke/test_defects.py::test_loose_defect"


def _defect(node: str) -> str:
    return f'\n[[known_defect]]\ntitle = "Broken"\nnode = "{node}"\nhow_to_reproduce = "run it"\n'


def test_known_defects_load_when_each_xfail_smoke_check_is_listed(tmp_path: Path) -> None:
    toml = _cap() + _SUMMARY + _defect(_STRICT)
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
    toml = _cap() + _SUMMARY + _defect(node)
    with pytest.raises(capabilities.CapabilityError, match=message):
        capabilities.load(_tree(tmp_path, toml, defects=True))
