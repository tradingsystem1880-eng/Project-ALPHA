---
owner: command line follow journal
sources:
  - apps/alpha-cli/src/alpha_cli/follow_journal.py
  - apps/alpha-cli/src/alpha_cli/follow_chain.py
  - apps/alpha-cli/src/alpha_cli/follow_store.py
  - apps/alpha-cli/src/alpha_cli/follow_source.py
  - apps/alpha-cli/src/alpha_cli/follow_cmds.py
  - apps/alpha-cli/src/alpha_cli/follow_update.py
  - apps/alpha-cli/src/alpha_cli/follow_update_check.py
  - apps/alpha-cli/src/alpha_cli/follow_replay.py
  - apps/alpha-cli/src/alpha_cli/follow_book.py
  - apps/alpha-cli/src/alpha_cli/follow_show.py
  - apps/alpha-cli/src/alpha_cli/follow_today.py
  - apps/alpha-cli/src/alpha_cli/follow_counts.py
  - apps/alpha-cli/src/alpha_cli/spine/book.py
  - apps/alpha-cli/src/alpha_cli/nightly_follow.py
  - apps/alpha-cli/src/alpha_cli/nightly_refresh.py
  - tests/unit/test_follow_separation.py
verified: f82b7658d6a7bebe
---

# Command line follow invariants

