---
owner: web backend
sources:
  - apps/alpha-web/src/alpha_web/*.py
  - apps/alpha-web/src/alpha_web/api/**
  - tests/unit/test_web_*.py
  - tests/integration/test_web_api_*.py
verified: 492ffa489529401e
---

# Web API reads and writes invariants

What the Workstation backend reads, writes and relays. The other backend rules are in [web-api.md](web-api.md).

## Reads and writes

- Never open the CLI's SQLite control store (`control/workstation.sqlite3`) from web code. Read control-plane state
  through `alpha ... --json`. `_activity.py` only stats the file and its `-wal`/`-shm` sidecars to detect change.
  The one in-process writer is the owner-auth seam, which records challenges and receipts in the control store.
- Read runs only through bounded seams (`alpha_cli.run_store`, `artifact_contract.verify_manifest_artifacts`,
  `run_projection`). Operational state needs its own governed public seam — do not scan `RUN_DIRS` for it.
- Read paper state only through `alpha_cli.paper_store` / `paper_readiness`. Starting or stopping a paper node is a CLI
  job, never an in-process call. [ADR-0002](../../adr/0002-cli-sole-composer-subprocess-surfaces.md)
- The only file the web code writes itself is a named workspace, `data_dir/web/workspaces/<slug>.json` (atomic write through
  `alpha_core.atomic`, slugified name). It is presentation state with no research or execution authority.
- Never reconstruct trading evidence or compute metrics in the backend; relay what the CLI and artifacts record.
- RD-Agent GETs read bounded receipt/ledger/round/evaluation files; IDs select listed folders, never paths; raw fields are allowlisted/redacted.
  Tasks join trials by evaluation number/name/hash, never loop count; conflicts fail loud; unlinked counts stay unknown; empty dead rounds are disclosed.
  The run detail lists journey availability by evaluation number, name and full code hash. Indexed ideas can be unbuilt after a filtered CLI build.
  GET `/api/rdagent/runs/{run_id}/journeys/{idea_id}` returns the stored document or the quoted CLI command for a missing journey.
  Its `/figures/{filename}` GET serves listed PNGs only. Both check identity and refuse symlinks. Source paths are display text. The server never builds.
- Setup Lab's GET `/api/setup/runs`, `/{find_id}` and `/{find_id}/sheets/{kind}/{number}` use `_setup_runs` only:
  bounded, allowlisted reads, no CLI run. `setups/<id>/` files
  (`manifest.json`, `spec.json`, `summary.json`, `candidates.parquet`, `sheets/*.png`) and the linked `setup-studies/`, `setup-trades/`
  manifests, summaries, rows and PNGs, plus `ledger/trials.jsonl`, are shown as stored. Missing files stay null; corrupt, linked or
  oversized files fail with 422. Trade rows pass through direction, initial risk fraction and R when recorded. Older rows keep missing values.
  Price snapshots and portfolio totals remain unrecorded.
- Run labels are server-side: `_runs.display_name` builds `<strategy> <bar> — <symbol> · <source> · <first → last> · run
  <8 hex>` from the manifest (`<bar>` from its `timeframe`: `M5`, `H1`, ..., `D1` when absent; the period
  shows times when the curve has several points a day) and omits any part it does not record; `market_of` decides
  crypto/equities or `unknown`; the equity sources include `alpaca`.
  Identity fields (symbol, symbols, label, snapshot id) are read from the manifest top level first, then its `metadata`.
- A rule test is a run whose manifest has a `spine` key (`alpha test`). `_rule_test.py` projects it as `RunDetail.rule_test`
  (and `RunListItem.rule_test_labels`) from the run's own `manifest.json` and `diagnostics.json` only: values pass
  through, nothing is recomputed, a missing part is null and a missing or unreadable file is null with a reason. The
  rule's one-sentence wording is built server-side from the stored rule and is null for an unknown rule kind. Its
  display name puts `rule test <spec name>` in the strategy slot. Every other run has `rule_test: null` and is unchanged;
  `run_context_*` keeps its meaning for all runs. Enforced by `tests/integration/test_web_api_rule_test.py`.
- The `/api/ml` models accept the Alpha158 feature recipe v3 (`MlUpstreamAlpha158`, all 158 upstream Qlib columns, processors
  `qlib_processors_v3`) next to v1 and v2; the API only relays what the Qlib worker recorded.
  [ADR-0042](../../adr/0042-qlib-worker-delegates-data-layer-to-upstream.md)

## Reading reads

- GET `/api/runs/{id}/checks` carries the run's `reading` (`AlphaReadingV1`) and the CLI's `counts` line, both from
  `alpha results show --json`. The reading is stored for a new run and derived by the CLI for an old one.
- Each check carries the CLI's `status` (declared or exploratory). Nothing is derived here
  ([test](../../../tests/integration/test_web_api_reading.py)).
- Setup Lab: each outcome carries `reading`, relayed from one `alpha setup show <id> ... --json` call per find (`_setup_runs.py`):
  the evidence word, or the old word
  mapped to it with `old_wording`, and its place in the setup's family. The CLI computes it; the web keeps no copy
  ([test](../../../tests/integration/test_web_setup_reading_cli.py)).
- The family-adjusted figure is the CLI's alone. The screen says so in one muted line.
- `RunListItem.evidence` is the evidence word (or `fault`) a new run stored in its manifest `reading`; null for an older run.
  The list relays it and works nothing out.

## Market overview read

- `GET /api/market/overview` relays `alpha data market-overview --json` (`api/market.py`, 120 s timeout). The CLI reads stored bars only through
  `load_bars`, the point-in-time reader the chart uses. It writes nothing, reads no run, ledger or research result, and never uses the network. The
  web adds no second bar reader. Caps: 200 assets per store (name order) and the newest 400 bars each (`MAX_ASSETS_SCANNED`, `MAX_BARS_READ`); windows
  30, 90 or 365; 1 to 30 assets. "Top" assets rank by median close times volume over the window. An asset with too few bars, or one that cannot be
  read, is listed with its reason, never dropped. Enforced by `tests/unit/test_market_overview.py` and `tests/integration/test_web_api_market.py`.

## Follow today read

- `GET /api/follow/today` and `GET /api/follow/{id}` relay `alpha follow today|show --json` as a subprocess (`api/follow.py`, 30 s timeout). The web
  backend never opens the `forward/` folder ([guard](../../../tests/unit/test_follow_separation.py)). The id must match 4 to 12 lowercase hex characters
  before any command is built. A command failure is a 409 with its text; a timeout is a 504. No route starts, updates or stops a follow.
  Enforced by `tests/unit/test_web_follow_routes.py` and `tests/integration/test_web_api_follow.py`.
- `GET /api/ideas` relays `alpha idea list --json` as a subprocess (`api/ideas.py`, 30 s timeout; 409 on a failure, 504 on a timeout).
  No route writes a card.
- `GET /healthz` returns `status`, `code_commit` (the running code), `build_commit` and `build_time`
  (from the built bundle's `build-info.json`); `unknown` when absent.
