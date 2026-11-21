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
from alpha_core import Bar, CorporateAction, DataError
from alpha_data.sessions import CalendarRangeError, supported_range


def refuse(code: str, message: str, next_step: str) -> SpineError:
    return SpineError(code, message, next_step)


class Source:
    """What a follow is made from: read from the stored test or find, never changed."""

    def __init__(
        self,
        kind: str,
        source_id: str,
        spec: str,
        card: str,
        assets: list[str],
        study: dict[str, Any] | None = None,
    ) -> None:
        self.kind, self.source_id, self.spec, self.card, self.assets = (
            kind,
            source_id,
            spec,
            card,
            assets,
        )
        self.study = study  # a setup follow: the labels and ids of the study it came from


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


def _setup_trade(home: Path, trade_id: str) -> tuple[dict[str, Any], Any]:
    """The stored setup trade manifest and the find's spec it was made from."""
    from alpha_cli.spine.errors import SpineError as _Error
    from alpha_cli.spine.setup_find import load_find

    manifest = _manifest(home / "setup-trades" / trade_id, "setup trade", trade_id)
    try:
        _, _, spec = load_find(home, str(manifest.get("find_id", "")))
    except (_Error, OSError, ValueError, KeyError) as exc:
        raise refuse(
            "FOLLOW_SOURCE_UNKNOWN",
            f"The setup find of trade {trade_id!r} cannot be read: {exc}",
            "Run `alpha setup find` and `alpha setup trade` again.",
        ) from exc
    return manifest, spec


def setup_trade_source(home: Path, trade_id: str, asset: str) -> Source:
    """A Setup Lab trade study as a follow source. One asset, long only, no context series.
    It keeps the study's labels and trial identity (trade id, find id) in the start entry."""
    manifest, spec = _setup_trade(home, trade_id)
    named = [r["asset"] for r in manifest.get("assets", []) if r.get("error") is None]
    if not named or manifest.get("direction") != "long" or spec.exit is None:
        why = (
            "A short setup cannot be followed: the paper account is long only."
            if manifest.get("direction") == "short"
            else f"There is no usable setup trade with the id {trade_id!r}."
        )
        raise refuse("FOLLOW_SETUP_REFUSED", why, "Follow a long setup trade.")
    if spec.context:
        raise refuse(
            "FOLLOW_SETUP_CONTEXT",
            "A setup that reads outside series (context) cannot be followed yet.",
            "Follow a setup that reads only price bars.",
        )
    if not asset and len(named) == 1:
        asset = named[0]
    if asset not in named:
        raise refuse(
            "FOLLOW_SETUP_ASSET",
            f"Name one asset of this trade with --asset. Choices: {', '.join(named)}.",
            "Example: alpha follow start --trade <trade id> --asset " + named[0],
        )
    study = {
        "trade_id": trade_id,
        "find_id": manifest["find_id"],
        "name": spec.setup.name,
        "idea": spec.setup.idea,
        "labels": list(manifest.get("labels", [])),
        "direction": "long",
        "costs": manifest["costs"][asset],
        "exits": spec.exit.model_dump(exclude={"direction"}),
        "trade_rule_version": manifest.get("trade_rule_version", ""),
    }
    return Source("setup_trade", trade_id, manifest["spec_sha256"], "", [asset], study)


def frozen_setup(
    home: Path, source_id: str, spec_sha256: str, asset: str
) -> tuple[Any, dict[str, Any]]:
    """The stored spec and costs of a followed setup trade. Refused unless the spec still has the
    frozen hash."""
    manifest, spec = _setup_trade(home, source_id)
    if spec.spec_sha256 != spec_sha256 or manifest.get("spec_sha256") != spec_sha256:
        raise refuse(
            "FOLLOW_SPEC_CHANGED",
            f"The stored spec of setup trade {source_id} no longer matches the frozen hash "
            f"{spec_sha256[:12]}. Its source changed or is gone.",
            "Do not edit stored setups. Start a new follow from a trade that still verifies.",
        )
    return spec, dict(manifest["costs"][asset])


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
        elif kind == "setup_trade":
            raw = json.loads(
                (home / "setup-trades" / source_id / "summary.json").read_text("utf-8")
            )
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


def forward_dividends(home: Path, asset: str, now: datetime) -> list[CorporateAction]:
    """The cash dividends of `asset` knowable at `now`: the rule test's own point-in-time read
    (`load_dividends`, knowledge-gated by announce date). Forward use reads up to the clock on
    purpose, as `forward_bars` does. A research command never takes this path."""
    from alpha_cli import _runner
    from alpha_cli.spine.stores import resolve_asset

    resolved = resolve_asset(asset, data_dir=home)
    try:
        return _runner.load_dividends(resolved.symbol, data_dir=resolved.data_dir, as_of=now)
    except DataError as exc:
        raise refuse(
            "FOLLOW_NO_BARS",
            f"Cannot read stored dividends for {asset}: {exc}",
            "Store the asset's data again.",
        ) from exc


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
