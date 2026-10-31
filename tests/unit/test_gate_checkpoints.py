"""Non-destructive retention uses verified evidence, never age alone."""

import hashlib
import json
import os
import tarfile
from pathlib import Path

import gate
import gate_checkpoints
import gate_components
import pytest

from tests.unit._harness_support import git


def checkpoint(root: Path, value: str, age: int) -> Path:
    payload = json.dumps({"tree_hash": value * 64, "head": value * 40}).encode()
    name = ".alpha/state/gate-stamp.json"
    manifest = f"{name}\t{len(payload)}\t{hashlib.sha256(payload).hexdigest()}\n"
    digest = hashlib.sha256(manifest.encode()).hexdigest()[:16]
    folder = root / gate_components.CHECKPOINT_DIR / f"pre-run-{digest}"
    (folder / name).parent.mkdir(parents=True)
    (folder / name).write_bytes(payload)
    (folder / "MANIFEST.tsv").write_text(manifest)
    os.utime(folder, (age, age))
    return folder


def test_dry_run_excludes_latest_current_and_incomplete_without_writes(repo: Path) -> None:
    current = checkpoint(repo, "a", 1)
    old = checkpoint(repo, "b", 2)
    latest = checkpoint(repo, "c", 3)
    state = repo / gate.STATE_DIR
    (state / gate.STAMP_FILE).write_bytes((current / gate.STATE_DIR / gate.STAMP_FILE).read_bytes())
    incomplete = repo / gate_components.CHECKPOINT_DIR / ".incomplete-preserved"
    incomplete.mkdir()
    (incomplete / "owner-data").write_text("do not inspect or archive")
    before = sorted(str(p) for p in repo.rglob("*"))
    report = gate_checkpoints.inventory(repo, keep=1)
    rows = {row["name"]: row for row in report["checkpoints"]}
    assert rows[current.name]["disposition"] == "keep-current"
    assert rows[latest.name]["disposition"] == "keep-recent"
    assert rows[old.name]["disposition"] == "archive-candidate"
    assert rows[old.name]["recorded_identities"] == [{"head": "b" * 40, "tree_hash": "b" * 64}]
    assert rows[incomplete.name]["disposition"] == "excluded-incomplete"
    assert sorted(str(p) for p in repo.rglob("*")) == before


