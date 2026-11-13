# Storage settings and the free-space reserve

ALPHA keeps market data under one data folder. Before it writes data there it checks that enough
disk space would be left over afterwards (the **reserve**). If not, it refuses before writing
anything, so a download cannot die half-way on a full disk.

- **Default** ([ADR-0032](../adr/0032-governed-crypto-data-house.md)): the reserve is the larger
  of 15% of the disk and 100 GB. It applies whenever you have not set your own value.
- **Your own value** ([ADR-0043](../adr/0043-storage-reserve-is-owner-set.md)): you may set a
  lower reserve for one data folder. It must name who decided and when, and it can never be
  below **10 GB**. You also set an advisory "low space" level that only warns.

The settings live in `<data folder>/crypto/storage-config.json` on the machine (not in the
repository). A filled-in example for the Dell is
[`dell-storage-settings.example.json`](dell-storage-settings.example.json); do not copy it by
hand, because the disk identity numbers are read from the machine by the command below.

## The Dell (owner decision of 2026-11-14)

Reserve 10 GB, advisory 20 GB. From the repository folder, with your chosen data folder
(`/home/hunta/alpha-data` below is a suggestion; it must not be under `/tmp`):

```sh
mkdir -p /home/hunta/alpha-data/bulk
# 1. Dry run: prints the settings it would write, writes nothing.
uv run python scripts/storage_settings.py write --data-dir /home/hunta/alpha-data \
  --bulk-root /home/hunta/alpha-data/bulk \
  --durable-hosting-reference "Dell internal disk /dev/sda2 (ext4); owner decision 2026-11-14; not backed up" \
  --reserve-gb 10 --advisory-gb 20 \
  --decided-by owner --decided-on 2026-11-14 \
  --decision-record "ADR-0043; owner chat 2026-11-14: use the Dell's available disk for now"
# 2. The same command with --apply writes it and reads it back through ALPHA's own checks.
# 3. Check at any time:
uv run python scripts/storage_settings.py show --data-dir /home/hunta/alpha-data
ALPHA_DATA_DIR=/home/hunta/alpha-data uv run python scripts/gate.py doctor
```

`write` never changes an existing disk identity or an existing reserve; to change a reserve,
edit the file deliberately and record the new decision. Changing the file changes its checksum, so
a daily study frozen against the old file refuses to start until it is drafted again.

## What still refuses, and what only warns

- **Refuses:** any data write that would leave less than the reserve
  (`alpha crypto-data` acquisition and `storage` checks report `bulk_storage_reserve_blocked`
  with the free space, the request, the reserve and who set it).
- **Warns:** below the advisory level, `alpha crypto-data storage` starts its next step with
  `LOW DISK SPACE`, and `scripts/gate.py doctor` shows the same in its
  "storage free-space advisory" line. The doctor line never fails the doctor.
- **Not checked:** the daily study launch checks the storage identity and the frozen settings
  file, not free space. The QuantPad archive keeps its own separate 15%/100 GB reserve.
