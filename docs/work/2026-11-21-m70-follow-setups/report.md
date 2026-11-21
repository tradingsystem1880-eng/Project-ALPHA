# Report: forward follow for setups, dividends, plain words

Branch `feat/m70-follow-setups`. Paper only. Readings, not verdicts.

## What works end to end
1. `alpha follow start --trade <setup trade id> [--asset A]` then `alpha follow update`, `verify`, `show`, `stop` on a synthetic store
   (`tests/unit/test_follow_setup.py`). The update finds new setup occurrences with the study's code (`find_candidates`,
   `cluster_candidates`, `prepare_exits`, `simulate`), opens a paper position at the next open and applies stop, target, time limit and
   opposite signal. One entry per session in the existing hash-chained journal, same `must_write_by` window.
2. Replay equality: the follow's closed trades (entry, exit, prices, reason, net return) equal the study's own `trades.parquet` rows.
3. Dividends: booked on the rule test's basis (units before the ex-date open, cash at pay date, known by that session). `follow show`
   prints price and dividend parts of the return since the start. Tests: inside the held period, outside it, known late, booked once.
4. Words: `follow_labels.py` is the one label map; `follow show <id> [--all | --last N]` (default 20) prints one plain sentence per entry;
   `list` and `today` use the same words. A test fails when a strategy signal column has no label.
5. Today screen: setup follows show their exits (`FollowToday.tsx`, `exits` in the API row). Display only.

## Decisions
- The brief says `follow start <setup trade id>`. The existing options style is kept: `--trade <id>`. A trade with several assets needs
  `--asset`; one follow follows one asset.
- New record kind `setup_trade`. Study labels and trial identity (trade id, find id, costs, exits) live in the start entry (`setup`),
  not in `follow.toml`, so existing follow ids do not change. `--find` still records a find; its update is refused in plain words.
- Short setups and setups with context series are refused at start (`FOLLOW_SETUP_REFUSED`, `FOLLOW_SETUP_CONTEXT`).
- A trigger on the last known bar is the order for the next open (the study calls this row `no-next-bar`). Cluster first-ness uses the
  study's `cluster_candidates` with that row counted as accepted. Occupancy: one position at a time, as in the study.
- Stop and target fill at the study's conservative prices inside their session; the paper book adds the study's slippage and fee.
- A late or missed session places no paper order. The book mirrors a replay buy only if it holds the order and a sell only if it holds
  the position. The replay check still shows the study's view, so the two can differ after a missed session (same as the rule follow).
- A dividend the store learns late is booked at the first update that sees it (units from the journal's own book), never in an old entry.
- Session loop moved to `follow_session.py` (shared); `follow_update.py` keeps the rule follow and dispatches `setup_trade`.
- Added readers on purpose to `test_follow_separation.py` (`follow_session`, `follow_setup`, `follow_setup_update`) and the regex now
  also names them. Added `follow_source.forward_dividends` to the `ALLOWED` list of `test_research_reads_are_cut.py` (forward use, as
  `forward_bars`). No guard was weakened.
- `follow_update`'s old refusal text for setups changed; three old assertions (words) were updated to the new plain words.
- Docs: `cli-follow.md`, `research/tools/follow.md`, `commands.md`, `openapi.json`, `generated.ts`. `fs.py verify` was not run, as ruled:
  `gate.py check` lists stale documents under "living documents" (expected).

## Fail-first evidence
- Dividends: with the `follow_update.py` and `follow_source.py` changes stashed, `test_follow_dividends.py` gave 3 failed (`KeyError:
  'dividends'`), 2 passed (pure-function tests).
- Setup follow, labels, show options: tests were written together with the code and not run against a missing implementation.
  The suite did fail on first runs for real defects found by the tests (entry count with weekends, wrong expected trade count).

## Checks
`uv run lint-imports` 13 kept; ruff, ruff format, mypy pass; follow tests, web route tests, frontend vitest (495) pass. `gate.py check`:
only "living documents" (stale list) fails.

## Unverified
- No real data. Multi-asset setups, dividends on a setup follow (shared code, no own test), a setup with a trigger window, and an
  ATR stop were not exercised in the follow tests.
- Frontend e2e (Playwright) not run.

## Real-data trial (owner's machine)
1. `uv run alpha setup find <spec.toml>` then `uv run alpha setup trade <find id>`
2. `uv run alpha follow start --trade <trade id> --asset <asset>`
3. After new bars are stored: `uv run alpha follow update <follow id>`
4. `uv run alpha follow show <follow id> --last 20` and `uv run alpha follow verify <follow id>`
5. `uv run alpha follow today`; open the Workstation Today screen.
6. For dividends: follow a stock rule test over an ex-dividend date and read "price" and "dividends" in `follow show`.
