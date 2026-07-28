"""Turn 75 per-image extractions into one deduplicated, provenance-checked call record.

Three problems stand between a folder of screenshots and a record you can score. Each is handled
here explicitly, because each of them silently inflates or corrupts a track record if it is not.

**1. Overlap.** Consecutive screenshots of a scrolling chat share messages. One post captured in
three frames is one call, not three. Counting frames instead of statements would let a caller's
apparent sample size grow with how enthusiastically their followers screenshot them. The unit of
record here is therefore a **(author, timestamp, text) statement**, deduplicated across files, and
every statement carries the list of files it appeared in.

**2. Reconstruction.** The Drive OCR returns an empty string for some images. An extraction agent
looking at an empty read can reasonably infer content from neighbouring frames — and that inference
is *not evidence*. :func:`verify` checks every structured field back against the image's own
``raw_text`` and quarantines anything that cannot be found there. A quarantined record is reported,
never scored.

**3. Fabricated precision.** A price in a ``levels`` field that does not appear anywhere in the OCR
text was invented by the extractor. Those get stripped, loudly.

Output: ``corpus.json`` (every verified statement, with provenance) and ``calls.csv`` (the subset
that is a dated, directional, scoreable call).

Run: ``python -m research.ace_calls.consolidate``
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW = REPO_ROOT / "research" / "ace_calls" / "raw"
OUT = REPO_ROOT / "research" / "ace_calls"
ANALYSIS = OUT / "analysis"

#: How much of a statement must match for two frames to be the same message. Chat screenshots
#: truncate long posts differently, so an exact-text key would treat a truncated copy as new.
DEDUPE_PREFIX = 60

#: A structured number is trusted only if it appears in the raw OCR text. Digits are compared with
#: separators stripped, because OCR renders 69,011 / 69011 / 69.011 inconsistently.
_DIGITS = re.compile(r"[^0-9]")


#: A statement is accepted as a transcription when this share of its words appear in the OCR text.
#: Not 1.0: OCR wraps lines, mangles the odd character, and drops emoji, so exact-substring matching
#: rejects genuine transcriptions. Not lower: below this an extractor could pass off a paraphrase.
TOKEN_OVERLAP_FLOOR = 0.75


def _normalise_number(value: object) -> str:
    """Digits only, so 69,011 / $69,011 / 69011.0 all compare equal."""
    return _DIGITS.sub("", str(value))


def _number_is_supported(value: object, raw_lower: str, raw_digits: str) -> bool:
    """Whether a structured number is genuinely present in the OCR text.

    Accepts the plain digit form *and* the abbreviated one. A trader writing "79k" and an extractor
    recording 79000 is a correct normalisation, not a fabrication, and an over-strict check here
    would strip real levels while claiming to protect against invented ones.
    """
    digits = _normalise_number(value)
    if not digits:
        return True
    if digits in raw_digits:
        return True
    try:
        number = int(digits)
    except ValueError:
        return False
    # "79k" / "79 k" for 79,000; "1.5m" style is out of range for the levels seen here.
    for scale, suffix in ((1_000, "k"), (1_000_000, "m")):
        if number % scale == 0 and f"{number // scale}{suffix}" in raw_lower:
            return True
    return False


def _tokens(text: str) -> list[str]:
    """Lowercased alphanumeric tokens, which is the granularity OCR preserves reliably."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _text_key(text: str) -> str:
    """Whitespace- and case-insensitive prefix key for deduplication."""
    return " ".join(text.lower().split())[:DEDUPE_PREFIX]


@dataclass
class Statement:
    """One timestamped thing Ace said, and every screenshot it was captured in."""

    author: str
    timestamp: str
    text: str
    files: list[str] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)
    indicators: list[str] = field(default_factory=list)
    kind: str = ""

    @property
    def date(self) -> str:
        return self.timestamp[:10]


#: Phrases an extractor uses when the OCR tool failed and it fell back to reading the PNG directly.
#: Both routes produce genuine transcriptions, but they are different evidence and the report says
#: which is which rather than presenting a hand-read image as tool output.
_VISUAL_MARKERS = (
    "returned an empty",
    "read_file_content returned",
    "reading it directly as an image",
    "manual verbatim transcription",
    "downloaded the png",
)


