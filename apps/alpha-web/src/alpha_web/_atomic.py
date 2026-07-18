"""Package-local atomic file publication helpers."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from pathlib import Path


def publish(path: Path, writer: Callable[[Path], object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    tmp = Path(raw_tmp)
    try:
        writer(tmp)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def write_text(path: Path, content: str) -> None:
    publish(path, lambda tmp: tmp.write_text(content, encoding="utf-8"))