Rules for `alpha follow`. A tested idea is followed on paper as new bars arrive. Options are in the
[command reference](../commands.md#alpha-follow). F1: the frozen record and the journal. F2: `follow update` for a followed
rule test (below). F3: `follow today` and the nightly steps N4 and N0 (below).
A followed setup trade is updated like a rule test (Setup follow, below). A setup find or a factor cannot be updated. Every screen of text says "paper".

## Separation (the integrity rule)
- `<data_dir>/forward/` is one-way. Research writes nothing there and reads nothing from there.
- Only the modules on the explicit `READERS` list in `tests/unit/test_follow_separation.py` may name the follow store
  modules or open a path under `forward/`. Today that is the fifteen `follow_*.py` modules, each with a one-line reason in `READER_REASONS`.
  A new reader (a Today page) is added on purpose, in review.
  The nightly modules and `next_cmds.py` are not readers: they call `alpha follow ...` as child commands, or `follow_counts`.
- The guard reads source text under `apps/*/src`, `packages/*/src` and `workers/`. It also fails on the store's file names
  (`journal.jsonl`, `follow.toml`), `FOLLOW_DIR`, `AlphaFollowV1`, a name glued from parts (`"for" "ward"`), and a module that
  lists every folder of the data directory (`home` or `data_dir` with `iterdir`, `rglob`, `os.walk`, `copytree`, or a `glob` that starts with `*`).
  It proves itself with fixture strings, not an edit of real modules. It is a text guard: a path built at run time from
  other words is not caught.
- `follow start` and `follow update` write no trial-ledger row, change no research record and write no file outside `forward/`.
  A follow is not a trial. Choosing what to follow is still a selection; later builds count it where the owner sees it.
- Forward use reads the newest bars on purpose, as `alpha scan check` does, only through `follow_source`. `start` reads one bar per
  asset, only to record its hash. `update` reads the bars known at the clock. Research commands keep their cut-off. No forward module
  adds a reserved date or bypasses a cut-off helper.
- The start entry carries bar hashes and no bar dates, so no timestamp from before the start is written.

## The follow record
- `forward/<follow_id>/follow.toml` is written once and never edited. `follow_id` is the first 12 hex characters of a hash of the rest.
- Fields: `kind` (`rule_test` or `setup_find`), `source_id` (the run id or find id), `spec_sha256`, `card_id` (the idea card, if any),
  `assets`, `paper_account_percent`, `started_at` (aware UTC), `version`, `supersedes`.
- A factor is refused: "Following a factor is not built yet."
- Size is a percent of a paper account. The default is 10. It must be above 0 and at most 100.
- An edited record no longer matches its id. Every read checks this and fails loud.

## Versions
- Changing a followed idea is never an edit. The idea is the linked idea card. Without a card, the idea is the source:
  the same rule test or setup find (`kind` and `source_id`). Two different tests without a card are two ideas, because
  nothing stored links them. Link a card to make them one idea.
- `follow start` on the same spec, assets and size of an active follow returns that follow. Nothing is written.
- A different spec, asset set or size for the same idea makes a new follow: `version` plus one and `supersedes` set.
  The old follow gets a `stop` entry. Its folder is kept. The text says the forward clock restarts.
- The new follow is written first. A crash can leave two active follows. It cannot leave none.
- Starts take one lock (`forward/.start.lock`), so two starts at once of one spec make one follow.

## The journal
- `forward/<follow_id>/journal.jsonl` is append-only. One line is one entry.
- Entry fields: `seq` (from 1), `session_date`, `written_at` (aware UTC, from an injected clock), `kind`
  (`start`, `bar`, `missed`, `late`, `stop`), `bar_hashes` (latest bar hash per asset), `payload` (free object),
  `prev_hash`, `entry_hash`. The hash is SHA-256 of the canonical entry without `entry_hash`. The first `prev_hash` is 64 zeros.
- `start` and `stop` come from F1. `update` writes `bar` (a normal session entry), `late` and `missed`.
- The start entry's payload names its `follow_id`. A journal moved into another follow's folder fails every read.
- The clock is passed in. Append takes an exclusive lock, checks the whole chain, writes one line and syncs it. Then, under the same lock, it
  replaces `forward/<follow_id>/head.json` (`entries` and `head`, the last entry hash) atomically.

## What the writer refuses
Each refusal is a typed error with a stable code and plain words.

| Code | Refused |
|---|---|
| `FOLLOW_SESSION_NOT_AFTER` | a session date not after the last one: no inserts, no back-fill |
| `FOLLOW_CLOCK_BACK` | `written_at` earlier than the previous entry |
| `FOLLOW_SEQ_GAP` | a missing or moved sequence number |
| `FOLLOW_CHAIN_BROKEN` | an entry that does not link to the one before, or does not match its hash |
| `FOLLOW_STOPPED` | any write after `stop` |
| `FOLLOW_SECOND_START` | a second `start` |
| `FOLLOW_NO_START` | a first entry that is not `start` |
| `FOLLOW_BAR_TOO_LATE` | a `bar` written more than one day after its session |
| `FOLLOW_SESSION_AHEAD` | a session date later than the day of `written_at`: a day cannot be recorded before it happens |

- A `stop` may share the last session date, so a follow can be replaced on the day it started. It cannot be earlier.
- The first session entry may share the date of the `start` entry: a follow can start in the morning of the session it first records.
- A day not recorded in time can only be written as `missed`. The function that builds a `bar` entry refuses the late day.
- The `start` entry seals `market_calendar` (`""`: trades every day). Only it sets a `bar`'s window; the caller cannot.
  With a calendar the writer sets `must_write_by`, the next session's open from `alpha_data.sessions`; another value is
  `FOLLOW_DEADLINE_NOT_FROM_CALENDAR`. A `bar` before its session's close is `FOLLOW_BAR_BEFORE_CLOSE` (00:00 UTC next day
  with no calendar). A `bar` after the deadline (no calendar: `MAX_BAR_LATENESS_DAYS` after the close) is too late.
  `alpha follow update` refuses `FOLLOW_CALENDAR_CHANGED` if the store's calendar differs from the sealed one.
