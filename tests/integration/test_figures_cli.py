"""End-to-end `alpha figures`, including the invariant the whole design exists to protect."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from alpha_cli.artifact_contract import verify_manifest_artifacts
from alpha_cli.run_store import RUN_DIRS, read_manifest

_REPO = Path(__file__).resolve().parents[2]
_DATA = _REPO / "data"
_RUN = "0e68fb2f8ebfdaad"  # a stored v3 validate run

pytestmark = pytest.mark.skipif(
    not (_DATA / "runs" / _RUN / "manifest.json").is_file(),
    reason="requires the stored sample run",
)


def _alpha(*args: str, data_dir: Path) -> dict[str, object]:
    env = {**os.environ, "ALPHA_DATA_DIR": str(data_dir)}
    result = subprocess.run(
        [sys.executable, "-m", "alpha_cli.main", "figures", *args, "--json"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        cwd=_REPO,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A data dir whose runs are a copy, so a failure cannot damage the real store."""
    import shutil

    target = tmp_path / "data"
    (target / "runs").mkdir(parents=True)
    shutil.copytree(_DATA / "runs" / _RUN, target / "runs" / _RUN)
    # price_signal reads bars back through the run's frozen snapshot, so the snapshot has
    # to come along or that figure exercises its failure path instead of its real one.
    snapshot = read_manifest(target / "runs" / _RUN).get("metadata", {}).get("snapshot_id")
    source = _DATA / "snapshots" / str(snapshot)
    if snapshot and source.is_dir():
        shutil.copytree(source, target / "snapshots" / str(snapshot))
    return target


def _fingerprint(directory: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.iterdir())
        if path.is_file()
    }


def test_rendering_never_mutates_the_immutable_run_directory(workspace: Path) -> None:
    """The single most important test here.

    Figures live in a derived cache precisely so ARTIFACT_CONTRACT_VERSION can stay at 3
    and historical runs can still be drawn. If a render ever writes into a run directory,
    the manifest's declared file set no longer matches disk and the run stops verifying.
    """
    rdir = workspace / "runs" / _RUN
    before = _fingerprint(rdir)

    _alpha("render", _RUN, data_dir=workspace)

    after = _fingerprint(rdir)
    assert after == before, "rendering altered the run directory"
    verify_manifest_artifacts(rdir, read_manifest(rdir))


def test_a_figure_that_fails_at_render_time_does_not_cost_the_others(tmp_path: Path) -> None:
    """price_signal needs the snapshot; without it the other figures must still land."""
    import shutil

    target = tmp_path / "data"
    (target / "runs").mkdir(parents=True)
    shutil.copytree(_DATA / "runs" / _RUN, target / "runs" / _RUN)  # deliberately no snapshot

    payload = _alpha("render", _RUN, data_dir=target)
    assert len(payload["figures"]) >= 10  # type: ignore[arg-type]
    failures = {str(item["figure_id"]) for item in payload["failed"]}  # type: ignore[index,union-attr]
    assert "price_signal" in failures
    assert payload["failed"], "a render failure must be reported, never swallowed"


def test_the_cache_is_not_a_run_directory(workspace: Path) -> None:
    _alpha("render", _RUN, "--figure", "equity_underwater", data_dir=workspace)
    assert "figures" not in RUN_DIRS
    assert (workspace / "figures" / _RUN).is_dir()


def test_a_second_render_is_served_from_cache(workspace: Path) -> None:
    first = _alpha("render", _RUN, "--figure", "rolling_risk", data_dir=workspace)
    second = _alpha("render", _RUN, "--figure", "rolling_risk", data_dir=workspace)
    assert first["figures"][0]["cached"] is False  # type: ignore[index]
    assert second["figures"][0]["cached"] is True  # type: ignore[index]
    assert first["figures"][0]["cache_key"] == second["figures"][0]["cache_key"]  # type: ignore[index]


def test_force_rerender_asserts_byte_identity(workspace: Path) -> None:
    """`--force` is the determinism canary: a drifting renderer fails here, loudly,
    instead of silently overwriting a figure that no longer matches its own key."""
    _alpha("render", _RUN, "--figure", "qq_normal", data_dir=workspace)
    forced = _alpha("render", _RUN, "--figure", "qq_normal", "--force", data_dir=workspace)
    assert forced["figures"][0]["cached"] is False  # type: ignore[index]


def test_a_sidecar_accompanies_every_rendered_figure(workspace: Path) -> None:
    payload = _alpha("render", _RUN, "--figure", "null_distribution", data_dir=workspace)
    image = Path(str(payload["figures"][0]["path"]))  # type: ignore[index]
    sidecar = image.with_suffix(".json")
    assert sidecar.is_file()
    document = json.loads(sidecar.read_text())
    # The four teaching strings are what the UI renders beside the image; without them a
    # reader is left to guess what the chart is claiming.
    for field in ("question", "plain_language_answer", "uncertainty", "caveat", "alt_text"):
        assert document[field].strip()
    assert document["panels"]


def test_availability_reports_a_specific_reason_rather_than_a_blank(workspace: Path) -> None:
    payload = _alpha("list", "--run", _RUN, data_dir=workspace)
    items = {str(item["figure_id"]): item for item in payload["items"]}  # type: ignore[index,union-attr]
    assert items["trade_pnl"]["available"] is False
    assert items["trade_pnl"]["unavailable_reason"] == "artifact_empty:trades.parquet"
    assert items["equity_underwater"]["available"] is True


def test_clean_removes_figures_and_leaves_the_run_alone(workspace: Path) -> None:
    _alpha("render", _RUN, "--figure", "equity_underwater", data_dir=workspace)
    rdir = workspace / "runs" / _RUN
    before = _fingerprint(rdir)
    _alpha("clean", _RUN, data_dir=workspace)
    assert not (workspace / "figures" / _RUN).exists()
    assert _fingerprint(rdir) == before


def test_the_catalogue_lists_every_figure_with_its_teaching_text() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alpha_cli.main", "figures", "list", "--json"],
        capture_output=True,
        text=True,
        check=True,
        cwd=_REPO,
    )
    catalogue = json.loads(result.stdout)
    assert len(catalogue) >= 20
    for item in catalogue:
        for field in ("question", "uncertainty", "caveat", "summary"):
            assert item[field].strip(), f"{item['figure_id']} is missing {field}"


def test_figures_never_appear_as_a_launchable_command() -> None:
    """`alpha info commands` drives the Workstation's new-run form.

    `figures render` consumes a run that already exists and produces no run, so offering
    it there would invite the user to launch something that cannot start.
    """
    result = subprocess.run(
        [sys.executable, "-m", "alpha_cli.main", "info", "commands", "--json"],
        capture_output=True,
        text=True,
        check=True,
        cwd=_REPO,
    )
    ids = [str(entry["id"]) for entry in json.loads(result.stdout)]
    assert ids, "the command catalogue is empty"
    assert not [entry for entry in ids if entry.startswith("figures")]
