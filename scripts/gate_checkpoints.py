"""Inventory and archive gate checkpoints without deleting or restoring evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tarfile
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO

import gate
from gate_components import CHECKPOINT_DIR, PRESERVED_EVIDENCE

ARCHIVE_DIR = gate.STATE_DIR / "gate-checkpoint-archives"
_ALLOWED = {path.as_posix() for path in PRESERVED_EVIDENCE}


def _no_symlinks(root: Path, path: Path) -> None:
    current = root
    for part in path.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ValueError("evidence paths must not contain symlinks")


@contextmanager
def _regular(path: Path) -> Iterator[BinaryIO]:
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("evidence must be a regular file")
        yield stream


def _manifest(directory: Path) -> str:
    """Validate the small manifest before reading only allowlisted evidence files."""
    path = directory / "MANIFEST.tsv"
    with _regular(path) as stream:
        data = stream.read(16_385)
    if len(data) > 16_384:
        raise ValueError("oversized checkpoint manifest")
    manifest = data.decode()
    names: set[str] = set()
    for line in manifest.splitlines():
        name, size, digest = line.split("\t")
        if name not in _ALLOWED or name in names or not re.fullmatch(r"[0-9]+", size):
            raise ValueError("invalid checkpoint manifest entry")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("invalid checkpoint digest")
        names.add(name)
    if not names:
        raise ValueError("empty checkpoint manifest")
    if directory.name != "pre-run-" + hashlib.sha256(manifest.encode()).hexdigest()[:16]:
        raise ValueError("checkpoint name does not match manifest")
    files = set()
    for entry in directory.rglob("*"):
        mode = entry.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError("checkpoint contains nonregular entries")
        files.add(entry.relative_to(directory).as_posix())
    if files != names | {"MANIFEST.tsv"}:
        raise ValueError("checkpoint file set does not match manifest")
    for line in manifest.splitlines():
        name, size, digest = line.split("\t")
        with _regular(directory / name) as stream:
            actual = hashlib.sha256()
            remaining = int(size)
            while remaining:
                chunk = stream.read(min(1_048_576, remaining))
                if not chunk:
                    raise ValueError("checkpoint file is truncated")
                actual.update(chunk)
                remaining -= len(chunk)
            if stream.read(1) or actual.hexdigest() != digest:
                raise ValueError("checkpoint bytes do not match manifest")
    return manifest


def _archive_matches(path: Path, manifest: str) -> bool:
    expected = {
        "MANIFEST.tsv": (len(manifest.encode()), hashlib.sha256(manifest.encode()).hexdigest())
    }
    expected.update(
        {
            name: (int(size), digest)
            for name, size, digest in (line.split("\t") for line in manifest.splitlines())
        }
    )
    try:
        with _regular(path) as source, tarfile.open(fileobj=source, mode="r:gz") as archive:
            seen: set[str] = set()
            for member in archive:
                if member.name not in expected or member.name in seen:
                    return False
                seen.add(member.name)
                size, digest = expected[member.name]
                if not member.isfile() or member.size != size:
                    return False
                stream = archive.extractfile(member)
                if stream is None:
                    return False
                actual = hashlib.sha256()
                while chunk := stream.read(1_048_576):
                    actual.update(chunk)
                if actual.hexdigest() != digest:
                    return False
            if seen != expected.keys():
                return False
    except (tarfile.TarError, EOFError):
        return False
    return True


def _archive(root: Path, directory: Path, manifest: str) -> Path:
    destination = root / ARCHIVE_DIR / f"{directory.name}.tar.gz"
    _no_symlinks(root, destination)
    if destination.exists():
        if not _archive_matches(destination, manifest):
            raise ValueError("existing checkpoint archive differs; nothing overwritten")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Failed partial archives are deliberately retained for diagnosis, never promoted.
    with tempfile.NamedTemporaryFile(
        prefix=".incomplete-", dir=destination.parent, delete=False
    ) as staging:
        temporary = Path(staging.name)
    with tarfile.open(temporary, "w:gz") as archive:
        for name in ["MANIFEST.tsv", *(line.split("\t")[0] for line in manifest.splitlines())]:
            with _regular(directory / name) as stream:
                metadata = os.fstat(stream.fileno())
                member = tarfile.TarInfo(name)
                member.size = metadata.st_size
                member.mode = stat.S_IMODE(metadata.st_mode)
                member.mtime = metadata.st_mtime
                archive.addfile(member, stream)
    if not _archive_matches(temporary, manifest) or _manifest(directory) != manifest:
        raise ValueError("archive/source changed during copy; partial archive retained")
    # Exclusive publication: an existing archive is never replaced, even by another invocation.
    os.link(temporary, destination)
    temporary.unlink()
    return destination


def inventory(root: Path, *, keep: int = 10, archive: bool = False) -> dict[str, Any]:
    """Dry-run by default. Archive old verified copies; retain every original path."""
    if keep < 0:
        raise ValueError("keep must be nonnegative")
    base = root / CHECKPOINT_DIR
    _no_symlinks(root, base)
    entries = (
        sorted(base.iterdir(), key=lambda p: (-p.lstat().st_mtime_ns, p.name))
        if base.exists()
        else []
    )
    current_rows = []
    for path in PRESERVED_EVIDENCE:
        _no_symlinks(root, root / path)
        if (root / path).is_file():
            with _regular(root / path) as stream:
                data = stream.read()
            current_rows.append(
                f"{path.as_posix()}\t{len(data)}\t{hashlib.sha256(data).hexdigest()}\n"
            )
    current_manifest = "".join(current_rows)
    result: list[dict[str, Any]] = []
    retained = 0
    for directory in entries:
        row: dict[str, Any] = {"name": directory.name}
        result.append(row)
        if directory.name.startswith(".incomplete-"):
            row["disposition"] = "excluded-incomplete"
            continue
        try:
            _no_symlinks(root, directory)
            if not directory.is_dir() or not re.fullmatch(r"pre-run-[0-9a-f]{16}", directory.name):
                raise ValueError("not a checkpoint directory")
            # Check all descendants before the existing verifier follows any file path.
            for path in directory.rglob("*"):
                _no_symlinks(directory, path)
            manifest = _manifest(directory)
        except (OSError, ValueError, UnicodeError):
            row["disposition"] = "excluded-invalid"
            continue
        row["manifest_sha256"] = hashlib.sha256(manifest.encode()).hexdigest()
        row["bytes"] = sum(int(line.split("\t")[1]) for line in manifest.splitlines())
        identities = []
        for line in manifest.splitlines():
            name = line.split("\t")[0]
            if name.endswith(".json") and name.startswith(".alpha/state/"):
                try:
                    with _regular(directory / name) as stream:
                        receipt = json.load(stream)
                except (ValueError, UnicodeError):
                    continue
                if isinstance(receipt, dict):
                    identity = {
                        key: receipt[key]
                        for key in ("head", "tree_hash")
                        if isinstance(receipt.get(key), str)
                        and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", receipt[key])
                    }
                    if identity and identity not in identities:
                        identities.append(identity)
        row["recorded_identities"] = identities
        if manifest == current_manifest:
            row["disposition"] = "keep-current"
        elif retained < keep:
            row["disposition"] = "keep-recent"
            retained += 1
        elif archive:
            saved = _archive(root, directory, manifest)
            with _regular(saved) as stream:
                archive_digest = hashlib.sha256(stream.read()).hexdigest()
            row.update(
                disposition="archived-source-retained",
                archive=saved.relative_to(root).as_posix(),
                archive_sha256=archive_digest,
            )
        else:
            row["disposition"] = "archive-candidate"
    return {
        "schema_version": 1,
        "mode": "archive" if archive else "dry-run",
        "head": gate._git(root, "rev-parse", "HEAD").strip(),
        "git_tree": gate._git(root, "rev-parse", "HEAD^{tree}").strip(),
        "worktree_changes": bool(gate._git(root, "status", "--porcelain")),
        "keep_recent": keep,
        "checkpoints": result,
        "restoration": (
            "Verify archive SHA256; extract only into a new empty directory, compare "
            "MANIFEST.tsv sizes/hashes, then reconcile explicitly. Never overwrite current "
            "receipts or reuse stale qualification."
        ),
        "deletions": 0,
    }
