"""`alpha follow`: follow a tested idea forward on paper. F1: the frozen record and the journal.

No signal is computed and no trade is simulated here. No network, no model. Writes only under
`<data_dir>/forward/`, never a trial-ledger row.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

import typer

from alpha_cli import follow_show, follow_source, follow_today, follow_update
from alpha_cli import follow_store as store
from alpha_cli._cli_json import emit
from alpha_cli.follow_journal import JournalRefusal
from alpha_cli.spine import book as book_math
from alpha_cli.spine.errors import SpineError, fail
from alpha_core.config import AlphaSettings

follow_app = typer.Typer(
    help="Follow a tested idea forward on paper. Never an order, never advice."
)
JSON = Annotated[bool, typer.Option("--json", help="Print the same facts as JSON.")]


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


CLOCK = utc_now  # tests replace this; the journal never reads the wall clock itself


def _clock() -> datetime:
    return CLOCK()


def _row(f: dict[str, Any]) -> str:
    if f["state"] == "broken":
        return (
            f"  {f['follow_id']}  paper follow, broken: run `alpha follow verify {f['follow_id']}`"
        )
    state = store.WAITING if f["state"] == "waiting" else f["state"]
    return (
        f"  {f['follow_id']}  {store.KINDS[f['kind']]}  {', '.join(f['assets'])}  "
        f"version {f['version']}  {f.get('reading', state)}"
    )


def _show_text(facts: dict[str, Any]) -> str:
    r = facts["record"]
    counts = ", ".join(f"{n} {k}" for k, n in sorted(facts["entries"].items()))
    lines = [
        f"Follow {r['follow_id']} (paper), version {r['version']}",
        f"  What: {store.KINDS[r['kind']]} {r['source_id']}",
        f"  Assets: {', '.join(r['assets'])}",
        f"  Spec hash: {r['spec_sha256']}",
        f"  Idea card: {r['card_id'] or 'none linked'}",
        f"  Paper size: {r['paper_account_percent']:g}% of a paper account",
        f"  Started: {r['started_at']}",
    ]
    if r["supersedes"]:
        lines.append(f"  Replaces follow {r['supersedes']}")
    lines += [f"  Entries: {counts}", f"  Chain head: {facts['head']}"]
    lines += follow_show.text(facts)
    if facts["state"] == "stopped":
        lines.append(f"State: stopped. Reason: {facts['stop_reason'] or 'none given'}.")
    elif facts["waiting_for_first_bar"]:
        lines.append(f"State: {store.WAITING}.")
    else:
        lines.append("State: active.")
    lines.append(store.PAPER)
    return "\n".join(lines)


@follow_app.command("start")
def start(
    test: Annotated[str, typer.Option("--test", help="Run id of a rule test.")] = "",
    find: Annotated[str, typer.Option("--find", help="Find id of a setup find.")] = "",
    trade: Annotated[str, typer.Option("--trade", help="Trade id of a setup trade.")] = "",
    asset: Annotated[
        str, typer.Option("--asset", help="The asset of a setup trade to follow.")
    ] = "",
    factor: Annotated[str, typer.Option("--factor", help="Not built yet.")] = "",
    card: Annotated[
        str, typer.Option("--card", help="Idea card id (default: the test's own).")
    ] = "",
    size_pct: Annotated[
        float, typer.Option("--size-pct", help="Paper size, percent of a paper account.")
    ] = store.DEFAULT_SIZE_PCT,
    json_out: JSON = False,
) -> None:
    """Follow a tested rule or setup forward on paper. A changed spec starts a new version."""
    home = AlphaSettings().data_dir
    try:
        if sum(bool(x) for x in (test, find, trade, factor)) != 1:
            raise SpineError(
                "FOLLOW_SOURCE_NEEDED",
                "Name exactly one thing to follow: --test, --trade, --find or --factor.",
                "Example: alpha follow start --test <run id>",
            )
        if factor:
            raise SpineError(
                "FOLLOW_FACTOR_NOT_BUILT",
                "Following a factor is not built yet.",
                "Follow a rule test (--test) or a setup trade (--trade).",
            )
        if not 0 < size_pct <= 100:
            raise SpineError(
                "FOLLOW_SIZE",
                "Paper size must be above 0 and at most 100 percent.",
                "Use --size-pct.",
            )
        if test:
            source = follow_source.rule_test_source(home, test)
        elif trade:
            source = follow_source.setup_trade_source(home, trade, asset)
        else:
            source = follow_source.setup_find_source(home, find)
        facts = store.start_follow(home, source, card=card, size_pct=size_pct, clock=_clock)
    except (SpineError, JournalRefusal) as exc:
        fail(exc, json_out)
    lines = [
        f"{'Following' if facts['created'] else 'Already following'} "
        f"{store.KINDS[facts['kind']]} {facts['source_id']} on paper. "
        f"Follow id {facts['follow_id']}.",
        f"Paper size: {facts['paper_account_percent']:g}% of a paper account.",
    ]
    if facts["replaced"]:
        lines.append(
            f"This is version {facts['version']}. It replaces follow {facts['replaced']}, now "
            "stopped and kept. The forward clock restarts."
        )
    lines += [f"State: {store.WAITING}.", f"See it: alpha follow show {facts['follow_id']}"]
    emit(facts, json_out=json_out, fallback="\n".join(lines))


@follow_app.command("list")
def list_follows(json_out: JSON = False) -> None:
    """One row per follow, with its state. Paper only."""
    home = AlphaSettings().data_dir
    rows = [
        r
        if r["state"] == "broken"
        else {**r, "reading": follow_show.reading(store.entries_of(home, r["follow_id"]))}
        for r in store.list_facts(home)
    ]
    head = f"{len(rows)} idea(s) followed on paper." if rows else "No follows yet (paper)."
    tail = [] if rows else ["Start one: alpha follow start --test <run id>"]
    emit({"follows": rows}, json_out=json_out, fallback="\n".join([head, *map(_row, rows), *tail]))


@follow_app.command("show")
def show(
    follow_id: Annotated[str, typer.Argument(help="Follow id or prefix.")],
    all_entries: Annotated[bool, typer.Option("--all", help="Show every entry.")] = False,
    last: Annotated[
        int, typer.Option("--last", help="Show the newest N entries.")
    ] = follow_show.RECENT,
    json_out: JSON = False,
) -> None:
    """The frozen record, the entries by kind and the chain head. The newest 20 entries."""
    home = AlphaSettings().data_dir
    try:
        if last < 1:
            raise SpineError(
                "FOLLOW_SHOW_LAST", "--last needs a number of 1 or more.", "Use --last 20."
            )
        identity = store.resolve(home, follow_id)
        facts = {
            **store.show_facts(home, identity),
            **follow_show.extra(store.entries_of(home, identity), None if all_entries else last),
        }
    except (SpineError, JournalRefusal) as exc:
        fail(exc, json_out)
    emit(facts, json_out=json_out, fallback=_show_text(facts))


@follow_app.command("verify")
def verify(
    follow_id: Annotated[str, typer.Argument(help="Follow id or prefix.")],
    entry: Annotated[
        int, typer.Option("--entry", help="Also print the hash of this entry number.")
    ] = 0,
    json_out: JSON = False,
) -> None:
    """Recompute the hash chain. Exit 1 at the first break."""
    home = AlphaSettings().data_dir
    try:
        identity = store.resolve(home, follow_id)
        report = store.journal_report(home, identity, now=_clock())
    except (SpineError, JournalRefusal) as exc:
        fail(exc, json_out)
    broken = report.first_break
    facts = {
        "follow_id": identity,
        "ok": broken is None,
        "entries": report.entries,
        "head": report.head,
        "first_break": None if broken is None else broken._asdict(),
    }
    if entry and broken is None:
        found = store.entries_of(home, identity)
        facts["at_entry"] = {
            "seq": entry,
            "entry_hash": found[entry - 1].entry_hash if 0 < entry <= len(found) else None,
        }
    text = (
        f"Journal of follow {identity} (paper) is intact: {report.entries} entries, "
        f"head {report.head}."
        if broken is None
        else f"Journal of follow {identity} (paper) is broken at entry {broken.seq}: "
        f"{broken.reason}"
    )
    emit(facts, json_out=json_out, fallback=text)
    if broken is not None:
        raise typer.Exit(1)


@follow_app.command("today")
def today(json_out: JSON = False) -> None:
    """What is active today: one row per active follow, grouped. Reads journals only."""
    facts = follow_today.build(AlphaSettings().data_dir, _clock())
    emit(facts, json_out=json_out, fallback=follow_today.text(facts))


@follow_app.command("book")
def book(json_out: JSON = False) -> None:
    """Every active follow as a share of ONE paper account, and the sum per asset. Read-only."""
    home = AlphaSettings().data_dir
    sizes = {f["follow_id"]: f for f in store.list_facts(home) if f["state"] != "broken"}
    today_rows = follow_today.build(home, _clock())["rows"]
    rows: list[book_math.AccountRow] = [
        {
            "follow_id": r["follow_id"],
            "name": r["name"],
            "assets": list(sizes[r["follow_id"]]["assets"]),
            "size_pct": float(sizes[r["follow_id"]]["paper_account_percent"]),
            "open": bool(r["paper"]["open"]),
        }
        for r in today_rows
        if r["entry_kind"] != "broken"
    ]
    facts = {
        **book_math.account_view(rows),
        "paper": True,
        "unreadable": [r["follow_id"] for r in today_rows if r["entry_kind"] == "broken"],
        "notice": book_math.ACCOUNT_NOTICE,
    }
    emit(facts, json_out=json_out, fallback=book_math.render_account(facts))


@follow_app.command("stop")
def stop(
    follow_id: Annotated[str, typer.Argument(help="Follow id or prefix.")],
    reason: Annotated[str, typer.Option("--reason", help="Why it stops.")] = "",
    json_out: JSON = False,
) -> None:
    """Stop a follow. The record and journal stay. Nothing can be written after a stop."""
    home = AlphaSettings().data_dir
    try:
        identity = store.resolve(home, follow_id)
        entry = store.stop_follow(home, identity, reason=reason, clock=_clock)
    except (SpineError, JournalRefusal) as exc:
        fail(exc, json_out)
    emit(
        {"follow_id": identity, "stopped": True, "seq": entry.seq},
        json_out=json_out,
        fallback=f"Follow {identity} stopped (paper). Its record and journal are kept.",
    )


def _update_text(row: dict[str, Any]) -> list[str]:
    lines = [f"Follow {row['follow_id']} (paper): {row['message']}"]
    lines += [f"  {w['session']}  {w['kind']:<6} {w['words']}" for w in row.get("written", [])]
    check = row.get("replay")
    if check and not check["agrees"]:
        lines.append(f"  Replay check differs in {len(check['differences'])} place(s):")
        lines += [f"    {d['session']}: {d['what']}: {d['detail']}" for d in check["differences"]]
    return lines


@follow_app.command("update")
def update(
    follow_id: Annotated[str, typer.Argument(help="Follow id or prefix.")] = "",
    all_follows: Annotated[
        bool, typer.Option("--all", help="Update every active rule follow.")
    ] = False,
    json_out: JSON = False,
) -> None:
    """Book the sessions that closed since the last entry of a followed rule test. Paper only.

    Reads the newest stored bars. It downloads nothing. A session whose bar is not stored is
    `late`; one written after the next open is `missed`. A second run on the same session does
    nothing."""
    home = AlphaSettings().data_dir
    try:
        if bool(follow_id) == all_follows:
            raise SpineError(
                "FOLLOW_UPDATE_TARGET",
                "Name one follow, or use --all.",
                "Example: alpha follow update <follow id>",
            )
        if all_follows:
            rows = follow_update.update_all(home, clock=_clock)
        else:
            identity = store.resolve(home, follow_id)
            rows = [follow_update.update_follow(home, identity, clock=_clock)]
    except (SpineError, JournalRefusal) as exc:
        fail(exc, json_out)
    lines = [line for row in rows for line in _update_text(row)] or ["No follows yet (paper)."]
    emit({"follows": rows}, json_out=json_out, fallback="\n".join(lines))
    if any(row["status"] == "refused" for row in rows):
        raise typer.Exit(1)
