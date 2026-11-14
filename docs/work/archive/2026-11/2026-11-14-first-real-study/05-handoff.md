# Handoff: the owner's approval packet for the first real study

## Status

- **Candidate B (Packet 3) is prepared to its approval boundary except one engineering step.**
  The real case, its sources, the 36-month snapshot of real bars, the storage identity and the
  Docker image are ready. Drafting the exact contract waits for the `wt-daily` change (the daily
  price reader reads only one month per snapshot today, and does not yet accept Binance monthly
  archive captures). Once it is on `main`, the contract is drafted with the one command below and
  the packet is final.
- **Candidate A cannot be run by ALPHA today.** It is pre-registered in the [brief](01-brief.md);
  it needs a new research operator (backlog, size L) before any governed case can test it.

## The study in five lines (B)

1. Question: does a 20-day momentum rule on Bitcoin beat simply holding the same Bitcoin?
2. Data: Binance BTC/USDT daily bars, 1 January 2020 to 31 December 2022 (1,096 days), from
   Binance's free monthly archives; free data, labelled not yet confirmed.
3. Test: two 10,000 USDT accounts. The rule holds 0.05 BTC while today's close is above the close
   20 days earlier and is flat otherwise; the control buys 0.05 BTC once and holds it. Decided at
   each close, filled at the next open, by ALPHA's real backtest engine inside RD-Agent's loop.
4. Support or contradiction: the run reports both accounts' results (returns, drawdown, trades,
   fees). All 1,096 days are discovery; there is no sealed confirmation period, so the case can
   only close as INCONCLUSIVE (or INVALID), whatever the numbers say.
5. Costs: 10 bps commission per side, plus 2 bps spread and 5 bps slippage per side.

## What the owner approves

The exact exploration contract of case `dc74ae53-a9cb-5aa8-8a92-7662de27c96f` that the draft
command prints (`contract_id`). Approving lets the program run: one synthetic pilot (D0, three
launches at most) and one real comparison (at most 60 seconds, 1 CPU, 1 GiB, no AI model calls).
It does not admit any result as evidence, does not promote anything and cannot trade.

## Steps

