# Crypto snapshot faults from the first real data run

## What the owner wants

From the hand-off of the first real data run on the Dell
([05-handoff.md](../2026-11-14-free-real-data-dell/05-handoff.md), "What I am unsure about"),
passed on by the orchestrating session on 2026-11-14: the faults the first real run found in the
governed crypto store must be fixed, each reproduced first with a failing test; "every fault must
fail loud, never pass quietly". Five faults:

1. Downloading one month twice left two identical copies; `snapshot-create` accepted a snapshot of
   that month but `snapshot-verify` refuses it as ambiguous.
2. Because of that, the whole-store check `alpha crypto-data storage-verify` fails on the real
   data folder, and snapshots cannot be deleted.
3. The backfill records a failure for the unfinished current month, which Binance cannot have
   published yet.
4. A crypto snapshot seemed to hold only one month of one coin, so a multi-year study through the
   governed crypto path looked impossible.
5. The `stooq` downloader gets past the site's "verify your browser" check by itself.

In one sentence: creation and verification of crypto snapshots follow one strict rule, the real
data folder verifies cleanly again through a legitimate path, unfinished months are reported as
not published yet, snapshots can hold many months, and no ALPHA code gets past a bot check.

## What done looks like

- A snapshot that can be created can always be verified; two byte-identical downloads of one file
  never break a snapshot, and any real difference between them fails loud.
- `alpha crypto-data storage-verify` passes on `/home/hunta/alpha-clean-base/data` with no receipt,
  manifest or snapshot edited and nothing deleted.
- A backfill run never writes a failure for a month that has not ended.
- Snapshot identity does not depend on the order manifests are named in.
- The `stooq` downloader refuses when challenged; the data-layer page records that, and that
  Yahoo's terms forbid automated collection.

## How they will see it

```sh
export ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data
uv run alpha crypto-data storage-verify --json
uv run alpha crypto-data snapshot-verify c8ab0d2a0ad8b0faff797569521c16b1aa7f615e9d80a3818a92b95e1f5f6226 --json
```

## Out of scope

Deleting or editing any stored data; Binance daily archive files; changing the daily rule lane's
one-month price reader (it is bound to owner approvals); deleting the `yfinance` downloader;
keyed providers; research approvals.
