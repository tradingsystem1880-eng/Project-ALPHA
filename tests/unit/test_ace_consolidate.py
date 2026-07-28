"""Consolidation: deduplication, provenance verification, and the fabrication guard.

Two things here decide whether a track record is honest, and both are silent when wrong.

**Deduplication** sets the sample size. Screenshots of a scrolling chat overlap, so the same post
appears in several frames. Count frames and a caller's apparent record grows with how often they
were screenshotted; count statements and it does not. A dedup bug in either direction changes every
interval downstream without changing anything visible.

**Verification** decides what counts as evidence. An extraction agent looking at a failed OCR can
infer content from neighbouring frames, and that inference reads exactly like a transcription. The
guard is that every structured field must be traceable to the image's own text — but the guard must
not be so strict that it rejects correct extractions, which is a failure mode I hit for real: an
early version dropped statements I had personally verified as word-perfect.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.ace_calls.consolidate import (
    Record,
    _number_is_supported,
    _tokens,
    load_raw,
    statements_from,
    summarise,
    verify,
)


def _record(**overrides: object) -> Record:
    data: dict = {
        "file": "IMG_0001",
        "kind": "chat",
        "raw_text": "Ace 01/03/2026, 09:59\nlonged btc at 64.3k with 5x leverage, target 79k",
        "statements": [
            {
                "author": "Ace",
                "timestamp": "2026-03-01 09:59",
                "text": "longed btc at 64.3k with 5x leverage, target 79k",
            }
        ],
        "levels": {"entry": None, "stop": None, "target": None},
        "pnl": {},
        "assets": ["BTC"],
        "indicators": [],
        "notes": "",
    }
    data.update(overrides)  # type: ignore[arg-type]
    return Record(
        file=str(data["file"]),
        kind=str(data["kind"]),
        raw_text=str(data["raw_text"]),
        data=data,
    )


class TestNumberSupport:
    def test_exact_digits_are_supported(self) -> None:
        assert _number_is_supported(69011, "pivot at 69,011 usd", "69011")

    def test_separators_do_not_matter(self) -> None:
        assert _number_is_supported("69,011", "pivot at $69011", "69011")

    def test_k_notation_is_accepted(self) -> None:
        """A trader writing '79k' and an extractor recording 79000 is correct normalisation."""
        assert _number_is_supported(79000, "waiting for btc to hit 79k...", "79")

    def test_m_notation_is_accepted(self) -> None:
        assert _number_is_supported(1_000_000, "i have a 1m position on link", "1")

    def test_an_absent_number_is_rejected(self) -> None:
        assert not _number_is_supported(73700, "waiting for btc to hit 79k", "79")

    def test_empty_values_pass_through(self) -> None:
        assert _number_is_supported("", "anything", "")
        assert _number_is_supported(None, "anything", "")


class TestVerify:
    def test_a_clean_record_survives_intact(self) -> None:
        rec = verify(_record())
        assert not rec.quarantined
        assert rec.problems == []
        assert len(rec.data["statements"]) == 1

    def test_empty_ocr_quarantines_the_whole_record(self) -> None:
        rec = verify(_record(raw_text=""))
        assert rec.quarantined
        assert "cannot be scored" in rec.problems[0]

    def test_a_paraphrased_statement_is_dropped(self) -> None:
        rec = verify(
            _record(
                statements=[
                    {
                        "author": "Ace",
                        "timestamp": "2026-03-01 09:59",
                        "text": "completely different words nowhere near the original transcript",
                    }
                ]
            )
        )
        assert rec.data["statements"] == []
        assert any("paraphrase" in p for p in rec.problems)

    def test_a_genuine_statement_with_ocr_noise_survives(self) -> None:
        """The false-positive case an earlier version got wrong.

        OCR wraps lines and mangles the odd character. A real transcription must not be thrown out
        for differing from the raw text by punctuation and a stray token.
        """
        rec = verify(
            _record(
                raw_text="Ace 20/07/2026, 03:59\n\n\\-The whole crypto market is on the verge\n\n"
                "of a breakout\n\nImage labels: [Screenshot]",
                statements=[
                    {
                        "author": "Ace",
                        "timestamp": "2026-07-20 03:59",
                        "text": "-The whole crypto market is on the verge of a breakout",
                    }
                ],
            )
        )
        assert len(rec.data["statements"]) == 1, rec.problems

    def test_an_invented_level_is_stripped_and_reported(self) -> None:
        rec = verify(_record(levels={"entry": None, "stop": None, "target": "73,700"}))
        assert rec.data["levels"]["target"] is None
        assert any("does not appear" in p for p in rec.problems)

    def test_a_real_level_is_kept(self) -> None:
        rec = verify(
            _record(
                raw_text="target is 73,700 on the upper boundary",
                levels={"entry": None, "stop": None, "target": "73,700"},
                statements=[],
            )
        )
        assert rec.data["levels"]["target"] == "73,700"
        assert rec.problems == []


class TestProvenance:
    def test_default_is_ocr(self) -> None:
        assert _record().provenance == "ocr"

    def test_a_visual_fallback_is_labelled(self) -> None:
        rec = _record(
            notes="read_file_content returned an EMPTY string; transcribed by reading "
            "the PNG directly as an image"
        )
        assert rec.provenance == "visual"

    def test_provenance_appears_in_the_summary(self) -> None:
        rec = verify(_record())
        text = summarise([rec], statements_from([rec]))
        assert "text provenance" in text
        assert "ocr" in text


class TestDeduplication:
    def _rec(self, file: str, stmts: list[dict], assets: list[str] | None = None) -> Record:
        raw = "\n".join(s["text"] for s in stmts)
        return verify(_record(file=file, raw_text=raw, statements=stmts, assets=assets or ["BTC"]))

    def test_the_same_post_in_two_frames_becomes_one_statement(self) -> None:
        stmt = {
            "author": "Ace",
            "timestamp": "2026-03-14 08:55",
            "text": "That grey region is made for shorts and i do complex things behind it",
        }
        out = statements_from([self._rec("IMG_A", [stmt]), self._rec("IMG_B", [dict(stmt)])])
        assert len(out) == 1
        assert out[0].files == ["IMG_A", "IMG_B"]

    def test_a_truncated_copy_merges_and_the_longer_text_wins(self) -> None:
        long_text = (
            "That grey region is made for shorts and i do complex things behind the "
            "scene to get you a clearer image of the market"
        )
        short = {"author": "Ace", "timestamp": "2026-03-14 08:55", "text": long_text[:70]}
        full = {"author": "Ace", "timestamp": "2026-03-14 08:55", "text": long_text}
        out = statements_from([self._rec("IMG_A", [short]), self._rec("IMG_B", [full])])
        assert len(out) == 1
        assert out[0].text == long_text

    def test_different_timestamps_stay_separate(self) -> None:
        a = {"author": "Ace", "timestamp": "2026-03-14 08:55", "text": "the same words entirely"}
        b = {"author": "Ace", "timestamp": "2026-03-14 09:55", "text": "the same words entirely"}
        assert len(statements_from([self._rec("IMG_A", [a, b])])) == 2

    def test_different_authors_stay_separate(self) -> None:
        a = {"author": "Ace", "timestamp": "2026-03-14 08:55", "text": "the same words entirely"}
        b = {"author": "Bob", "timestamp": "2026-03-14 08:55", "text": "the same words entirely"}
        assert len(statements_from([self._rec("IMG_A", [a, b])])) == 2

    def test_assets_are_unioned_across_frames(self) -> None:
        stmt = {"author": "Ace", "timestamp": "2026-03-14 08:55", "text": "heavy on link and xrp"}
        out = statements_from(
            [self._rec("IMG_A", [stmt], ["LINK"]), self._rec("IMG_B", [dict(stmt)], ["XRP"])]
        )
        assert len(out) == 1
        assert set(out[0].assets) == {"LINK", "XRP"}

    def test_quarantined_records_contribute_nothing(self) -> None:
        good = self._rec(
            "IMG_A",
            [
                {
                    "author": "Ace",
                    "timestamp": "2026-03-14 08:55",
                    "text": "a genuine statement here",
                }
            ],
        )
        bad = verify(_record(file="IMG_B", raw_text=""))
        out = statements_from([good, bad])
        assert len(out) == 1
        assert out[0].files == ["IMG_A"]

    def test_statements_come_back_in_timestamp_order(self) -> None:
        rows = [
            {"author": "Ace", "timestamp": "2026-03-17 15:23", "text": "third thing said here"},
            {"author": "Ace", "timestamp": "2026-03-01 09:59", "text": "first thing said here"},
            {"author": "Ace", "timestamp": "2026-03-09 22:33", "text": "second thing said here"},
        ]
        out = statements_from([self._rec("IMG_A", rows)])
        assert [s.timestamp for s in out] == [
            "2026-03-01 09:59",
            "2026-03-09 22:33",
            "2026-03-17 15:23",
        ]


class TestLoadRaw:
    def test_unparseable_json_is_quarantined_not_fatal(self, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        import research.ace_calls.consolidate as mod

        (tmp_path / "IMG_BAD.json").write_text("{not json")
        (tmp_path / "IMG_OK.json").write_text(json.dumps({"file": "IMG_OK", "raw_text": "hello"}))
        monkeypatch.setattr(mod, "RAW", tmp_path)

        records = load_raw()
        assert len(records) == 2
        bad = next(r for r in records if r.file == "IMG_BAD")
        assert bad.quarantined
        assert "unparseable" in bad.problems[0]


class TestTokens:
    def test_punctuation_and_case_are_normalised(self) -> None:
        assert _tokens("BTC at $64,300! (5x)") == ["btc", "at", "64", "300", "5x"]

    @pytest.mark.parametrize("text", ["", "   ", "!!!"])
    def test_empty_input_yields_no_tokens(self, text: str) -> None:
        assert _tokens(text) == []
