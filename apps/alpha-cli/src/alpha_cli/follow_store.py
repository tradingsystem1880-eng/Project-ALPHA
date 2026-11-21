"""The follow store: `<data_dir>/forward/<follow_id>/follow.toml` and its journal. Paper only.

A follow is frozen when it starts. Changing a followed idea is never an edit: it makes a new
version that names the old follow, and the old follow gets a `stop` entry. This module computes
no signal and simulates no trade. It reads one bar per asset, only to record that bar's hash.
Only the modules on the allow-list in `tests/unit/test_follow_separation.py` may import it.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import tomllib
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from alpha_cli.follow_chain import append_entry, read_entries, verify_journal
from alpha_cli.follow_journal import CALENDAR_KEY, Clock, Entry, JournalRefusal
from alpha_cli.follow_source import Source, latest_bar_hashes, market_calendar, refuse
from alpha_cli.spine import idea_card
from alpha_cli.spine.errors import SpineError

FOLLOW_DIR = "forward"
RECORD_FILE = "follow.toml"
SCHEMA = "AlphaFollowV1"
ID_LENGTH = 12
DEFAULT_SIZE_PCT = 10.0
KINDS = {"rule_test": "rule test", "setup_find": "setup find", "setup_trade": "setup trade"}
WAITING = "waiting for its first new bar"
PAPER = "This is a paper follow. It places no order and is not advice."


class FollowRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    schema_: str = Field(default=SCHEMA, alias="schema")
    follow_id: str
    kind: str
    source_id: str
    spec_sha256: str
    card_id: str = ""
    assets: list[str] = Field(min_length=1)
    paper_account_percent: float = Field(gt=0, le=100)
    started_at: datetime
    version: int = Field(ge=1)
    supersedes: str = ""

    @field_validator("started_at")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("started_at must be an aware UTC time")
        return value.astimezone(UTC)

    def body(self) -> dict[str, Any]:
        return dict(self.model_dump(mode="json", by_alias=True))


def _follow_id(body: dict[str, Any]) -> str:
    text = json.dumps({k: v for k, v in body.items() if k != "follow_id"}, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:ID_LENGTH]


def _toml(record: FollowRecord) -> str:
    return "".join(f"{k} = {json.dumps(v, ensure_ascii=False)}\n" for k, v in record.body().items())


def _root(home: Path) -> Path:
    return home / FOLLOW_DIR


def folder_of(home: Path, follow_id: str) -> Path:
    return _root(home) / follow_id


def load_record(folder: Path) -> FollowRecord:
    try:
        record = FollowRecord.model_validate(
            tomllib.loads((folder / RECORD_FILE).read_text(encoding="utf-8"))
        )
    except (OSError, ValueError) as exc:
        raise refuse(
            "FOLLOW_RECORD_UNREADABLE",
            f"The follow record in {folder.name} cannot be read: {exc}",
            "Do not edit follow files. Start a new follow.",
        ) from exc
    if _follow_id(record.body()) != record.follow_id or folder.name != record.follow_id:
        raise refuse(
            "FOLLOW_RECORD_CHANGED",
            f"The follow record {folder.name} no longer matches its id.",
            "Do not edit follow files. Start a new follow.",
        )
    return record


def all_ids(home: Path) -> list[str]:
    return sorted(p.name for p in _root(home).glob("*") if (p / RECORD_FILE).is_file())


def resolve(home: Path, wanted: str) -> str:
    """A full follow id or a unique prefix of at least four characters."""
    wanted = wanted.strip().lower()
    found = [
        i for i in all_ids(home) if re.fullmatch(r"[0-9a-f]{4,12}", wanted) and i.startswith(wanted)
    ]
    if len(found) != 1:
        raise refuse(
            "FOLLOW_AMBIGUOUS" if found else "FOLLOW_UNKNOWN",
            f"More than one follow starts with {wanted!r}."
            if found
            else f"There is no follow with the id {wanted!r}.",
            "Run `alpha follow list` to see the follows.",
        )
    return found[0]


def entries_of(home: Path, follow_id: str) -> list[Entry]:
    return read_entries(folder_of(home, follow_id), follow_id)


def state_of(entries: list[Entry]) -> str:
    if entries and entries[-1].kind == "stop":
        return "stopped"
    return "waiting" if len(entries) <= 1 else "active"


def _write_record(folder: Path, record: FollowRecord) -> None:
    folder.mkdir(parents=True, exist_ok=False)
    staged = folder / f"{RECORD_FILE}.{os.getpid()}.part"
    staged.write_text(_toml(record), encoding="utf-8")
    os.replace(staged, folder / RECORD_FILE)


def _same(record: FollowRecord, source: Source, pct: float) -> bool:
    return (record.kind, record.source_id, record.spec_sha256, record.assets) == (
        source.kind,
        source.source_id,
        source.spec,
        source.assets,
    ) and record.paper_account_percent == pct


def _same_idea(record: FollowRecord, source: Source, card: str) -> bool:
    """One idea: the same idea card, or with no card the same test or find."""
    if card:
        return record.card_id == card
    return not record.card_id and (record.kind, record.source_id) == (source.kind, source.source_id)


def _lineage(home: Path, source: Source, card: str) -> list[tuple[FollowRecord, str]]:
    found = [
        (load_record(folder_of(home, i)), state_of(entries_of(home, i))) for i in all_ids(home)
    ]
    return sorted(
        [(r, s) for r, s in found if _same_idea(r, source, card)],
        key=lambda x: (x[0].version, x[0].started_at),
    )


@contextmanager
def _start_lock(home: Path) -> Iterator[None]:
    """One start at a time, so two starts of one spec cannot make two follows."""
    _root(home).mkdir(parents=True, exist_ok=True)
    with (_root(home) / ".start.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def start_follow(
    home: Path, source: Source, *, card: str, size_pct: float, clock: Clock
) -> dict[str, Any]:
    """Freeze a follow and write its start entry. Writes only under `forward/`. No ledger row."""
    card_id = idea_card.resolve(home, card or source.card) if (card or source.card) else ""
    with _start_lock(home):
        return _start_locked(home, source, card_id, size_pct, clock)


def _start_locked(
    home: Path, source: Source, card_id: str, size_pct: float, clock: Clock
) -> dict[str, Any]:
    related = _lineage(home, source, card_id)
    active = [r for r, s in related if s != "stopped"]
    for record, state in ((r, s) for r, s in related if s != "stopped"):
        if _same(record, source, size_pct):
            return {**_facts(record, state), "created": False, "replaced": ""}
    hashes = latest_bar_hashes(home, source.assets)
    now = clock()
    previous = related[-1][0] if related else None
    body = {
        "schema": SCHEMA,
        "follow_id": "",
        "kind": source.kind,
        "source_id": source.source_id,
        "spec_sha256": source.spec,
        "card_id": card_id,
        "assets": source.assets,
        "paper_account_percent": size_pct,
        "started_at": now.astimezone(UTC).isoformat(),
        "version": previous.version + 1 if previous else 1,
        "supersedes": previous.follow_id if previous else "",
    }
    draft = FollowRecord.model_validate(body)
    record = draft.model_copy(update={"follow_id": _follow_id(draft.body())})
    folder = folder_of(home, record.follow_id)
    _write_record(folder, record)
    payload = {"source_id": source.source_id, "kind": source.kind, "version": record.version}
    payload[CALENDAR_KEY] = market_calendar(home, source.assets[0])
    if source.study is not None:
        payload["setup"] = source.study
    append_entry(
        folder,
        kind="start",
        session_date=record.started_at.date(),
        clock=lambda: record.started_at,
        bar_hashes=hashes,
        payload={**payload, "follow_id": record.follow_id, "paper": True},
        follow_id=record.follow_id,
    )
    replaced = ""
    for old in active:
        stop_follow(
            home, old.follow_id, reason=f"replaced by version {record.version}", clock=clock
        )
        replaced = old.follow_id
    return {**_facts(record, "waiting"), "created": True, "replaced": replaced}


def stop_follow(home: Path, follow_id: str, *, reason: str, clock: Clock) -> Entry:
    folder = folder_of(home, follow_id)
    load_record(folder)
    now = clock()
    return append_entry(
        folder,
        kind="stop",
        session_date=now.date(),
        clock=lambda: now,
        payload={"reason": reason},
        follow_id=follow_id,
    )


def _facts(record: FollowRecord, state: str) -> dict[str, Any]:
    return {**record.body(), "state": state}


def show_facts(home: Path, follow_id: str) -> dict[str, Any]:
    folder = folder_of(home, follow_id)
    record = load_record(folder)
    entries = entries_of(home, follow_id)
    state = state_of(entries)
    return {
        "record": record.body(),
        "state": state,
        "entries": dict(Counter(e.kind for e in entries)),
        "head": entries[-1].entry_hash,
        "waiting_for_first_bar": state == "waiting",
        "stop_reason": entries[-1].payload.get("reason", "") if state == "stopped" else "",
        "path": str(folder),
    }


def list_facts(home: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for follow_id in all_ids(home):
        try:
            record = load_record(folder_of(home, follow_id))
            state = state_of(entries_of(home, follow_id))
        except (SpineError, JournalRefusal):
            rows.append({"follow_id": follow_id, "state": "broken"})
            continue
        rows.append(_facts(record, state))
    return rows


def journal_report(home: Path, follow_id: str, *, now: datetime) -> Any:
    load_record(folder_of(home, follow_id))
    return verify_journal(folder_of(home, follow_id), follow_id=follow_id, now=now)
