# Hand-off: daily-rule approval binding gap, and the daily price reader over many months

## For the owner

- **Done.** The daily rule study's approval now covers 15 more program files: the three you
  knew about, six found while planning, and six found by the review. A test fails if a new file
  appears without being covered or given a written reason.
- **Many months.** A daily-rule study can be drafted on a snapshot of many monthly Binance files.
  Name one stored copy per month with `--normalized-manifest-id` (repeat it). Proved on a copy of
  your data folder: the 36 BTCUSDT months of 2020-2022 give all 1,096 days. The result is the same
  in any order. Leaving a month out is refused.
- **One-month snapshots** give exactly the same result as before (pinned by a test).
- **Cost:** every pending daily-rule approval stops verifying once. None existed (checked
  read-only, below). Research approvals and synthetic rule approvals are unaffected.

## For you to decide

1. **Packages the lane uses but approvals do not cover.** These are `alpha_validation` (it makes
   the daily run's tearsheet files) and `alpha_research` (loaded by the rule protocol). Covering
   them would mean every behavioural edit to those packages also voids daily-rule approvals. While
   no daily-rule approval exists, deciding later costs nothing extra.
2. **`research_cmds.py`.** This command file holds the daily pilot's own approval-drift check, and
   approvals do not cover it. Same trade-off: it is a large, often-edited file.

## What I found that is not mine

The Dell's data folder now holds two new things, both created by another session at about 19:37
on 2026-11-14:

- a control store (`/home/hunta/alpha-clean-base/data/control/workstation.sqlite3`);
- the same 36-month BTCUSDT 2020-2022 snapshot (`561a39bf…8b95`).

Read-only inspection shows the control store holds one generic research contract (no daily-rule
protocol, no review events). It holds no daily-rule approval. Nothing there was changed by this
task. This task's own writes went only to the copy `/home/hunta/alpha-clean-base/tmp/data-proof-daily`.

## Follow-ups

- Optional: the V2 study validator accepts at most 100 members while the reader accepts 200; the
  study range (36 months) is far inside both.
- `scripts/handoff.py`: a plan cannot both change a file already in the size baseline and stay
  under 1,500 lines; the first Codex round stopped on that question (plan clarified, line-neutral
  edit).
