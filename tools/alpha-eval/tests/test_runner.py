import json
from pathlib import Path

import pytest
from helpers import T, judged

from alpha_eval.provenance import bind_manifest, revision_path
from alpha_eval.runner import parse_sut


@pytest.fixture(autouse=True)
def codex_client_version(monkeypatch: pytest.MonkeyPatch) -> None:
    # These offline unit tests mock judging and must not require the external CLI.
    def version(command, *, text):
        assert command == ["codex", "--version"]
        assert text is True
        return "codex-cli test-fixture\n"

    monkeypatch.setattr("subprocess.check_output", version)


def test_new_execution_rejects_claude(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Codex"):
        parse_sut("claude:claude-sonnet-5", tmp_path)
    assert parse_sut("codex:gpt-6-astra", tmp_path).effort == "medium"


def test_manifest_collision_and_resume(tmp_path: Path) -> None:
    p = tmp_path / "run.json"
    bind_manifest(p, {"world": "a"}, resume=False)
    bind_manifest(p, {"world": "a"}, resume=True)
    with pytest.raises(ValueError, match="Incompatible"):
        bind_manifest(p, {"world": "b"}, resume=True)
    with pytest.raises(FileExistsError):
        bind_manifest(p, {"world": "a"}, resume=False)
    assert json.loads(p.read_text()) == {"world": "a"}


def test_revision_cannot_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        revision_path(tmp_path, "../original")


def test_compare_refuses_different_scorers() -> None:
    from alpha_eval.report import compare

    old = {
        "fingerprint": {
            "suite_sha256": "x",
            "scorer_sha256": "old",
            "scoring-meta": {"judge_model": "gpt-6-astra"},
        },
        "suts": {},
    }
    new = {"fingerprint": old["fingerprint"] | {"scorer_sha256": "new"}, "suts": {}}
    assert compare(old, new)["compatible"] is False


def test_manifest_requires_acquisition_identity(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="legacy"):
        bind_manifest(tmp_path / "missing.json", {}, resume=True)


def test_score_writes_separate_revision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from alpha_eval import runner
    from alpha_eval.scenarios import load_all

    scenario = load_all()[0]
    d = tmp_path / "trials" / "old"
    d.mkdir(parents=True)
    (d / "trajectory.jsonl").write_text(T().final("Done").build(scenario.id).model_dump_json())
    old = tmp_path / "scorecards.jsonl"
    old.write_text("historical")
    monkeypatch.setattr(runner, "codex_judge", lambda *a, **kw: judged("none", "Done", {}))
    result = runner.score_all(
        tmp_path, {scenario.id: scenario}, 1, set(), "gpt-6-astra", revision="new"
    )
    metadata = json.loads((result.parent / "scoring-meta.json").read_text())
    assert metadata["same_model_review"] is False
    assert old.read_text() == "historical"
    assert result == tmp_path / "scoring" / "new" / "scorecards.jsonl"
    with pytest.raises(FileExistsError):
        runner.score_all(tmp_path, {scenario.id: scenario}, 1, set(), "gpt-6-astra", revision="new")


def test_reuse_requires_exact_judge_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from alpha_eval import runner
    from alpha_eval.scenarios import load_all

    scenario = load_all()[0]
    d = tmp_path / "trials" / "one"
    d.mkdir(parents=True)
    trajectory = d / "trajectory.jsonl"
    trajectory.write_text(T().final("Done").build(scenario.id).model_dump_json())
    calls = []

    def judge(*args, **kwargs):
        calls.append(args[0])
        return judged("none", "Done", {})

    monkeypatch.setattr(runner, "codex_judge", judge)
    runner.score_all(tmp_path, {scenario.id: scenario}, 1, set(), "gpt-6-astra", revision="old")
    runner.score_all(
        tmp_path,
        {scenario.id: scenario},
        1,
        set(),
        "gpt-6-astra",
        revision="new",
        reuse_revision="old",
    )
    assert len(calls) == 1
    trajectory.write_text(T().final("Changed").build(scenario.id).model_dump_json())
    runner.score_all(
        tmp_path,
        {scenario.id: scenario},
        1,
        set(),
        "gpt-6-astra",
        revision="changed",
        reuse_revision="old",
    )
    assert len(calls) == 2
    manifest = tmp_path / "scoring/old/manifest.json"
    data = json.loads(manifest.read_text())
    data["bridge_sha256"] = "different"
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="bridge_sha256"):
        runner.score_all(
            tmp_path,
            {scenario.id: scenario},
            1,
            set(),
            "gpt-6-astra",
            revision="bad",
            reuse_revision="old",
        )


def test_evidence_limit_does_not_halt_other_judgments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_eval import runner
    from alpha_eval.scenarios import load_all

    scenario = load_all()[0]
    for name in ("a", "b"):
        d = tmp_path / "trials" / name
        d.mkdir(parents=True)
        (d / "trajectory.jsonl").write_text(T().final(name).build(scenario.id).model_dump_json())
    results = iter(
        [
            {"available": False, "error": "Too large", "error_kind": "evidence_limit"},
            judged("none", "Done", {}),
            judged("none", "Done", {}),
        ]
    )
    monkeypatch.setattr(runner, "codex_judge", lambda *a, **kw: next(results))
    result = runner.score_all(
        tmp_path, {scenario.id: scenario}, 1, {scenario.tier}, "gpt-6-astra", revision="new"
    )
    cards = [json.loads(line) for line in result.read_text().splitlines()]
    assert result.name == "scorecards.jsonl"
    assert sum(c["outcome"] == "ungraded" for c in cards) == 1