def test_archive_round_trip_and_idempotency_never_removes_source(repo: Path) -> None:
    folder = checkpoint(repo, "a", 1)
    before = {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    report = gate_checkpoints.inventory(repo, keep=0, archive=True)
    row = report["checkpoints"][0]
    assert row["disposition"] == "archived-source-retained"
    archive = repo / row["archive"]
    with tarfile.open(archive) as saved:
        restored = {}
        for member in saved.getmembers():
            stream = saved.extractfile(member)
            assert stream is not None
            restored[member.name] = stream.read()
    assert restored == before
    assert {
        str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob("*") if p.is_file()
    } == before
    first = archive.stat().st_mtime_ns
    gate_checkpoints.inventory(repo, keep=0, archive=True)
    assert archive.stat().st_mtime_ns == first
    archive.write_bytes(b"corrupt")
    with pytest.raises((OSError, ValueError, tarfile.TarError)):
        gate_checkpoints.inventory(repo, keep=0, archive=True)
    assert folder.exists()


@pytest.mark.parametrize("fault", ["traversal", "secret", "symlink", "tamper", "extra", "name"])
def test_untrusted_checkpoint_is_excluded_without_archiving(repo: Path, fault: str) -> None:
    folder = checkpoint(repo, "a", 1)
    manifest = folder / "MANIFEST.tsv"
    stamp = folder / gate.STATE_DIR / gate.STAMP_FILE
    if fault in {"traversal", "secret"}:
        manifest.write_text(f"{'../outside' if fault == 'traversal' else '.env'}\t1\t{'0' * 64}\n")
    elif fault == "symlink":
        stamp.unlink()
        stamp.symlink_to(repo / "outside")
    elif fault == "tamper":
        stamp.write_text("changed")
    elif fault == "extra":
        (folder / "unexpected").write_text("private")
    else:
        folder.rename(folder.with_name("pre-run-" + "0" * 16))
    assert (
        gate_checkpoints.inventory(repo, keep=0, archive=True)["checkpoints"][0]["disposition"]
        == "excluded-invalid"
    )
    assert not (repo / gate_checkpoints.ARCHIVE_DIR).exists()


def test_symlinked_checkpoint_root_is_not_followed(repo: Path, tmp_path: Path) -> None:
    target = tmp_path / "external"
    target.mkdir()
    root = repo / gate_components.CHECKPOINT_DIR
    root.parent.mkdir(parents=True)
    root.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        gate_checkpoints.inventory(repo)
    assert list(target.iterdir()) == []


def test_cli_defaults_to_inventory_and_rejects_negative_retention(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    checkpoint(repo, "a", 1)
    monkeypatch.setattr(gate, "repo_root", lambda: repo)
    assert gate.main(["checkpoints", "--keep", "0"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["head"] == git(repo, "rev-parse", "HEAD")
    assert result["mode"] == "dry-run"
    assert not (repo / gate_checkpoints.ARCHIVE_DIR).exists()
    assert gate.main(["checkpoints", "--keep", "-1"]) == 1


def test_archive_root_symlink_never_writes_outside(repo: Path, tmp_path: Path) -> None:
    checkpoint(repo, "a", 1)
    external = tmp_path / "external"
    external.mkdir()
    (repo / gate_checkpoints.ARCHIVE_DIR).symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        gate_checkpoints.inventory(repo, keep=0, archive=True)
    assert list(external.iterdir()) == []


def test_changed_source_during_archive_keeps_partial_and_original(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = checkpoint(repo, "a", 1)
    original = gate_checkpoints._archive_matches

    def changed(path: Path, manifest: str) -> bool:
        valid = original(path, manifest)
        (folder / gate.STATE_DIR / gate.STAMP_FILE).write_bytes(b"changed during copy")
        return valid

    monkeypatch.setattr(gate_checkpoints, "_archive_matches", changed)
    with pytest.raises(ValueError):
        gate_checkpoints.inventory(repo, keep=0, archive=True)
    archives = repo / gate_checkpoints.ARCHIVE_DIR
    assert not list(archives.glob("*.tar.gz"))
    assert len(list(archives.glob(".incomplete-*"))) == 1
    assert (folder / gate.STATE_DIR / gate.STAMP_FILE).read_bytes() == b"changed during copy"


def test_symlink_and_unknown_entries_are_not_examined(repo: Path, tmp_path: Path) -> None:
    base = repo / gate_components.CHECKPOINT_DIR
    base.mkdir(parents=True)
    target = tmp_path / "external"
    target.mkdir()
    (target / "MANIFEST.tsv").write_text("must not open")
    (base / ("pre-run-" + "f" * 16)).symlink_to(target, target_is_directory=True)
    (base / "unexpected").mkdir()
    report = gate_checkpoints.inventory(repo, keep=0, archive=True)
    assert all(row["disposition"] == "excluded-invalid" for row in report["checkpoints"])
    assert not (repo / gate_checkpoints.ARCHIVE_DIR).exists()


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="requires POSIX FIFO support")
@pytest.mark.parametrize("location", ["manifest", "archive"])
def test_special_evidence_files_fail_promptly_without_deletion(repo: Path, location: str) -> None:
    import subprocess
    import sys

    folder = checkpoint(repo, "a", 1)
    if location == "manifest":
        target = folder / "MANIFEST.tsv"
        target.unlink()
    else:
        target = repo / gate_checkpoints.ARCHIVE_DIR / f"{folder.name}.tar.gz"
        target.parent.mkdir(parents=True)
    os.mkfifo(target)
    result = subprocess.run(
        [sys.executable, str(Path(gate.__file__)), "checkpoints", "--archive", "--keep", "0"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=3,
        check=False,
    )
    if location == "manifest":
        assert result.returncode == 0
        assert json.loads(result.stdout)["checkpoints"][0]["disposition"] == "excluded-invalid"
    else:
        assert result.returncode == 1
        assert "regular file" in result.stderr
    assert target.exists() and folder.exists()


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="requires POSIX FIFO support")
def test_unknown_fifo_is_not_silently_omitted_from_checkpoint(repo: Path) -> None:
    folder = checkpoint(repo, "a", 1)
    os.mkfifo(folder / "unexpected")
    report = gate_checkpoints.inventory(repo, keep=0, archive=True)
    assert report["checkpoints"][0]["disposition"] == "excluded-invalid"
    assert not (repo / gate_checkpoints.ARCHIVE_DIR).exists()
    assert (folder / "unexpected").exists()


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="requires POSIX FIFO support")
def test_archive_never_reopens_payload_path_after_metadata(repo: Path) -> None:
    import subprocess
    import sys

    folder = checkpoint(repo, "a", 1)
    payload = folder / gate.STATE_DIR / gate.STAMP_FILE
    original = payload.read_bytes()
    code = (
        "import os,sys,tarfile\n"
        f"sys.path.insert(0, {str(Path(gate.__file__).parent)!r})\n"
        "from pathlib import Path\nimport gate\n"
        "original=tarfile.TarFile.gettarinfo\n"
        "def swapped(self,*args,**kwargs):\n"
        " info=original(self,*args,**kwargs)\n"
        " if info.name=='.alpha/state/gate-stamp.json':\n"
        f"  path=Path({str(payload)!r});path.unlink();os.mkfifo(path)\n"
        " return info\n"
        "tarfile.TarFile.gettarinfo=swapped\n"
        "raise SystemExit(gate.main(['checkpoints','--archive','--keep','0']))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=3,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["checkpoints"][0]["disposition"] == "archived-source-retained"
    assert payload.read_bytes() == original