@dataclass
class Record:
    """One verified image extraction."""

    file: str
    kind: str
    raw_text: str
    data: dict[str, Any]
    quarantined: bool = False
    problems: list[str] = field(default_factory=list)

    @property
    def provenance(self) -> str:
        """How this image's text was obtained: the OCR tool, or a direct visual read."""
        note = str(self.data.get("notes") or "").lower()
        return "visual" if any(m in note for m in _VISUAL_MARKERS) else "ocr"


def load_raw() -> list[Record]:
    """Read every per-image JSON, keeping malformed files visible rather than dropping them."""
    records: list[Record] = []
    for path in sorted(RAW.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            records.append(
                Record(path.stem, "", "", {}, quarantined=True, problems=[f"unparseable: {exc}"])
            )
            continue
        records.append(
            Record(
                file=str(data.get("file") or path.stem),
                kind=str(data.get("kind") or "unknown"),
                raw_text=str(data.get("raw_text") or ""),
                data=data,
            )
        )
    return records


def verify(record: Record) -> Record:
    """Check every structured field against the image's own OCR text.

    The rule is simple and strict: if the OCR produced nothing, nothing structured from that image
    can be evidence. If the OCR produced text, then any *number* in a structured field must appear
    in it. Statement text is checked more leniently — OCR line-wrapping means an exact substring
    test would reject genuine transcriptions — so a statement passes if a distinctive run of its
    words is present.
    """
    problems: list[str] = []
    raw = record.raw_text.strip()

    if not raw:
        record.quarantined = True
        record.problems.append(
            "OCR returned empty text — any structured content for this image is inference, "
            "not transcription, and cannot be scored"
        )
        return record

    raw_lower = raw.lower()
    raw_digits = _normalise_number(raw)
    raw_tokens = set(_tokens(raw))

    levels = record.data.get("levels") or {}
    for key in ("entry", "stop", "target"):
        value = levels.get(key)
        if value in (None, "", []):
            continue
        if not _number_is_supported(value, raw_lower, raw_digits):
            problems.append(f"levels.{key}={value!r} does not appear in the OCR text — stripped")
            levels[key] = None

    pnl = record.data.get("pnl") or {}
    for key, value in list(pnl.items()):
        if value in (None, "", []):
            continue
        if not _number_is_supported(value, raw_lower, raw_digits):
            problems.append(f"pnl.{key}={value!r} does not appear in the OCR text — stripped")
            pnl[key] = None

    kept: list[dict[str, Any]] = []
    for stmt in record.data.get("statements") or []:
        tokens = _tokens(str(stmt.get("text") or ""))
        if not tokens:
            continue
        overlap = sum(1 for t in tokens if t in raw_tokens) / len(tokens)
        if overlap < TOKEN_OVERLAP_FLOOR:
            problems.append(
                f"statement {stmt.get('timestamp')!r} only {overlap:.0%} of its words appear in "
                "the OCR text — dropped as a probable paraphrase"
            )
            continue
        kept.append(stmt)
    record.data["statements"] = kept

    record.problems.extend(problems)
    return record


def statements_from(records: list[Record]) -> list[Statement]:
    """Deduplicate statements across overlapping screenshots, preserving every source file."""
    merged: dict[tuple[str, str, str], Statement] = {}
    for rec in records:
        if rec.quarantined:
            continue
        for stmt in rec.data.get("statements") or []:
            author = str(stmt.get("author") or "").strip()
            ts = str(stmt.get("timestamp") or "").strip()
            text = str(stmt.get("text") or "").strip()
            if not (author and ts and text):
                continue
            key = (author.lower(), ts, _text_key(text))
            existing = merged.get(key)
            if existing is None:
                merged[key] = Statement(
                    author=author,
                    timestamp=ts,
                    text=text,
                    files=[rec.file],
                    assets=list(rec.data.get("assets") or []),
                    indicators=list(rec.data.get("indicators") or []),
                    kind=rec.kind,
                )
            else:
                if rec.file not in existing.files:
                    existing.files.append(rec.file)
                # Keep the longest transcription: a later frame often un-truncates an earlier one.
                if len(text) > len(existing.text):
                    existing.text = text
                for a in rec.data.get("assets") or []:
                    if a not in existing.assets:
                        existing.assets.append(a)
    return sorted(merged.values(), key=lambda s: (s.timestamp, s.author))


def summarise(records: list[Record], statements: list[Statement]) -> str:
    """A plain-text integrity report — what was read, what was merged, what was thrown out."""
    good = [r for r in records if not r.quarantined]
    bad = [r for r in records if r.quarantined]
    kinds = Counter(r.kind for r in good)
    flagged = [(r.file, p) for r in records for p in r.problems]
    dupes = [s for s in statements if len(s.files) > 1]
    dates = sorted({s.date for s in statements})

    provenance = Counter(r.provenance for r in good)
    lines = [
        "=" * 100,
        "EXTRACTION INTEGRITY",
        "=" * 100,
        f"  images extracted        {len(records)}",
        f"  usable                  {len(good)}",
        f"  quarantined             {len(bad)}",
        f"  kinds                   {dict(kinds)}",
        f"  text provenance         {dict(provenance)}  "
        "(ocr = Drive tool; visual = PNG read directly after the tool returned nothing)",
        "",
        f"  distinct statements     {len(statements)}",
        f"  appearing in >1 frame   {len(dupes)}  (merged, not double-counted)",
        f"  date range              {dates[0] if dates else '-'} .. {dates[-1] if dates else '-'}",
    ]
    if bad:
        lines += ["", "  QUARANTINED — not scoreable:"]
        lines += [f"    {r.file}: {'; '.join(r.problems)}" for r in bad]
    if flagged:
        lines += ["", f"  FIELD-LEVEL PROBLEMS ({len(flagged)}):"]
        lines += [f"    {f}: {p}" for f, p in flagged[:40]]
        if len(flagged) > 40:
            lines.append(f"    ... and {len(flagged) - 40} more")
    if dupes:
        lines += ["", "  MERGED ACROSS FRAMES (sample):"]
        for s in dupes[:10]:
            lines.append(f"    {s.timestamp}  {'+'.join(s.files)}  {s.text[:60]}")
    return "\n".join(lines)


def write_corpus(records: list[Record], statements: list[Statement]) -> None:
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    payload = {
        "images": len(records),
        "quarantined": [r.file for r in records if r.quarantined],
        "statements": [
            {
                "timestamp": s.timestamp,
                "author": s.author,
                "text": s.text,
                "files": s.files,
                "assets": s.assets,
                "indicators": s.indicators,
                "kind": s.kind,
            }
            for s in statements
        ],
        "problems": {r.file: r.problems for r in records if r.problems},
    }
    (ANALYSIS / "corpus.json").write_text(json.dumps(payload, indent=2))
    print(f"\nwrote {ANALYSIS / 'corpus.json'} ({len(statements)} statements)")


def write_call_template(statements: list[Statement]) -> None:
    """Emit every statement as a candidate call row, direction left BLANK for adjudication.

    Deliberately not automatic. Deciding whether "everything depends on the green line" is a long
    call, a short call or a shrug is a judgement, and hiding that judgement inside a keyword
    heuristic would make the record look more objective than it is. The blank column is filled in a
    reviewed pass, and rows left blank are excluded from scoring by ``score.load_calls``.
    """
    dest = OUT / "calls_candidates.csv"
    with dest.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "file",
                "date",
                "timestamp",
                "asset",
                "direction",
                "horizon_days",
                "entry",
                "stop",
                "target",
                "claim",
            ]
        )
        for s in statements:
            writer.writerow(
                [
                    "+".join(s.files),
                    s.date,
                    s.timestamp,
                    (s.assets[0] if s.assets else ""),
                    "",  # direction — adjudicated, never guessed
                    "",
                    "",
                    "",
                    "",
                    " ".join(s.text.split())[:300],
                ]
            )
    print(f"wrote {dest} ({len(statements)} candidate rows, direction column blank for review)")


def main() -> int:
    records = [verify(r) for r in load_raw()]
    statements = statements_from(records)
    print(summarise(records, statements))
    write_corpus(records, statements)
    write_call_template(statements)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