- `update` reads old bars through the one calendar home ([range rule](data-bar-timeframes.md#exchange-calendar-range)).
  A date after the last session is refused `FOLLOW_CALENDAR_RANGE`, in words with the supported range.

## Verify
- `alpha follow verify <id>` recomputes the chain and the same rules. It reports the first break by entry number and exits 1.
- A flipped byte, a removed middle line, a reordered line and an unreadable line are each found.
- The journal is compared with `head.json`. Fewer entries than the head names is `FOLLOW_TRUNCATED` (a removed last line,
  or a shorter valid chain in place of the file). Another hash at the head number is `FOLLOW_CHAIN_BROKEN`. A missing
  `head.json` counts as a head of 0 entries.
- The head may be one entry behind: a crash after the line was synced and before the head was replaced. That verifies,
  and the next append stores the head again. More than one entry ahead of the head is `FOLLOW_TRUNCATED`.
- `written_at` later than the verifier's clock is `FOLLOW_WRITTEN_AHEAD`. A record with no start entry is `FOLLOW_NO_START`.
  A journal from another follow is `FOLLOW_WRONG_FOLDER`.
- Not covered by `verify` alone: the journal and `head.json` rewritten together (the third anchor, below, catches it), and an
  external timestamp. The threat is an accidental back-fill, not a forger. `verify --entry N` prints the hash of entry N.

## Repair
A last line that was not written to its end (a crash or a full disk during an append) is `FOLLOW_PARTIAL_LINE`. Every read
and every append fails loud on it. Nothing repairs it on its own, and no data is dropped. The owner repairs it:
1. Copy the whole follow folder to a safe place. Keep the copy.
2. Remove only the incomplete last line of `journal.jsonl`, then run `alpha follow verify <id>`. The chain verifies.

## Update (F2)
- `follow update <id>` or `--all` reads the bars known at the clock. It downloads nothing. It refuses a stopped follow, a setup
  follow (`FOLLOW_UPDATE_SETUP_NOT_BUILT`) and a follow whose stored spec no longer hashes to the frozen hash (`FOLLOW_SPEC_CHANGED`).
- One entry per session. A second run on the same session writes nothing and says so. The replay check still runs and is shown.
- Decide on the close of session t from bars up to t. The paper fill is the open of t+1. The update that first sees that bar books it.
  The test `no decision changes when later bars arrive` replays every prefix of a series.
- The engine step is `_runner.run_full_backtest`, the call the rule test makes, with the spec from `assemble_run_spec`. It is never
  `run_idea`: no run folder, no ledger row. `spine/run.py` and `_runner.py` are unchanged, so no run id moved.
- The first forward session is the first whose close is after `started_at`. Bars before it only prime the indicators.
  The follow starts flat. A rule already long at the start is not bought: the paper book waits for the next entry signal
  (a decision that is not long, then a long one). No trade, return or date from before the start is written.
- `late`: the session has closed and its bar is not stored. No decision. The session stays `late`: one entry per session.
- `missed`: written after the next session's open (crypto: more than a day after the session), or a skipped older session. The entry
  says what the rule "would have signalled". There is no paper order. A skipped session is never back-filled as a normal entry.
- A pending order from a normal entry still fills at the next stored open, even if the entry after it is `missed`.
- Each entry holds `decision` (words), `readings` (the rule's operands), `fills`, `book` (cash, units, pending order, equity,
  percent, fees), `bar_hashes` (hash of all bars up to the session), `latest_bar_ts` (a forward bar only), `engine_code_sha256`, `replay`.
- Paper size is a percent of a paper account of 10,000, a fixed share, not compounded. Fees are the rule test's `fee_bps`. Slippage
  is in the engine fill price. Long only. A cash dividend is booked for a position held before the ex date, on the engine's basis:
  units held before the ex-date open, cash at the pay date, only when known (`knowledge_time`). A dividend the store learns late is
  booked at the first update that sees it, never in an older entry. No carry. `follow show` states these terms and a rule long at the start in plain words.

## Setup follow
- `follow start --trade <trade id> [--asset A]` follows a Setup Lab trade study: `kind` `setup_trade`, one asset, long only. A short
  setup and a setup with context series are refused. The start entry keeps the study's `setup`: trade id, find id, labels, costs, exits.
- `update` runs the study's own code (`find_candidates`, `prepare_exits`, `simulate`) on the bars up to each close. A trigger on the
  last bar is an order for the next open. Stop and target fill at the study's prices; an opposite signal exits at the next open.

## Replay check
- Each run replays the frozen rule over warm-up and forward bars and compares the journal with it: decision, readings, fills,
  `engine_code_sha256`, and the hash of the bars up to each session.
- `replay.agrees` is true only if nothing differs. `differences` names the session and what changed. `bars_changed_from` is the first
  session whose stored bars hash differently. The journal is never rewritten. The paper book stays as recorded.
- `missed` and `late` entries are compared on bars only. An engine change shows as `agrees = false`, never as a silent new number.

## Today (F3)
- `follow today [--json]` reads the journals only. It computes no decision, calls no engine and writes nothing (a test lists the
  home before and after). Stopped follows are left out.
- One row per active follow, in groups: NEW SIGNAL (the newest entry is an order for the next open), OPEN PAPER POSITION,
  NOTHING TODAY, LATE OR MISSED (newest entry `late` or `missed`, no entry for the newest closed session, or an unreadable journal), WAITING.
- A row has the idea's name (the card sentence, else the test's name), the asset, the decision in words, the rule's readings, the paper
  position and equity change, the session date and its age ("as of the close of D; 1 session ago").
- The header gives the newest closed session per market (the calendar sealed in the start entry; no calendar: 00:00 UTC) and how many
  follows are behind it. JSON keys: `as_of`, `groups`, `rows`, `behind` (also `markets`, `followed`).
- `alpha next` adds one line when follows exist. It calls `follow_counts` only; `next_cmds.py` is not a reader.
- `today` is a safe read in the generic launcher. `follow update` stays owner-only.

## Book
- `follow book [--json]` shows every active follow as a share of ONE paper account: each size, the total, and the sum per asset
  (two follows of one asset add up; "in the market now" counts open paper positions). Above 100% it prints one plain line.
- It reads through `follow_store` and `follow_today` only, inside `follow_cmds.py`; it writes nothing. The sums are in `spine/book.py`,
  which is not a reader. Sizes are the fixed paper sizes, not marked to market. An unreadable follow is named and not counted.

## Nightly (N4, N0)
- N4 runs `alpha follow update --all --json`, then `follow today --json`, then `follow verify <id> --json` per follow.
  It runs only when a follow is active. With none it is "not run: nothing is followed" and is not a path.
  Blocking: non-zero exit, time out, bad JSON, a failed `verify`, the third anchor. Minor: a late or missed newest entry, a replay that
  does not agree. A decision such as "would sell" is never a defect.
- Third anchor: each record keeps, per follow, the entry count and chain head from `verify`. The next night, entry N of the journal
  must still have the old hash, else the blocking defect "journal history changed since the last nightly record".
  A cut below the old count is the same defect. The first night has no earlier anchor: no alarm; the step says so.
- N0 (`refresh_followed = true`, default off) runs `alpha data pull` once per asset of an active follow, before N4. Never another asset.
  The command comes from the store's provenance (`ccxt:<exchange>`, `yfinance`, `stooq`, `tiingo`, `alpaca` with its identity), from
  the first stored bar. It ends at the newest closed day: the run's UTC date for `yfinance` (exclusive end) and `ccxt` (live candle
  dropped); the day before it for `stooq`, `tiingo`, `alpaca`. A forming bar is never asked for. A named store gets `ALPHA_DATA_DIR=<folder>`.
