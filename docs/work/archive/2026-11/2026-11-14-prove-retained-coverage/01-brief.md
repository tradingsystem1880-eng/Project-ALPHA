# Prove the "Are my downloaded daily bars complete?" check end to end

## What the owner wants

From the owner's direction of 2026-11-14 ("All 31 unproven features. Prove, built, implement,
improve all of them. 1 by 1."), passed on by the orchestrating session: run `retained-coverage`
from start to finish through the installed `alpha` (and its Workstation route), offline against
the recorded provider and for real on the Dell's Binance history, fix what that run finds, and
add the smoke check that lets it become Working.

## What done looks like

- A smoke check downloads a complete month and a month with a missing day through the recorded
  provider with the installed `alpha`, and the check reports the complete month as complete
  (exit 0) and the missing day exactly (exit 1), without any provider call or write. The installed
  `alpha-web` gives the same answer through its API.
- Every real monthly file on the Dell is checked against its calendar month and the result is
  written down.

## How they will see it

```sh
uv run alpha crypto-data quality <manifest-id> --coverage-start 2026-10-01T00:00:00Z \
  --coverage-end 2026-11-01T00:00:00Z --as-of 2026-11-14T00:00:00Z \
  --expected-cadence-seconds 86400 --max-verify-artifact-bytes 100000000 --json
```

## Out of scope

A check across many monthly files of one coin at once (backlog); the browser screen (already
covered by its Playwright journey against the real API); stored real data.
