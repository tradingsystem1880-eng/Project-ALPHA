"""The screening CLI records exploratory attempts without entering research governance."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from tests.fixtures.hypothesis_scan_fixtures import frozen_crypto, frozen_equities


@pytest.mark.parametrize("missing", [False, True])
def test_screen_and_replay_text_show_trial_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: bool
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    frozen_equities(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "scan",
            "hypotheses",
            "--symbols",
            "A,B,C,D,E,ZZZ" if missing else "A,B,C,D,E",
            "--snapshot",
            "frozen",
            "--as-of",
            "2020-04-09",
            "--signals",
            "rev_1m",
            "--horizons",
            "1,5",
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.stdout.startswith("exploratory screen ")
    assert ": 2 trials; authority none\n" in result.stdout
    scan_id = result.stdout.split()[2].removesuffix(":")
    replay = runner.invoke(app, ["scan", "replay", scan_id])
    assert replay.exit_code == 0, replay.output
    assert replay.stdout.startswith(f"replayed {scan_id}; attempt ")
    assert "; authority none\n" in replay.stdout
    for output in (result.stdout, replay.stdout):
        assert (
            "signal      h    IC mean   t (plain)  dates   spread     cost-adj   turnover/h"
            in output
        )
        rows = [line.split() for line in output.splitlines() if line.startswith("rev_1m")]
        assert len(rows) == 2
        assert {row[1] for row in rows} == {"1", "5"}
        assert all(len(row) == 8 for row in rows)
        assert (
            "plain t statistics; horizons over 1 overlap and are not corrected; "
            "no selection adjustment over 2 trials"
        ) in output
        if missing:
            assert "missing from snapshot: ZZZ" in output
        else:
            assert "missing from snapshot:" not in output


def test_text_screen_prints_unavailable_ic_as_na(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import _hypothesis_scan as scan

    frozen_equities(tmp_path)
    runner = CliRunner()
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    args = [
        "scan",
        "hypotheses",
        "--symbols",
        "A,B,C,D,E",
        "--snapshot",
        "frozen",
        "--as-of",
        "2020-04-09",
        "--signals",
        "rev_1m",
        "--horizons",
        "1",
    ]
    result = runner.invoke(app, [*args, "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    payload["results"][0]["ic"].update(mean=None, t_stat=None)
    monkeypatch.setattr(scan, "run_hypotheses", lambda *_: payload)
    text = runner.invoke(app, args)
    assert text.exit_code == 0, text.output
    row = next((line.split() for line in text.stdout.splitlines() if line.startswith("rev_1m")), [])
    assert row[2:4] == ["n/a", "n/a"]


def test_frozen_screen_cli_and_replay(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    frozen_equities(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "scan",
            "hypotheses",
            "--symbols",
            "E,D,C,B,A",
            "--snapshot",
            "frozen",
            "--as-of",
            "2020-04-09",
            "--signals",
            "rev_1m",
            "--horizons",
            "1,5",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["authority"] == "none" and payload["trials"] == 2
    replay = runner.invoke(app, ["scan", "replay", payload["scan_id"], "--json"])
    assert replay.exit_code == 0, replay.output
    assert json.loads(replay.stdout)["result_digest"] == payload["result_digest"]
    assert not (tmp_path / "control").exists()
    assert not (tmp_path / "runs").exists()


def test_live_equity_screen_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    result = CliRunner().invoke(
        app, ["scan", "hypotheses", "--symbols", "A,B,C", "--as-of", "2020-04-09"]
    )
    assert result.exit_code == 2 and "snapshot" in result.output
    assert len(list((tmp_path / "scans" / "hypotheses" / "attempts").glob("*/finished.json"))) == 1


def test_crypto_screen_replay_ignores_new_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import _crypto_panel

    store = frozen_crypto(tmp_path)
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(_crypto_panel, "bulk_store", lambda _: store)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "scan",
            "hypotheses",
            "--lane",
            "crypto",
            "--symbols",
            "AAAUSDT,BBBUSDT,CCCUSDT",
            "--as-of",
            "2020-03-01",
            "--horizons",
            "1,5",
            "--min-names",
            "3",
            "--quantiles",
            "3",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["trials"] == 6
    monkeypatch.setattr(
        store, "inventory", lambda: (_ for _ in ()).throw(AssertionError("live inventory read"))
    )
    replay = runner.invoke(app, ["scan", "replay", payload["scan_id"], "--json"])
    assert replay.exit_code == 0, replay.output
    assert json.loads(replay.stdout)["result_digest"] == payload["result_digest"]
