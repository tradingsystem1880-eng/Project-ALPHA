# ADR-0042: The Qlib worker delegates its data layer to upstream Qlib

**Status:** Accepted (feature recipe v3 is opt-in; switching the default is an owner decision)
**Date:** 2026-11-14
**Deciders:** Project ALPHA owner and AI build agents

## Context

[ADR-0016](0016-isolated-qlib-worker.md) put Qlib in a separately locked worker,
`workers/qlib/` (package `alpha_qlib_worker`), behind an immutable JSON/Parquet exchange. That
worker has always installed and used the real Microsoft package, `pyqlib==0.9.7`: it trains with
upstream model classes (`qlib.contrib.model.gbdt.LGBModel`, linear, CatBoost, XGBoost,
DoubleEnsemble) and the upstream recorder. Nothing needs to be cloned; the installed wheel is the
upstream code.

What was hand-written is the data layer:

- `features.py` re-implements all 158 Alpha158 formulas (feature recipe v1, the default). It
  uses upstream's names and column order but not upstream's definitions. On a clean synthetic
  panel (`workers/qlib/tests/test_upstream_alpha158.py:parity_panel`, instruments without gaps)
  v1 differs from upstream after the 60-bar warm-up in 6 families (IMAX/IMIN/IMXD by up to 1.97,
  STD/VSTD sample-vs-population deviation, WVMA), its warm-up NaN masks differ in 28 families
  (full windows instead of upstream partial windows), and it ignores calendar gaps (positional
  rows instead of calendar positions). `VWAP0` is a typical-price proxy.
- Recipe v2 (opt-in, `native_feature_corrections.py`) replaced 40 columns (8 families x 5
  windows) with real `qlib.data.ops` operators through an in-memory `Expression` leaf; 118
  columns stayed hand-written.
- `real.py` re-implements normalisation (`_normalize_features`: train-median fill then z-score;
  `_normalize_label`: per-target population z-score) and feeds models through an in-memory
  dataset adapter.
- A separate demo, `apps/alpha-cli/src/alpha_cli/native_qlib_pipeline.py`, runs upstream `qrun`
  on fabricated data; it is not a production path.

The 2026-11-06 "native upstream first" intent
([area map](../context/alpha-quant-platform.md)) asks that installed upstream capability be used
before ALPHA writes its own.

## Decision

1. **One integration.** The `workers/qlib` worker is ALPHA's only Qlib integration. ADR-0016's
   isolation stays: the worker imports no ALPHA package, ALPHA imports no Qlib, and the exchange
   is the boundary.
