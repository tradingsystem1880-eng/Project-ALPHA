from alpha_eval.trajectory import Normalizer


def test_codex_search_and_file_changes_are_not_silently_lost() -> None:
    n = Normalizer()
    for kind in ("web_search", "file_change"):
        for state in ("started", "completed"):
            n.codex(
                {
                    "type": f"item.{state}",
                    "item": {
                        "type": kind,
                        "id": kind,
                        "action": {"query": "source"},
                        "changes": [{"path": "x"}],
                    },
                }
            )
    assert [e.tool for e in n.events] == ["web_search", "web_search", "file_change", "file_change"]
    assert "source" in n.events[1].text


def test_judge_sees_notes_past_old_truncation() -> None:
    from helpers import T

    from alpha_eval.judge import render_trajectory

    t = T().call("mcp__alpha__get_project").result("x" * 9000 + "notes: IC=0.031")
    assert "notes: IC=0.031" in render_trajectory(t.build())


def test_timeout_retains_partial_stdout(tmp_path) -> None:
    import io
    import os
    import sys

    from alpha_eval.stream import stream_process

    raw = io.StringIO()
    result = stream_process(
        [sys.executable, "-u", "-c", "import time; print('evidence'); time.sleep(10)"],
        tmp_path,
        dict(os.environ),
        0.2,
        raw,
        lambda _: True,
    )
    assert result["stop"] == "timeout"
    assert raw.getvalue() == "evidence\n"


def test_stream_stops_at_tool_cap(tmp_path) -> None:
    import io
    import os
    import sys

    from alpha_eval.stream import stream_process

    raw = io.StringIO()
    result = stream_process(
        [sys.executable, "-u", "-c", "import time; print('tool'); time.sleep(10)"],
        tmp_path,
        dict(os.environ),
        2,
        raw,
        lambda _: False,
    )
    assert result["stop"] == "tool_call_cap"
    assert "tool" in raw.getvalue()


def test_zero_exit_without_completed_turn_is_invalid(tmp_path, monkeypatch) -> None:
    import io

    from alpha_eval import harness
    from alpha_eval.models import Scenario, Truth, Turn
    from alpha_eval.sandbox import TrialPaths

    scenario = Scenario(
        id="S",
        tier="atomic",
        title="t",
        capabilities=[],
        turns=[Turn(text="one"), Turn(text="two")],
        truth=Truth(summary="t"),
    )
    n = Normalizer()
    calls = 0

    def fake(*args):
        nonlocal calls
        calls += 1
        consume = args[-1]
        if calls == 1:
            consume('{"type":"item.completed","item":{"type":"agent_message","text":"done"}}')
            consume('{"type":"turn.completed"}')
        return {"stop": "completed", "returncode": 0}

    monkeypatch.setattr(harness, "stream_process", fake)
    result = harness.run_codex(
        scenario,
        harness.SutConfig("codex", "gpt-6-astra", tmp_path),
        TrialPaths.create(tmp_path, "S", "codex:gpt-6-astra", 1),
        {},
        n,
        io.StringIO(),
    )
    assert calls == 2 and result["stop"] == "harness_invalid"


def test_timeout_kills_term_resistant_child(tmp_path) -> None:
    import io
    import os
    import sys
    import time

    from alpha_eval.stream import stream_process

    marker = tmp_path / "survived"
    child = (
        "import signal,time,pathlib; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
        f"time.sleep(1); pathlib.Path({str(marker)!r}).write_text('bad')"
    )
    parent = f"import subprocess,time,sys; subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(10)"
    result = stream_process(
        [sys.executable, "-u", "-c", parent],
        tmp_path,
        dict(os.environ),
        0.3,
        io.StringIO(),
        lambda _: True,
    )
    time.sleep(1)
    assert result["stop"] == "timeout" and not marker.exists()


def test_normalization_marks_incomplete_evidence() -> None:
    from alpha_eval.trajectory import MAX_TEXT

    n = Normalizer()
    n.system("x" * (MAX_TEXT + 20))
    assert "[truncated" in n.events[0].text
