# Daily-rule approval binding gap, and the daily price reader over many months

## What the owner wants

Two changes the owner agreed to on 2026-11-14, passed on by the orchestrating session. Both touch
files that daily-rule owner approvals are bound to, so they ship in one pull request and pending
daily-rule approvals are invalidated once, not twice.

1. **Close the daily-rule binding gap.** `DAILY_GUARD_FILES`
   (`apps/alpha-cli/src/alpha_cli/_native_rule_environment.py`) is the set of `alpha_cli` files
   whose code a daily-rule approval is bound to. The control-store split plan
   ([control-store-split.md](../../../../roadmap/refactors/control-store-split.md), "Existing gap")
   names three files the lane depends on that are missing: `_control_schema.py`,
   `_ml_observation_store.py`, `_native_daily_rule_history.py`. Verify that, find any other file
   the lane's behaviour depends on that is unbound, bind what the lane runs through, and add a
   test so the gap cannot silently reopen.
2. **The daily price reader reads multi-month crypto snapshots.** A governed crypto snapshot may
   hold many months of many coins
   ([ADR-0046](../../../../adr/0046-crypto-snapshot-members-are-content-addressed.md)), but
   `crypto_price_snapshot_query.py` reads exactly one member. Make it read every month of the
   requested instrument and range: point-in-time safe, strictly ordered, gaps and overlaps fail
   loud, deterministic, and identical output to today for a single-month snapshot.

In one sentence: every `alpha_cli` module the daily rule lane runs through is bound to its
approvals (or recorded as reviewed and outside), and a daily-rule study can be drafted over a
multi-year snapshot of monthly Binance archives, such as the ones on the Dell.

## What done looks like

- The nine `alpha_cli` modules the lane runs through but did not bind are in `DAILY_GUARD_FILES`
  (the three named, plus six found by tracing imports); a test fails when a bound module imports
  an `alpha_cli` module that is neither bound nor listed as reviewed-outside with a reason.
- For each newly bound file, a test shows a logic edit changes the daily code hash and a
  comment-only edit does not.
- `query_binance_daily_price_snapshot` reads one named normalized manifest per month member,
  in canonical order, refusing overlaps, missing months, duplicates, unnamed in-range members
  and other coins; one named manifest gives exactly today's document (pinned hash).
- Binance monthly archive captures (`binance-public-archive-v1`), which is what all real crypto
  data on the Dell is, are accepted under a closed rule next to the existing REST rule.
- `alpha research draft-daily` takes `--normalized-manifest-id` once per month.

## How they will see it

```sh
uv run alpha research draft-daily <project-id> --source-pack-id … --snapshot-id <36-month snapshot> \
  --normalized-manifest-id <2020-01> … --normalized-manifest-id <2022-12>
```

Every pending daily-rule approval stops verifying once and must be re-drafted and re-approved.
None exists today (checked: no control store in `/home/hunta/alpha-clean-base/data` or the
default data folder).

## Out of scope

Approving, promoting or re-approving anything; editing stored data; the RD-Agent worker
(`workers/rdagent`, another agent's area) and `alpha_research` rendering (another agent's
area); binding packages below `alpha_cli` or `research_cmds.py` (reported as remaining gaps);
mixed archive-plus-REST captures and daily archive files; widening the lane beyond BTCUSDT.
