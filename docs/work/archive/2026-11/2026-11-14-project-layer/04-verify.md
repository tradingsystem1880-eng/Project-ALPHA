# Verify: project layer

## Commands run

- `uv run pytest -q tests/unit/test_filesystem_contract.py tests/unit/test_docs_links.py`, on the
  working tree that became commit `63c32144`: 48 passed.
- The same, after deliberately removing one capability claim and one workspace link-up row: the
  two new tests failed with messages naming the file to fix. Both edits were then undone.
- `uv run python scripts/gate.py check --all` on that tree: exit 0 (ruff, formatting, import
  contracts, mypy, the fast test tier).

## End-to-end check

A cold-reader trial, run twice by a fresh agent (Claude Sonnet) that saw only the repository: no
web, no memory, no git history. It started at `CLAUDE.md` and `CONTEXT.md`, followed only the
links, and kept a ledger of every file and its size. Topics: RD-Agent, Qlib, Nautilus, the data
layer, the validation checks and owner approval, the Workstation, the literature worker, and the
route to paper and live trading. For each it answered: job and why, design, what is real, where
(code, plan, decision record), what is next, and what must never be done.

Before: a snapshot of `main` at `f89aa1bb`. After: commit `63c32144` (before two wording fixes).

| Measure | Before | After |
|---|---|---|
| "Should RD-Agent be shelved because it is not installed?" | No, but only via the triage sheet, found through `STATUS.md` and a text search; no routing row pointed to it | No, from the overview's rule at 15.6 KB; the owner's own words at 27.5 KB |
| Bytes read before that answer | about 56 KB (48 KB of whole files plus excerpts) | 15.6 KB (rule), 27.5 KB (owner's words) |
| Searches used | 8 document searches and 1 grep | none |
| Where "why it exists" and "never" came from | scattered: workspace files, invariants, ADRs, README | one component file per topic |
| Files read in total | 24 (several only partly, three of 33 to 190 KB) | 19, all in full, 77.9 KB |

Cell counts (36 answered, 11 partial, 1 not found before; 32, 15 and 1 after) are not comparable:
the second reader marked "what is real today" partial when the part itself is only partly
working, and marked plans partial because it did not open `capabilities.toml`, where plans are
listed. The gaps both readers found are real and are listed below.

## Not run

- CI: runs on the pull request.
- The trial used one reader per side; it is evidence about routing, not a statistic.

## Review findings

- Built by Claude (Opus 5.5); reviewed by the two trial readers, not by a second model. Their findings:
- Fixed: the overview said all three engines "are installed"; it now says they are meant to be,
  and an uninstalled engine is work to finish. The Workstation now states that no next step is
  recorded.
- Left open, by design: "what is real today" links `STATUS.md` instead of restating it.
- Left open, for the owner: `STATUS.md` still shows SHELVE or DELETE recommendations for Qlib
  cards 10, A and F; whether Qlib and Nautilus are core engines is the first Qlib question.
- Left open: `docs/roadmap/rd-agent-in-alpha.md` has no front matter; no decision record states
  RD-Agent's role.
