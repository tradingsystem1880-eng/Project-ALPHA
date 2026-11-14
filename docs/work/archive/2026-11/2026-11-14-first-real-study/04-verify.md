# Verification: walking both candidates with the installed program

Every command below was run on the Dell on 2026-11-14 with `uv run alpha ...` from the main
checkout (`/home/hunta/alpha-clean-base/Project-ALPHA`) unless a line says otherwise. No
approval, admission, confirmation or promotion was made by an agent; no stored data was deleted
or rewritten; no outcome of either hypothesis was computed or looked at.

## Candidate A: cross-sectional 3-week momentum across the 15 coins

Walked on a throwaway data folder (scratch), because stage 01 touches no data and a case blocked
in triage cannot be closed (it would stay in the real store for good).

| Step | Command | Result |
|---|---|---|
| 01.1 | `research list --json` | empty |
| 01.2 | `research capture "<the pre-registered sentence in 01-brief>" --name ... --json` | case created, phase `triage`, blocker "No registered research operator matches this observation." |
| 01.3 | (read the triage contract) | `gate1_availability: UNAVAILABLE`, three blocking questions with no choices, `valid_answer_bundles: []` |

Stop, by design ([stage 01, step 4](../../../../../research/stages/01-idea/CONTEXT.md)). The only
registered operators are the double bottom (synthetic SPY, Tiingo SPY daily), the Bybit BTCUSDT
crowding reversal and the fixed Packet 3 daily rule. A governed cross-sectional or daily-bar case
needs a new reviewed operator: [backlog item](../../../../roadmap/backlog/daily-research-operators.md),
size L, ADR needed. Not a defect to patch here.

## Candidate B: Packet 3 on the real bars

Real data folder `ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data`.

| Step | Command | Result |
|---|---|---|
| storage | `crypto-data storage --json --metadata-only` | `state: ready`, backend `cloud_root_identity`, reserve 10 GB set by the owner (ADR-0043), 45.9 GB free |
| data | `crypto-data coverage --json --metadata-only` (metadata only) | 36 qualified BTCUSDT 1d monthly manifests for 2020-01 to 2022-12, 1,096 rows; ids listed in the [handoff](05-handoff.md) draft command |
| snapshot | `crypto-data snapshot-create --manifest-id ×36 --json` | new frozen snapshot `561a39bf1eb555ced3ea9931b1c401f204d2b95beec2d81919d5ede5b3958b95`, 36 members (a new file; nothing existing changed) |
| check | `crypto-data snapshot-verify 561a39bf… --required-family market_bars --json` | `eligible: true`, no blockers |
| image | `python workers/rdagent/qualify_daily_container.py --image-id sha256:ae4e8b7c…` | wrote the ignored `.alpha/state/runtime/daily-container.json` in the main checkout (image was already local) |
| 01 | `research capture "<Packet 3 sentence>" --name "Packet 3: BTC 20-day momentum vs buy-and-hold, 2020-2022" --json` | case `dc74ae53-a9cb-5aa8-8a92-7662de27c96f`, phase `triage`, blocker "No registered research operator matches" (expected for this lane; the daily lane does not use answer bundles) |
| 01 | `research sources add` ×2 (Moskowitz, Ooi, Pedersen 2012 by DOI, metadata only; the Packet 3 plan) | `rs_317da768…`, `rs_7deb52b0…` |
| 01 | `research sources freeze dc74ae53… --source-id ×2 --json` | pack `sp_0c80bcc6f0c1fb1ed4ada95c3fcf8772c5638d2b8e957279d8ba336d1053a9d4` |
| 02 | `research draft-daily dc74ae53… --source-pack-id sp_0c80… --snapshot-id 561a39bf… --normalized-manifest-id <2020-01> --json` | refused: "price query requires exactly one frozen price member"; no contract written |

The last refusal is the known gap the `wt-daily` change closes (the daily price reader reads one
month per snapshot; it also adds acceptance of Binance monthly archive captures, which all real
bars on the Dell are). The draft is therefore regenerated after that change lands
([handoff](05-handoff.md)).

## Defects found

1. **Not a defect (withdrawn).** A first reading suggested a bare `alpha research approve
   exploration` of a rule contract would record the review and strand the case. The builder's
   test-first run showed `ControlStore.review_research_contract` already refuses it (no review,
   phase unchanged; message "fixed rule approval requires one exact consumed owner
   confirmation"). The planned code change was stopped; the rule is now written down instead.
2. **The research stage documents do not mention the daily rule lane.** Stage 02 never names
   `draft-daily`, and says the command-line approval works for every contract. Fixed in this
   task's pull request (stage 02 note; cli-native invariant).
3. **One month per snapshot in the daily reader**, and monthly archive captures not accepted:
   already being fixed by `wt-daily` (not duplicated here).

## Rehearsal of the after-approval path

There is no command an agent may use to approve, even in a throwaway store (the owner commands
are blocked for agents everywhere). The rehearsal is therefore the daily-lane test suite, which
records approvals inside the test, in throwaway folders, on the artificial 1,096-day fixture (not
the real bars), with the real pinned RD-Agent source and the real locked Docker image:

```sh
ALPHA_RDAGENT_SOURCE=/home/hunta/alpha-clean-base/Project-ALPHA/.alpha/state/runtime/rdagent-source \
  uv run python scripts/run_owned_test.py -- uv run pytest -q -n 0 -rs \
  tests/unit/test_native_daily_rule_lifecycle.py tests/unit/test_daily_native_cli.py \
  tests/unit/test_native_daily_rule_admission.py tests/unit/test_native_daily_rule_container.py \
  tests/unit/test_daily_rule_costed_worker.py tests/unit/test_native_daily_rule_study.py
```

On `origin/main` 947d911e (worktree `wt-study`): 128 passed, 1 failed, 12 min. The passes include
the public `run pilot` and `run deep` commands, an actual native run that completes, publishes
and reopens identical evidence, cancellation, and changed-guard refusal.

The failure, `test_daily_owner_sigkill_leaves_bounded_container_and_quarantines_exposure`, failed
again 3 of 3 times alone (machine load about 7 from other agents). The container is created but
stays in Docker state `Created` and the run never records `native_started` within the test's
15-second window; each failed run also left its never-started container behind (three removed by
hand with `docker rm`). This test covers a killed owner process, not the normal path, but a
container that is created and not started, and is not cleaned up, is a defect. Root cause not
found here; handed back to the orchestrator.