Prepare (an agent can run this once `wt-daily`'s pull request has merged):

```sh
M=(
  a7ad2f1ee684dacc8bb52322727d682788bea6a0f8c9276a21b15610be9a9548
  dd343915bbec6e7e0040f62ce9c04f9507e54529eaec0266fc6732f251a0840e
  ec2f080dd7f83a194606cad2bdba1b4bbda23d1f1738573161bae910ac5789cd
  efae77085a545513c1d397f5ffd93ef6f4d4e2361a51aaa3c390d63aa9231d30
  313444d80b3a285f6a1899956025f0e5279037816f14d598ae37daaa76c1ae8a
  25190c2f2a99c920203e2b8fe2f2a0556555aa33335c33e09bda0a7317a504bd
  901e8c1747259439f12ba9427e8dac80edae9455ec108d4fb87850faaf24b7bc
  d55d3889cafd36f9ae1bdf21c28f45c5381453918049f995cf2204b6717bbe1b
  142f7ade076939bb70dd4146821a90a5235841b951b32784a40e50fa7d6c160d
  7ae5bfcf689a56372f99454b53cdef92ae83374ba765a273450a258adc9443f9
  330d6df6f6781e2129cca9db314543f2bf2b4a4dc50dd5e389c1c2dfcbd2d180
  ee2115971fa8e106c0c7bd381dfc4996f86b2087bcf86993eafa1476f73b7e93
  2702787ab9c820ae8e3e4b4a424a72a0468036977ab013acc8ec4b97c2eda5d7
  3781f692d9ddd4eb54024db88137e1fab971e9daf805259f432d384103ac3b13
  00ab3eddf0e911569e19435a49958ea739c0460896bb032b1b8daf64afae48d1
  91c2f18b1aec4db6e218a20146068eddbf25f8172c517c8f3475d8b2711aea91
  22b27d334452a37f9500f6ca7c8d8de07237a96da80a240c9c56ad6c2c31c40f
  bc68c8d5b77c0587abc30a6d2e7b66be4d74593c87e88fb51cd503e6544a435f
  eb5cd092e6fa199edbcd7295bb56e6440523ec128ab4f5a065fc35e86b47e865
  ed459230e8da70b3ec7d900c3528a9b4f316d12d139c8123fe05c28766ec8786
  6fc642e9a7f7369e1812e62c48b7cfb3a5aa0d2e33a96afe3e166a15d704df2c
  f28879a9e710c63753fd3688ff1e2e00bc4eca5c555392c240f0d68fededb5d2
  e0b2dda3061f30c0446490a5f83d221983b35d913f2403f6d1477eabe2380cc1
  1a8810cc6702aa193db80f0b437c1d410ebacc9616e674ffcdc3f6a40f0bac81
  00f686155efa4156a449f32c9b22a4cdc4178f4980e482204bdd41ab27d07395
  26c5375158b774d1374cdc83d6fd7ae9ac4b9461824008c8374294dda2963af4
  4a958a2e09824c87e77d8ad3189fd6167886fc7fb145afda3b628ed04fc8b976
  31404ef8f35d9c27a2ee2436c36a4479a7f934260dc463e9e2aa83a12077fb56
  9072fdd140c8b0423639762aa2ce178eaa3cd1252d20f1d6ad20d0fc297cf9ca
  4624a9870d477efcab9f97da94a4ca7884fd389cfc3325f5ffc0909a6b4d8022
  42d5910145d9a89846ee971dfff385d4d603218f3c1148457562a945b1876fa8
  dcb2fcbb6653520d5ee93730c77e1f8a6ac49637c3e2960552edba234baca4b6
  796d1ce5c307cdeff1603f96c0e6038343d3765e1d6da54aff16d9beb0d5485a
  1807cdefc4e34f033c62b5b0e3d6167344115b279cb91e2ed18989e1ec99b6d1
  a233abf80fd873e590e857dd15f3df3707e5ad147e09fbc3b63b9f09b2240314
  5a710733bf90382f8d94a7f3f8f6d03436c6beb2ae86fe5e2c205d8935098203
)  # BTCUSDT 1d, 2020-01 .. 2022-12, one per month in order
cd /home/hunta/alpha-clean-base/Project-ALPHA && git pull --ff-only \
  && bash scripts/setup_rdagent.sh --with-daily-container \
  && (cd apps/alpha-web/frontend && npm ci && npm run build) \
  && export ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data \
  && uv run alpha research draft-daily dc74ae53-a9cb-5aa8-8a92-7662de27c96f \
     --source-pack-id sp_0c80bcc6f0c1fb1ed4ada95c3fcf8772c5638d2b8e957279d8ba336d1053a9d4 \
     --snapshot-id 561a39bf1eb555ced3ea9931b1c401f204d2b95beec2d81919d5ede5b3958b95 \
     $(printf -- '--normalized-manifest-id %s ' "${M[@]}") \
     --json \
  && uv run alpha research export dc74ae53-a9cb-5aa8-8a92-7662de27c96f --json
```

Approve (owner only, in the Workstation; the command line cannot approve this kind of study):

```sh
cd /home/hunta/alpha-clean-base/Project-ALPHA
ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data uv run alpha-web
```

Open http://localhost:8801, open the research case "Packet 3: BTC 20-day momentum vs
buy-and-hold, 2020-2022", read the contract, choose Approve and confirm.

Run (no owner authority needed; about a minute):

```sh
export ALPHA_DATA_DIR=/home/hunta/alpha-clean-base/data
export ALPHA_RDAGENT_SOURCE=$PWD/.alpha/state/runtime/rdagent-source
uv run alpha research run pilot dc74ae53-a9cb-5aa8-8a92-7662de27c96f --json
uv run alpha research run deep dc74ae53-a9cb-5aa8-8a92-7662de27c96f --json
uv run alpha research status dc74ae53-a9cb-5aa8-8a92-7662de27c96f --json
uv run alpha research decision-view dc74ae53-a9cb-5aa8-8a92-7662de27c96f
```

It worked when `status` shows phase `research_decision` (or `deep_research` with a completed
attempt) and `alpha report <run_id> --daily-rule-evidence` prints both accounts. Then the owner
decides (`INCONCLUSIVE` with `park`, `revise` or `reject`), in the Workstation.

## What the approval is bound to

Any change to what these do invalidates the approval (comments and formatting do not; ADR-0045):

- `apps/alpha-cli/src/alpha_cli/`: every file in `DAILY_GUARD_FILES`
  (`_native_rule_environment.py`), which includes `control_store.py`, `owner_auth.py`,
  `crypto_price_snapshot_query.py`, `crypto_bulk_store.py`, `daily_native_cmds.py`; after
  `wt-daily` also `_control_schema.py`, `_native_daily_rule_history.py`, `_ml_observation_store.py`,
  `_native_rule_economics.py`, `_native_rule_study.py`, `job_capacity.py`, `paper_resources.py`,
  `run_store.py`, `run_context.py`.
- `workers/rdagent/`: `fixture_entry.py`, `source_pin.py`, `native_fixture.py`,
  `fixture_owner.py`, `conformance.py`, `admitted_probe.py`, `uv.lock`, `pyproject.toml`,
  `rule_probe.py`, `install_rule_profile.py`, `rule-requirements.lock`, `daily_container_entry.py`.
- By bytes: the root `uv.lock` and the source of `alpha-core`, `alpha-patterns` and
  `alpha-strategies` (through the measured rule runtime), the Docker image id, the storage
  settings file `data/crypto/storage-config.json`, the snapshot and its 36 monthly files.

So: hold the `control_store.py` split, and any behaviour change to the files above, until the run
has finished; do not edit the storage settings file.