- N0 runs `alpha data pull ... --json`. The pull freezes the stored series first ([freeze before replace](data-freeze-before-replace.md)),
  reuses an identical snapshot, and prints the snapshot id and the counts of bars added, removed and revised. N0 reads that JSON; it runs
  no snapshot command and compares no bars itself. Exit code 3 means the freeze failed and nothing was replaced: the blocking defect
  "could not freeze <asset> before the refresh" for that asset. Exit code 4 means a failed replace could not put the old bytes
  back; reads of that asset refuse until the named repair runs: the blocking defect "the refresh of <asset> broke its stored series".
  Other assets go on. No snapshot is ever deleted or rewritten.
- A revised or dropped old bar is the minor defect "the provider revised history for <asset>: first changed bar <date> (<columns>)". It
  names the snapshot that holds the earlier series and the command to list it (`alpha data snapshots`). No price is printed. No key is
  read, printed or logged; stderr is scrubbed. Any other failed pull is a minor defect; N4 then writes `late` or `missed`.
- Evidence: a pull that added bars is `computed`; one that added none is `reused` ("no new bar"); a result N0 cannot read is a minor defect.

## Commands
- `follow list`, `show`, `verify` and `today` are safe reads. `follow start`, `update` and `stop` are owner-only in the generic launcher.
- `follow show` prints the record, the entries by kind, the newest 20 entries (`--all`, `--last N`) as plain sentences, with
  readings in plain words (`follow_labels.py` is the one label map), the paper equity numbers and the newest replay check.
- `follow list` shows one state per follow. Ids may be a unique prefix of at least four characters.
