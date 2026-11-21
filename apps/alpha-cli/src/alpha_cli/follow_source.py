"""What a follow is made from: a stored rule test or setup find. Read-only. Paper only.

Also records the hash of the newest stored bar of each asset. Forward use reads the newest bars
on purpose, as `alpha scan check` does; a research command never takes this path.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from alpha_cli.spine.errors import SpineError
from alpha_cli.spine.spec import IdeaSpec
from alpha_core import Bar, DataError
from alpha_data.sessions import CalendarRangeError, supported_range


def refuse(code: str, message: str, next_step: str) -> SpineError:
    return SpineError(code, message, next_step)


class Source:
    """What a follow is made from: read from the stored test or find, never changed."""

    def __init__(self, kind: str, source_id: str, spec: str, card: str, assets: list[str]) -> None:
        self.kind, self.source_id, self.spec, self.card, self.assets = (
            kind,
            source_id,
            spec,
            card,
            assets,
        )


def _manifest(path: Path, what: str, source_id: str) -> dict[str, Any]:
    try:
        raw = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise refuse(
            "FOLLOW_SOURCE_UNKNOWN",
            f"There is no {what} with the id {source_id!r}.",
            f"Run `alpha {'test' if what == 'rule test' else 'setup find'}` first.",
        ) from exc
    return raw if isinstance(raw, dict) else {}


def rule_test_source(home: Path, run_id: str) -> Source:
    from alpha_cli.run_store import find_run_dir

    folder = find_run_dir(home, run_id)
    manifest = _manifest(folder, "rule test", run_id) if folder else {}
    spine = manifest.get("spine")
    symbol = manifest.get("metadata", {}).get("symbol")
    if not isinstance(spine, dict) or not symbol or not spine.get("spec_sha256"):
        raise refuse(
            "FOLLOW_SOURCE_UNKNOWN",
            f"There is no rule test with the run id {run_id!r}.",
            "Use the run id that `alpha test` printed.",
        )
    store = spine.get("store", "home")
    asset = symbol if store == "home" else f"{symbol}@{store}"
    return Source("rule_test", run_id, spine["spec_sha256"], spine.get("idea_card", ""), [asset])


def setup_find_source(home: Path, find_id: str) -> Source:
    manifest = _manifest(home / "setups" / find_id, "setup find", find_id)
    rows = manifest.get("assets")
    assets = [r["asset"] for r in rows if r.get("error") is None] if isinstance(rows, list) else []
    if not assets or not manifest.get("spec_sha256"):
        raise refuse(
            "FOLLOW_SOURCE_UNKNOWN",
            f"There is no setup find with the id {find_id!r}, or it found no asset.",
            "Use the find id that `alpha setup find` printed.",
        )
    return Source(
        "setup_find", find_id, manifest["spec_sha256"], manifest.get("idea_card", ""), assets
    )


def rule_words(rule: object) -> str:
    """A frozen rule in plain words, such as `50/200-day average cross`. Empty when unknown."""
    if not isinstance(rule, dict) or not isinstance(rule.get("kind"), str):
        return ""
    if rule["kind"] == "ma_cross" and {"fast", "slow"} <= rule.keys():
        return f"{rule['fast']}/{rule['slow']}-day average cross"
    params = ", ".join(
        f"{k.replace('_', ' ')} {v}"
        for k, v in sorted(rule.items())
        if k != "kind" and isinstance(v, (int, float, str)) and not isinstance(v, bool)
    )
    kind = rule["kind"].replace("_", " ")
    return f"{kind} rule ({params})" if params else f"{kind} rule"


def source_name(home: Path, kind: str, source_id: str) -> str:
    """A followed test or find in plain words, with its id in brackets. The id alone when the
    stored files cannot say more. A test shows its frozen rule and parameters."""
    try:
        if kind == "rule_test":
            from alpha_cli.run_store import find_run_dir

            folder = find_run_dir(home, source_id)
            raw = json.loads((folder / "spec.json").read_text(encoding="utf-8")) if folder else {}
        else:
            raw = json.loads((home / "setups" / source_id / "manifest.json").read_text("utf-8"))
    except (OSError, ValueError):
        raw = {}
    raw = raw if isinstance(raw, dict) else {}
    name = rule_words(raw.get("rule")) or str(raw.get("name") or "").strip()
    return f"{name} [{source_id}]" if name else source_id


def latest_bar_hashes(home: Path, assets: list[str]) -> dict[str, str]:
    """The hash of the newest stored bar of each asset. Forward use reads the newest bars on
    purpose, as `alpha scan check` does; a research command never takes this path."""
    from alpha_cli._runner import load_bars, source_fingerprint
    from alpha_cli.spine.stores import resolve_asset

    hashes: dict[str, str] = {}
    for asset in assets:
        try:
            resolved = resolve_asset(asset, data_dir=home)
            bars, _ = load_bars(resolved.symbol, data_dir=resolved.data_dir)
        except DataError as exc:
            raise refuse(
                "FOLLOW_NO_BARS",
                f"Cannot read stored bars for {asset}: {exc}",
                "Store bars for the asset first, then start the follow.",
            ) from exc
        hashes[asset] = source_fingerprint([bars[-1]])
    return hashes


def frozen_idea(home: Path, source_id: str, spec_sha256: str) -> IdeaSpec:
    """The stored spec of a followed rule test. Refused unless it still has the frozen hash."""
    from alpha_cli.run_store import find_run_dir

    folder = find_run_dir(home, source_id)
    raw: dict[str, Any] = {}
    idea: IdeaSpec | None = None
    found = ""
    try:
        if folder is None:
            raise ValueError("the run folder is gone")
        raw = json.loads((folder / "spec.json").read_text(encoding="utf-8"))
        idea = IdeaSpec.model_validate({k: v for k, v in raw.items() if k != "spec_sha256"})
        found = idea.spec_sha256
    except (OSError, ValueError, TypeError) as exc:
        found = f"unreadable ({type(exc).__name__})"
    if idea is None or found != spec_sha256 or raw.get("spec_sha256") != spec_sha256:
        raise refuse(
            "FOLLOW_SPEC_CHANGED",
            f"The stored spec of rule test {source_id} no longer matches the frozen hash "
            f"{spec_sha256[:12]}. Its source changed or is gone.",
            "Do not edit stored runs. Start a new follow from a rule test that still verifies.",
        )
    if idea.costs_class_default:
        raise refuse(
            "FOLLOW_COSTS_BY_CLASS",
            f"Rule test {source_id} takes its costs from the asset class. A follow needs costs "
            "stated in the spec.",
            "Test the rule again with costs stated, then follow that test.",
        )
    return idea


def forward_bars(home: Path, asset: str, now: datetime) -> tuple[list[Bar], str | None]:
    """The stored bars of `asset` known at `now`, and the market calendar (None: trades daily).

    Forward use reads up to the clock on purpose, as `follow start` does. A bar counts only once
    it has closed: `as_of=now` plus an explicit `bar_known_at` check. A research command never
    takes this path, and no research cut-off helper is changed.
    """
    from alpha_cli import _runner
    from alpha_cli.spine.stores import resolve_asset
    from alpha_data.sessions import bar_known_at
    from alpha_data.timeframe import DAILY

    resolved = resolve_asset(asset, data_dir=home)
    try:
        bars, _ = _runner.load_bars(resolved.symbol, data_dir=resolved.data_dir, as_of=now)
    except DataError as exc:
        raise refuse(
            "FOLLOW_NO_BARS",
            f"Cannot read stored bars for {asset}: {exc}",
            "Store bars for the asset first.",
        ) from exc
    calendar = market_calendar(home, asset) or None
    with calendar_guard(calendar):
        known = [b for b in bars if bar_known_at(b.ts, timeframe=DAILY, calendar=calendar) <= now]
    return known, calendar


@contextmanager
def calendar_guard(calendar: str | None) -> Iterator[None]:
    """Turn a lookup after the calendar's last session into a plain-words refusal."""
    try:
        yield
    except CalendarRangeError as exc:
        if calendar is None:
            raise
        first, last = supported_range(calendar)
        raise refuse(
            "FOLLOW_CALENDAR_RANGE",
            f"the market calendar {calendar} cannot answer: {exc}; "
            f"supported range {first} to {last}",
            "Follow a market the calendar covers, or update the exchange-calendars library.",
        ) from exc


def market_calendar(home: Path, asset: str) -> str:
    """The exchange calendar of the stored daily bars of `asset`; "" for a market that trades
    every day. `follow start` seals it in the start entry: only that sets the journal deadlines."""
    from alpha_cli import _runner
    from alpha_cli.spine.stores import resolve_asset
    from alpha_data.timeframe import DAILY

    resolved = resolve_asset(asset, data_dir=home)
    try:
        found = _runner._bar_store(
            resolved.symbol,
            data_dir=resolved.data_dir,
            snapshot_id=None,
            stored=DAILY,
            session=None,
        )[1]
    except DataError as exc:
        raise refuse(
            "FOLLOW_NO_BARS",
            f"Cannot read stored bars for {asset}: {exc}",
            "Store bars for the asset first.",
        ) from exc
    return str(found or "")
