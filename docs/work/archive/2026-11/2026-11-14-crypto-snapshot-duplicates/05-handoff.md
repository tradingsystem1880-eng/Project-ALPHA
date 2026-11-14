## What changed for you

- **Your stuck crypto snapshot works again, and the whole-store check passes.** The BTC January
  2024 snapshot was refused because that month had been downloaded twice. ALPHA now treats two
  downloads of the same file as one when they agree in every recorded detail except when they were
  fetched, and refuses loudly if they differ in anything else. Creating a snapshot and checking it
  later now follow that one rule, so a snapshot ALPHA lets you create can always be checked again.
  Nothing stored was edited or deleted (decision record: ADR-0046).
- **No more false failure for the current month.** Binance publishes a month's file only after the
  month ends. A backfill now lists that month as "not published yet" and records no failure; the
  status command shows the same list. The old November failure entries stay in the progress files
  but no longer appear in any status.
- **A crypto snapshot can hold many months of many coins**, and its name no longer depends on the
  order you list them in. That part already half-worked; what was missing was the fixed order and a
  rule that two members of one coin cannot cover the same days. The daily-rule reader still reads
  one month per snapshot (see "unsure" below).
- **The Stooq downloader no longer gets past Stooq's "verify your browser" check** (it used to
  solve it and pretend to be a desktop browser). It now refuses with a clear message. The
  data-layer page also records that Yahoo's terms forbid automated collection, so the `yfinance`
  downloader must not be used without Yahoo's permission; the downloader itself is kept.

## How to see it

```sh
export ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data
uv run alpha crypto-data storage-verify --json        # "state": "verified", 2 snapshots
uv run alpha crypto-data snapshot-verify c8ab0d2a0ad8b0faff797569521c16b1aa7f615e9d80a3818a92b95e1f5f6226 --json
```

Full commands and outputs: `docs/work/archive/2026-11/2026-11-14-crypto-snapshot-duplicates/04-verify.md`.

## Checks run

- Every fault reproduced first with a failing test on made-up data (16 new tests failed on main
  for the expected reason), then fixed; the real-folder refusal was recorded before the fix.
- On the real folder after the fix: both snapshots verify, `storage-verify` passes, the BTC
  backfill status shows no failures. A checksum list of every file showed the folder unchanged.
- On a copy of the folder: a 12-month BTC 2024 snapshot gets the same name in either order and
  verifies.
- `uv run python scripts/gate.py check --all`, then CI on this pull request.
- Not run: the live Stooq test (no network use), and the moment Binance publishes a finished month
  (not measured).

## Who built and who reviewed

- Built by Codex: the snapshot and backfill fix by `gpt-6-astra` (effort high, hard class, chosen
  because it decides which data research may use), 17m36s, one fix round; the Stooq fix by
  `gpt-6.1-sol` (effort medium, small class), 5m45s. No fallback to a Claude builder was needed.
  Claude (Opus) planned, wrote the documents and made four small fixes after review.
- Reviewed by an independent Claude Opus reviewer (2 medium, 4 low findings; 5 fixed, 1 rejected
  with a reason) and by Codex (`gpt-6-astra`, medium) twice (1 medium finding, the same as one of
  Opus's, fixed; then 0). Details in `04-verify.md`.

## The one document updated

- [ADR-0046](../../../../adr/0046-crypto-snapshot-members-are-content-addressed.md) (new): what a
  snapshot member is and why equal downloads count as one.
- `docs/reference/invariants/data.md` (Crypto storage; Stooq rule),
  `docs/reference/invariants/cli-crypto-data.md` (Backfill),
  `docs/reference/project/components/data-layer.md` (new "Limits": Stooq, Yahoo, Binance months),
  capability real-data lines, and the regenerated command reference, roadmap index and status
  page. The README was checked; it does not describe these commands, so it is unchanged.

## What I am unsure about

- A month that has ended but whose file Binance has not published yet (usually the first day or
  so of a month) is still recorded as a failure. I left it loud on purpose, because the delay is not
  measured and a guessed grace period could hide a genuinely missing file.
- Running a multi-year **daily-rule** study still needs the daily price reader to accept many
  months. That reader is one of the files your daily-rule approvals are bound to, so changing it
  would void pending daily-rule approvals; the plan for it is at the end of `02-plan.md`. Your call
  when you want such a study.
- A snapshot stored earlier with two overlapping members of one coin would now fail its check. The
  real folder has none (both snapshots hold one month); I could not check other copies of your data
  that might exist elsewhere.

## Protected files touched

- `.claude/code-size-baseline.json`: the entry for `crypto_data_cmds.py` lowered from 4,707 to
  4,704 lines, because the file shrank (the test requires the entry to equal the file's size).
- No approval-bound file changed: none of the daily-rule guard files (`crypto_bulk_store.py`,
  `control_store.py`, `crypto_price_snapshot_query.py` and the others) and no research-bound
  module. No owner approval is invalidated.
