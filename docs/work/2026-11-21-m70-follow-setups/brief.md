# Brief: forward follow for setups, dividends in the paper book, plain follow words

Branch: `feat/m70-follow-setups`. Rules: `docs/work/_common-rules-2026-11-21.md`. Workspace: `apps/alpha-cli/CONTEXT.md`
(follow rows), `docs/reference/invariants/cli-follow.md`, `research/tools/` follow cards.

## Why

`alpha follow` is the forward paper test: it replays a tested idea on new bars as they arrive. Today it works for rule tests only. An
audit found: "A setup can start a follow, but it cannot be updated"; "A follow is long only, price only: no dividend"; `follow show`
prints only the 5 newest entries and raw labels such as `fast_sma`.

## Build

1. **Setup follows.** `alpha follow start <setup trade id>` then `alpha follow update` must work end to end for a Setup Lab trade
   (`spine/setup_exits.py` holds the exit rules: stop, target, time stop). The update finds new occurrences of the setup on new bars with
   the same code path the study used, opens paper positions at the next open, and applies the same exits. Write journal entries in the
   existing hash-chained journal (`follow_journal`), one decision per session, with the same `must_write_by` rule. Replay check: the
   follow's first decisions on data the study already saw must equal the study's own trades (test it).
2. **Dividends.** A long paper position held over an ex-dividend date books the cash dividend (the store has dividends; the rule test
   already uses "one dividend basis": find it and use the same point-in-time rule: a dividend counts only when it was known by that
   session). Say in `follow show` how much of the return since the start is price and how much is dividends.
3. **Words.** `follow show <id> [--all | --last N]` (default 20), with plain labels for every signal column (a label map in ONE place;
   a raw code name never reaches the owner) and a one-line plain sentence per entry. `follow list` and `follow today` use the same words.
4. **Honesty.** A follow never reads research data paths and research never reads the forward store (the separation test). A setup
   follow keeps the labels and the trial identity of the study it came from. Short positions and context-gated sources stay refused with
   a clear message.
5. The Workstation Today screen (`apps/alpha-web`, `FollowToday*`): show setup follows with their exits in plain words. Display only.

## Tests

Start, update, verify and stop for a setup follow on a synthetic store; the replay equality; a dividend inside a held period, one known
late (not booked before it was known), one outside; journal chain intact after each update; the Today API row; label map complete (a test
fails when a signal column has no plain label).

## Done

Draft pull request, `ci-ok` green, `report.md` in this folder: what works end to end, decisions, what is unverified. A real-data trial
is done later on the owner's machine: list the exact commands for it in the report.
