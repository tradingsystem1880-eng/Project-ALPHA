# ADR-0010: Local Kronos weights + code-wired offline loading policy

**Status:** Accepted
**Date:** 2026-07-18
**Deciders:** AI build agents (per `CLAUDE.md`)

## Context

The platform should run its largest usable foundation model from local disk with **zero
Hugging Face network dependency** at inference: fully reproducible research on an
air-gapped-capable rig, no tokens (all Kronos repos are public MIT — anonymous download),
no silent hub fetch on a cache miss. Two facts shape the decision:

- **Kronos-large (499.2M) was never open-sourced.** `NeoQuasar/Kronos-base` (102.3M,
  512-token context, `Kronos-Tokenizer-base`) is the largest released model and is fully
  cached at `data/models/` in HF hub layout.
- The facade loads via `huggingface_hub.PyTorchModelHubMixin.from_pretrained`, which
  resolves a local cache **only** if pointed at one and hits the network otherwise.

## Decision

**Offline loading is a first-class, code-wired capability — kwargs through the facade,
never global env mutation.**

- `KronosForecaster` gains `cache_dir: Path | None` and `local_files_only: bool`, threaded
  into BOTH `from_pretrained` calls (tokenizer + model). `HF_HUB_OFFLINE`/`HF_HOME`
  mutation was rejected: process-global, invisible to type checking, untestable in-suite,
  and it would leak into unrelated code. Symlinking `data/models` into `~/.cache` was
  rejected as an untracked machine hack.
- `AlphaSettings` gains `forecast_hub_cache` (`ALPHA_FORECAST_HUB_CACHE`) and
  `forecast_local_only` (`ALPHA_FORECAST_LOCAL_ONLY`), defaults `None`/`False` (exact
  pre-ADR behavior). Only `alpha_cli` composes settings into the facade (ADR-0001/0002);
  no new CLI flags — model selection is env-only by convention, and cache location is
  machine config, not experiment config.
- **Fail loud offline:** with `local_files_only=True` and missing weights, the hub's
  `LocalEntryNotFoundError` is wrapped into a typed `DataError` naming id@revision, the
  cache dir, and the remediation — before any HTTP is attempted.
- **Identity boundary:** provenance blocks, run ids, and forecast signal-cache keys
  deliberately EXCLUDE `cache_dir`/`local_files_only`. Weight identity is
  `(model_id, revision)`; where the bytes sit on disk cannot change results for a pinned
  revision hash, and machine paths in manifests would break byte-stable manifests
  (spec §11.4). Same weights, different location ⇒ same run id, same signals.
- **Pinning convention:** the machine `.env` (git-ignored) pins `ALPHA_FORECAST_MODEL=
  NeoQuasar/Kronos-base`, `ALPHA_FORECAST_*_REVISION` to the exact HF commit hashes found
  in `data/models/*/refs/main`, `ALPHA_FORECAST_HUB_CACHE=data/models`,
  `ALPHA_FORECAST_LOCAL_ONLY=1`, `ALPHA_FORECAST_DEVICE=cpu` (bit-exact; mps opt-in per
  ADR-0008). `revision="main"` + local-only is legal but ambiguous (local refs can lag hub
  main) — pin hashes.

**Code anchors:**
- `alpha_forecast/kronos.py:KronosForecaster.{__init__,_load_predictor}` — kwargs + the
  `LocalEntryNotFoundError → DataError` wrap.
- `alpha_core/config.py:{forecast_hub_cache,forecast_local_only}`.
- `alpha_cli/_forecast.py:_forecaster_factory`, `forecast_cmds.py` (run/eval),
  `_forecast_cache.py:ensure_forecast_cache` — the three threading sites.

## Consequences

- `alpha forecast run/eval`, `alpha backtest run --strategy kronos`, `validate`, and
  `optim` all load Kronos-base purely from `data/models` and cannot touch the network on
  this machine; a missing/corrupt cache is a loud `DataError`, never a silent download.
- The `@network` live test and CI are untouched (defaults preserve hub behavior).
- A fine-tuned checkpoint still drops in as a local path via `ALPHA_FORECAST_MODEL`
  (ADR-0008); this ADR only governs cache-resolved HF ids.
- `.env` is CWD-scoped (pydantic-settings): invoking `alpha` outside the repo root
  reverts to code defaults — accepted, identical to the existing relative `data_dir`.
