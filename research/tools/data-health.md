---
owner: data layer
sources:
  - packages/alpha-data/src/alpha_data/health.py
  - apps/alpha-cli/src/alpha_cli/spine/data_health.py
  - apps/alpha-cli/src/alpha_cli/_data_health.py
  - apps/alpha-cli/src/alpha_cli/data_cmds.py
verified: 247e46524b4c04b3
---

# Daily data health

**Reach for it when** you want to know whether a stored daily series has a known data fault before you test on it.

**Command** `uv run alpha data health SPY@home`. A symbol alone searches every registered store.
Add `--universe members.csv` (membership intervals) to check survivorship. `--json` adds thresholds and all dates.

**How to read it** Four groups come in order: adjustments, timestamps, gaps, survivorship.
Each group shows its worst status, then one sentence per check. The verdict is the worst status of all.
Statuses, best to worst: not-applicable (the check does not apply, such as splits for crypto), pass, warn and fail.
- Adjustments: an overnight jump near a split ratio with no recorded split warns, as does a real crash that matches a ratio; check by hand.
- Timestamps: time zone, order, midnight UTC stamps, closed-exchange days, unfinished bars, and data that stops early.
- Gaps: repeated or impossible bars, missing trading days, zero volume, a spike that reverses next day, a bar frozen for 5 bars while volume trades.
- Survivorship: needs a membership history; without one the list is survivors only.

**Saved report** Each check writes `health/<symbol>.json` in the store. `--stored` reads it back.
If any input byte changed since, it says "out of date" instead of the old verdict. Run it again without `--stored`.
**On a run** A rule test or a setup find, study or trade looks up this report for each series it reads.
It counts only if it was made from the same bytes. Each series is pass, warn, fail, out-of-date (bytes changed) or unchecked.
The run takes the worst: fail, out-of-date, unchecked, warn, pass. Its label is `data-health-<verdict>`;
out-of-date uses `data-health-unchecked`. The run makes no report itself unless you add `--check-data`, which makes
missing or out-of-date reports first; for a stock it compares up to 20 stock series in the same store and calendar.
A fail stops the run before any test work. Fix the data, or run again with `--accept-bad-data "reason"` (one command only).
The verdict covers all stored bars at the report time shown. Older runs read "Data health: not recorded."

**What it cannot tell you**
- A clean report only means these faults were not found. The prices can still be wrong.
- `alpha data health SYMBOL` compares no other series. Peers are used only under a run's `--check-data`.
- Prices are raw. It does not check dividends, which are separate cash events.
**Next** Check flagged dates against another source. RD-Agent panels remain the next integration.
