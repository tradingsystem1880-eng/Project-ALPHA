## What changed for you

- **The "Are my downloaded daily bars complete?" check is proven end to end and counts as
  Working.** A new automatic check downloads a full month and a month with one missing day with
  the real `alpha` program (from a recorded copy of Binance on this computer); the check finds
  exactly that day, from the command line and through the Workstation's API, without downloading
  or changing anything, and refuses to judge a day that has not closed yet.
- **Your real Binance history is complete.** Every one of the Dell's 1,426 monthly files was
  checked against its calendar month: 1,412 are complete; the 14 short ones are each coin's first
  month, which starts on the day it was listed. No duplicated or out-of-place day anywhere.
- Your data folder was checked file by file before and after all four proofs: nothing of yours
  was changed.

## How to see it

```sh
uv run alpha crypto-data quality <manifest-id> --coverage-start 2026-10-01T00:00:00Z \
  --coverage-end 2026-11-01T00:00:00Z --as-of 2026-11-14T00:00:00Z \
  --expected-cadence-seconds 86400 --max-verify-artifact-bytes 100000000 --json
```

## What I am unsure about

- The check reads one monthly file at a time; checking a whole coin needed a script and 1,426
  runs. Filed as backlog `crypto-history-completeness` (one command per coin, gaps between files
  included).
