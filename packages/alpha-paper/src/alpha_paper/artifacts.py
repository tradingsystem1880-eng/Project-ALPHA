"""On-disk layout for a paper-trading session: ``data_dir/paper/<session_id>/``.

Unlike the backtest's byte-stable manifest, a live session is wall-clock-driven and therefore NOT
reproducible — so the integrity artifacts here are **append-only provenance + a structured audit
log**, not a hash target:

- ``session.json``     — start time, resolved ``PaperSpec``, exchange/symbol, library versions.
- ``audit.log.jsonl``  — one JSON object per line: each decision / order / fill / reconnect / error.
- ``equity_curve.parquet`` — per-session mark-to-market equity (``(ts, equity)``).

Secrets (API keys) are never written here. The fills/positions/reconciliation parquet land in 4e,
once the live node actually produces them.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_hex
from typing import Any

import polars as pl

from alpha_paper.errors import PaperError


def new_session_id(now: datetime | None = None, suffix: str | None = None) -> str:
    """A wall-clock-stamped, collision-resistant session id: ``YYYYMMDDTHHMMSSZ-<8hex>``.

    ``now``/``suffix`` are injectable for deterministic tests; live runs use UTC now + random hex.
    """
    when = now if now is not None else datetime.now(UTC)
    tag = suffix if suffix is not None else token_hex(4)
    return f"{when.strftime('%Y%m%dT%H%M%SZ')}-{tag}"


def session_dir(data_dir: Path, session_id: str) -> Path:
    """The artifact directory for a paper session: ``data_dir/paper/<session_id>``."""
    return data_dir / "paper" / session_id


def write_session(sdir: Path, session: dict[str, Any]) -> None:
    """Write append-only provenance to ``session.json`` (human-readable, NOT a byte-stable hash).

    Fails loud if a key looks credential-like, so a secret can never silently leak into an artifact.
    """
    for key in session:
        if "api_key" in key.lower() or "secret" in key.lower():
            raise PaperError(f"refusing to write credential-like field {key!r} into session.json")
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "session.json").write_text(json.dumps(session, indent=2), encoding="utf-8")


def read_session(sdir: Path) -> dict[str, Any]:
    """Load a session's ``session.json`` back into a dict."""
    result: dict[str, Any] = json.loads((sdir / "session.json").read_text(encoding="utf-8"))
    return result


class AuditLog:
    """Append-only, flush-per-record JSON-lines audit trail (``audit.log.jsonl``).

    Each ``record`` is one line: ``{"ts": <iso8601>, "event": <name>, ...fields}``. Opened in append
    mode per write so the trail survives a crash mid-session. The clock is injectable for tests.
    """

    def __init__(self, sdir: Path, *, clock: Callable[[], datetime] | None = None) -> None:
        sdir.mkdir(parents=True, exist_ok=True)
        self._path = sdir / "audit.log.jsonl"
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)

    @property
    def path(self) -> Path:
        return self._path

    def record(self, event: str, **fields: Any) -> None:
        """Append one ``event`` (with arbitrary JSON-serializable ``fields``) to the trail."""
        entry = {"ts": self._clock().isoformat(), "event": event, **fields}
        line = json.dumps(entry, sort_keys=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def read(self) -> list[dict[str, Any]]:
        """Read the trail back as a list of records (empty if nothing has been logged)."""
        if not self._path.exists():
            return []
        return [
            json.loads(line)
            for line in self._path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]


def write_equity_curve(sdir: Path, equity: Sequence[tuple[datetime, float]]) -> None:
    """Write the per-session mark-to-market equity curve to ``equity_curve.parquet``."""
    sdir.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"ts": [ts for ts, _ in equity], "equity": [v for _, v in equity]}).write_parquet(
        sdir / "equity_curve.parquet"
    )