2. **Feature recipe v3 delegates the data layer to upstream**
   (`workers/qlib/src/alpha_qlib_worker/upstream_alpha158.py`):
   - Feature names, order and expression strings come from
     `qlib.contrib.data.handler.Alpha158.get_feature_config`; every one of the 158 columns is
     computed by `qlib.utils.parse_field` + upstream `qlib.data.ops.OpsList` operators and cast to
     float32 as `LocalExpressionProvider.expression` does.
   - Fold normalisation runs `qlib.data.dataset.handler.DataHandlerLP` over
     `qlib.data.dataset.loader.StaticDataLoader` (`PTYPE_A`): `RobustZScoreNorm` (clipped) and
     `Fillna` on features, fitted on each fold's training rows only via upstream
     `check_transform_proc`; Alpha158's default learn processors `DropnaLabel` and
     `CSZScoreNorm` on the label. Upstream Alpha158's default infer list is empty; the feature
     processors are those of Qlib 0.9.7's published Linear Alpha158 benchmark, needed because
     the ridge member of the rank ensemble cannot take NaN inputs. Checked against the v0.9.7
     tag (`examples/benchmarks/*/workflow_config_*_Alpha158.yaml`): the LightGBM, XGBoost,
     CatBoost and DoubleEnsemble benchmarks keep the handler defaults (raw features, no
     clipping, no fill), and the Linear benchmark uses `CSRankNorm` on the label. v3 therefore
     matches upstream's features exactly but neither published processor set exactly: one
     matrix feeds both ensemble members, so the LightGBM member sees inputs clipped at three
     robust deviations with missing values set to zero. See "Open before v3 is the default".
   - Model fitting is unchanged (upstream model classes, the worker's in-memory dataset adapter).
3. **Mechanism: in-memory expression engine, not a temporary provider.** Considered:

   | | (a) panel fields as `Expression` leaves + upstream parser/ops | (b) dump to a temp file provider, `qlib.init`, real `Alpha158` handler |
   |---|---|---|
   | Upstream code exercised | config, parser, all operators, expression cache, float32 cast, processors and handler | the same plus provider/calendar/instrument loading and `QlibDataLoader` |
   | Glue | one leaf class, an operator namespace and the per-instrument loop (≈80 lines) | a bin-format writer (`scripts/dump_bin.py` is not in the wheel), calendar and instrument files |
   | Arbitrary / 24/7 calendars | panel sessions are the calendar | needs a written calendar; works |
   | Missing VWAP | proxy leaf | proxy bin file |
   | Global state | none (`qlib.init` never called; content-keyed cache) | `qlib.init` mutates process-global config and providers; conflicts with the worker's own recorder runtime |
   | Speed (this machine) | 0.34 s for 561 rows (v1: 0.31 s); 2.0 s for 20 x 760 rows (v1: 5.6 s) | not measured in production use; adds disk writes per request |

   (a) is chosen for production; (b) is the independent reference in the parity test, run in a
   separate process.
4. **VWAP: disclosed proxy, not refusal.** The canonical panel has no vendor VWAP; refusing would
   make v3 unusable on every ALPHA panel. The `vwap` leaf is the causal typical-price proxy
   `(high + low + close) / 3`; every v3 result names it in `vwap_source` and
   `upstream_alpha158.vwap` (`affected_columns: ["VWAP0"]`). This follows "no silent
   substitution": the substitution is explicit, scoped to one column and recorded.
5. **Proof.** `workers/qlib/tests/test_upstream_alpha158.py::test_v3_equals_upstream_provider_and_alpha158_handler_for_all_158_columns`
   compares v3 with upstream's own provider + `Alpha158` handler path on a panel with an
   irregular calendar, staggered starts, an instrument gap, zero volumes and a zero-range bar:
   all 158 columns are exactly equal, NaN positions included. `VWAP0` is formula parity on the
   proxy input. Further tests cover the training-only processor fit, causality, cache isolation
   and an end-to-end worker run; `tests/smoke/test_ml_smoke.py` runs prepare -> real worker ->
   import -> evaluate -> replay through the installed `alpha` program.
6. **Legacy v1/v2 frozen as readers.** `features.py`, `native_feature_corrections.py` and the
   v1/v2 normalisation stay byte-for-byte (golden digests in
   `workers/qlib/tests/test_feature_recipes.py`) so stored exchanges stay reproducible; they are
   labelled legacy. Stored feature-v1/v2 exchanges (`tests/fixtures/ml_exchanges/`) must keep
   validating. Refit protocols keep frozen inventories: `ml_refit._worker_source_names` is tiered
   7 -> 9 -> 10 files, and a ten-file protocol hash is not satisfied by older code.
7. **The `qrun` pipeline is a demo** ("Demo: upstream qrun on fabricated data — not a research
   path"), kept as is; its committed demo JSON no longer carries foreign absolute paths.
8. **Default stays v1** until the owner switches it after reviewing parity. Switching would change
   the bytes and `config_hash` of new default requests (old exchanges keep their recorded
   recipe), change feature values (upstream partial-window warm-up, sample deviations, calendar
   gaps as NaN, float32 precision), replace median-fill + z-score with robust z-score + clip +
   zero fill and the label z-score with pandas' sample deviation, make a label cross-section
   with fewer than two names or zero dispersion fail the run, and change the trained models and
   their scores. It needs no contract change.

## Open before v3 is the default

Processor choice per ensemble member. Upstream feeds tree models raw Alpha158 features and
linear models robust-normalised, clipped, filled ones with a ranked label. v3 gives both members
the linear feature set and the handler's default label z-score. Clipping and zero fill are not
neutral for trees: order inside the clipped tails is lost and "missing" becomes "typical". The
alternative is two inputs per fold (raw for LightGBM, processed for ridge), which changes the
fitting path and its provenance trace. This is decided by a side-by-side run on real data
(rank IC and its stability per fold, both ways), not by argument, and no result meant for an
owner decision uses v3 until it is. If the measurement changes the processors, v3 is amended in
place before it is declared the default rather than adding a fourth recipe.

## Consequences

- Easier: one claim that can be checked ("v3 is upstream Alpha158") with a parity test that
  fails if it stops being true; source pins fail closed if the installed Qlib differs.
- Harder: three recipes to keep readable; v3 and v1 results are not numerically comparable.
- Retiring v1/v2 later (owner decision) would let `features.py`, `native_feature_corrections.py`
  and the v1 normalisation helpers be deleted once no stored exchange needs reproducing.
- Not established: real-data or economic qualification, provider/corporate-action parity
  (ALPHA's panel is the input), vendor VWAP.
