"""Turn 212 corpus statements into the scoreable call record — the one irreducibly human step.

Deciding whether "everything depends on the green line" is a long, a short or a shrug cannot be
automated, and pretending otherwise would hide the judgement rather than remove it. So the
judgement lives here, as an explicit index-keyed map into ``analysis/corpus.json``, and every row
of ``calls.csv`` carries the corpus index, the source screenshot and the verbatim text it came
from. A reader who disagrees with a call can find it in seconds and re-run the score without it.

The rules were fixed in ``score.py`` before any screenshot was read. Four of them do the work:

* **Hedged is not a call.** "might", "could", "if it breaks", "I'll be looking for" — these stay in
  the corpus and out of the record. This costs the record some of its most memorable material
  (the 99k call is explicitly conditional) and that is the point: consistency beats anecdote.
* **Retrospective commentary is never a call.** "Market confirmed", "as planned", "undefeated".
* **One call per (date, asset, direction).** A stance repeated five times in an evening is one
  stance, and counting it five times would inflate whichever way it happened to go.
* **Same-day contradictions are unscoreable.** When both directions are stated for one asset on one
  day, *something* is going to look right afterwards. Both are dropped and the contradiction is
  counted separately — it is a fact about the method, not a coin-flip to be graded.

Two extra conventions, declared here before the scoring ran:

* **A bare price with no verb** ("89k", "46.2k") is read as directional relative to that day's
  close. This is a real inference, so those rows are marked ``bare_level`` and the report shows the
  record with and without them.
* **The follower's fill, not the caller's.** Scoring always enters at the close of the bar the
  message was posted on. When Ace says he is long from 64.3k and BTC is at 68.8k as he types, the
  reader cannot have his price. Recording his entry and scoring from it would credit him with a
  4,500-point head start no follower could take.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS = REPO_ROOT / "research" / "ace_calls" / "analysis" / "corpus.json"
CALLS = REPO_ROOT / "research" / "ace_calls" / "calls.csv"


@dataclass(frozen=True)
class Verdict:
    """One adjudicated call: what was decided about a corpus statement, and on what basis."""

    index: int
    asset: str
    direction: str
    #: ``position``  — he states he holds it ("I'm long", "holding short", "adding", "buying").
    #: ``forecast``  — he predicts a move without claiming a position.
    #: ``bare_level``— a naked price with no verb, read as directional against that day's close.
    basis: str
    target: float | None = None
    horizon_days: int = 30
    note: str = ""


#: Assets named in a statement that no price series covers. Kept in the record rather than dropped,
#: because "unscoreable" is part of the honest denominator: a caller whose verifiable calls are a
#: subset of his loud ones should not be graded only on the subset that happens to be checkable.
UNSCOREABLE_ASSETS = {"GMX", "SNDK", "GOLD", "HYPE"}

#: The adjudication. Index → verdict, against analysis/corpus.json.
VERDICTS: tuple[Verdict, ...] = (
    Verdict(0, "BTC", "long", "forecast", 79_000, note="waiting for btc to hit 79k"),
    Verdict(2, "BTC", "long", "forecast", 73_700, note="memorandum: 69k pivot then 73.7-74.5k"),
    Verdict(7, "BTC", "long", "position", note="long 5x, states avg 64.3k"),
    Verdict(7, "LINK", "long", "position", note="$1M 6x long, panel entry 8.7933"),
    Verdict(7, "XRP", "long", "position", note="'bought insane amount of XRP'"),
    Verdict(17, "BTC", "short", "position", note="shorted at 40x leverage"),
    Verdict(22, "BTC", "short", "position", note="'even though i shorted at the region'"),
    Verdict(42, "BTC", "short", "forecast", note="'FOMC - We Gonna Drop a bit'"),
    Verdict(52, "BTC", "short", "forecast", note="'Dump incoming, be careful'"),
    Verdict(55, "BTC", "short", "forecast", 62_000, note="'No matter what we going to see 62k'"),
    Verdict(59, "BTC", "short", "position", 66_000, note="'Shorts activated ... until 66k'"),
    Verdict(62, "BTC", "short", "position", 49_000, note="'71500 holding short'; wants 52-49k"),
    Verdict(69, "BTC", "short", "position", 49_000, note="holding short 'until I see BTC at 49k'"),
    Verdict(85, "BTC", "short", "position", note="'I'm shorting.'"),
    Verdict(93, "BTC", "short", "position", note="'be in short'; 'I'm short'"),
    Verdict(
        95, "BTC", "short", "forecast", 62_000, note="'62k is the main region i'm looking for'"
    ),
    Verdict(96, "BTC", "short", "forecast", note="'Many things wrong with this pump'"),
    Verdict(98, "BTC", "short", "forecast", note="'70.2k = bearish retest'"),
    Verdict(99, "GMX", "long", "position", note="'GMX 3X - LV HERE'"),
    Verdict(100, "BTC", "long", "forecast", note="'bullish region forming', prior shorts voided"),
    Verdict(113, "BTC", "long", "forecast", note="'The break out has begun'"),
    Verdict(125, "BTC", "long", "position", horizon_days=44, note="'LONG UNTIL JUNE' (to 1 Jun)"),
    Verdict(130, "BTC", "long", "bare_level", 89_000, note="'89k' with spot at 73,758"),
    Verdict(131, "GMX", "long", "position", note="'betting hard'"),
    Verdict(134, "BTC", "long", "forecast", 89_000, note="'monday we fly'; '89...' same day"),
    Verdict(146, "LINK", "long", "forecast", note="'Make sure your heavy on link'"),
    Verdict(152, "BTC", "long", "forecast", note="'The pump will be disgusting'"),
    Verdict(162, "BTC", "long", "position", 108_000, note="held since Feb, 'would go to 108k'"),
    Verdict(164, "BTC", "short", "bare_level", 46_200, note="'46.2k' with spot at 61,022"),
    Verdict(172, "BTC", "long", "forecast", 68_800, note="'We moving towards ... 68.8k'"),
    Verdict(177, "BTC", "long", "forecast", 68_800, note="'looking for a pull back to 68.8k'"),
    Verdict(188, "BTC", "long", "forecast", note="'Bottom is forming, 3 taps on 60k's'"),
    Verdict(187, "LINK", "long", "position", note="'Adding some link here'"),
    Verdict(187, "DOGE", "long", "position", note="'and some doge coin at same time'"),
    Verdict(190, "DOGE", "long", "position", note="'Buying doge here'"),
    Verdict(192, "BTC", "long", "forecast", note="'No more 48k btc, we are bottom'"),
    Verdict(193, "XRP", "long", "position", note="'Long' / 'Xrp'"),
    Verdict(200, "BTC", "long", "forecast", note="'summer gonna be green hold tight'"),
    Verdict(201, "BTC", "long", "forecast", 69_000, note="'Looking for 69-72k resistance level'"),
    Verdict(204, "BTC", "long", "forecast", note="market-wide claim, scored against BTC as proxy"),
    Verdict(206, "XRP", "long", "forecast", note="inverse H&S, 'upside bias', 'actual FOMO'"),
    Verdict(211, "BTC", "long", "forecast", 70_000, note="'next leg up which will lead to 70k+'"),
)

#: Days where both directions were stated for one asset, so neither is scoreable. Recorded because
#: the frequency of this is itself a result — see REPORT.md.
CONTRADICTIONS: tuple[tuple[str, str, int, int, str], ...] = (
    (
        "2026-03-21",
        "BTC",
        49,
        50,
        "02:42 'stay away from longs @everyone' vs 10:55 'Longs continues...' — 8h apart",
    ),
)


def load_statements() -> list[dict[str, object]]:
    if not CORPUS.exists():
        raise FileNotFoundError(f"{CORPUS} absent — run research.ace_calls.consolidate first")
    payload = json.loads(CORPUS.read_text())
    statements: list[dict[str, object]] = payload["statements"]
    return statements


def build_rows() -> list[dict[str, str]]:
    """Join each verdict to its corpus statement, failing loud on a stale index."""
    statements = load_statements()
    seen: set[tuple[str, str, str]] = set()
    rows: list[dict[str, str]] = []

    for v in VERDICTS:
        if not 0 <= v.index < len(statements):
            raise IndexError(
                f"verdict index {v.index} is outside the {len(statements)}-statement corpus — "
                "the corpus was rebuilt and the adjudication no longer lines up with it"
            )
        stmt = statements[v.index]
        timestamp = str(stmt["timestamp"])
        date = timestamp[:10]
        key = (date, v.asset, v.direction)
        if key in seen:
            raise ValueError(f"duplicate call {key} — one call per (date, asset, direction)")
        seen.add(key)
        files = stmt.get("files") or []
        rows.append(
            {
                "corpus_index": str(v.index),
                "file": ",".join(str(f) for f in files) if isinstance(files, list) else "",
                "date": date,
                "timestamp": timestamp,
                "asset": v.asset,
                "direction": v.direction,
                "basis": v.basis,
                "horizon_days": str(v.horizon_days),
                "entry": "",
                "stop": "",
                "target": "" if v.target is None else f"{v.target:g}",
                "claim": " ".join(str(stmt["text"]).split())[:300],
                "adjudication": v.note,
            }
        )
    return sorted(rows, key=lambda r: (r["date"], r["asset"], r["direction"]))


def write_calls() -> list[dict[str, str]]:
    rows = build_rows()
    with CALLS.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main() -> int:
    statements = load_statements()
    rows = write_calls()

    scoreable = [r for r in rows if r["asset"] not in UNSCOREABLE_ASSETS]
    print("=" * 100)
    print("ADJUDICATION — 212 statements to a scoreable call record")
    print("=" * 100)
    print(f"\n  corpus statements       {len(statements)}")
    print(f"  adjudicated as calls    {len(rows)}")
    print(f"  of which have price data{len(scoreable):>4}")
    print(f"  no series exists for    {len(rows) - len(scoreable)}  ({sorted(UNSCOREABLE_ASSETS)})")
    print(f"  dropped as neutral      {len(statements) - len(rows)}")
    print(f"  same-day contradictions {len(CONTRADICTIONS)}  (both sides dropped)")
    for date, asset, a, b, why in CONTRADICTIONS:
        print(f"    {date} {asset}  #{a}/#{b}  {why}")

    print(f"\n  by direction            {dict(Counter(r['direction'] for r in rows))}")
    print(f"  by asset                {dict(Counter(r['asset'] for r in rows))}")
    print(f"  by basis                {dict(Counter(r['basis'] for r in rows))}")
    with_target = sum(1 for r in rows if r["target"])
    with_stop = sum(1 for r in rows if r["stop"])
    print(f"\n  calls naming a target   {with_target}/{len(rows)}")
    print(f"  calls naming a stop     {with_stop}/{len(rows)}   <- not one, in five months")
    print(f"\nwrote {CALLS} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
