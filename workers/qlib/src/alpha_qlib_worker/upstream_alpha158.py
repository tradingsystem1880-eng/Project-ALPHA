"""Feature recipe v3: upstream Qlib Alpha158 features and processors over ALPHA's panel.

Every one of the 158 feature columns is computed by the installed pyqlib 0.9.7 code:

* the expression strings and names come from ``qlib.contrib.data.handler.Alpha158``'s own
  ``get_feature_config`` (which calls ``Alpha158DL.get_feature_config``);
* each string is parsed by ``qlib.utils.parse_field`` and evaluated against a private
  ``qlib.data.ops.OpsWrapper`` registered with upstream's ``OpsList``;
* values are cast to float32 exactly as ``LocalExpressionProvider.expression`` does.

The worker supplies only raw input series: one in-memory ``Expression`` leaf per panel field,
laid out on the panel's own session calendar the way a Qlib file provider stores an instrument
(dense from its first to last session, NaN where it has no row). No provider, calendar file,
``qlib.init`` or global operator registration is used, so 24/7 calendars work unchanged and no
state is shared between requests except upstream's content-keyed expression cache.

Fold normalisation uses upstream ``DataHandlerLP`` over a ``StaticDataLoader`` with upstream
processors: Alpha158's default learn processors (``DropnaLabel``, ``CSZScoreNorm`` on the
label) and ``RobustZScoreNorm`` + ``Fillna`` on features, fitted on the training segment only.

``$vwap`` has no vendor source in ALPHA's panel. The documented causal typical-price proxy
``(high + low + close) / 3`` is supplied as the ``vwap`` leaf and recorded in provenance; it
affects only ``VWAP0``.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import warnings
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl
from qlib.contrib.data.handler import _DEFAULT_LEARN_PROCESSORS, Alpha158, check_transform_proc
from qlib.data import ops
from qlib.data.base import Expression
from qlib.data.dataset.handler import DataHandlerLP
from qlib.data.dataset.loader import StaticDataLoader
from qlib.utils import parse_field

NATIVE_VERSIONS = {"pyqlib": "0.9.7", "pandas": "2.3.3", "numpy": "2.2.6"}
INPUT_FIELDS = ("open", "high", "low", "close", "volume", "vwap")
VWAP_SOURCE = "causal_typical_price_proxy_not_vendor_vwap"
VWAP_COLUMNS = ("VWAP0",)
# Alpha158's own default learn processors, copied at import and checked at run time.
LEARN_PROCESSORS: tuple[dict[str, Any], ...] = (
    {"class": "DropnaLabel"},
    {"class": "CSZScoreNorm", "kwargs": {"fields_group": "label"}},
)
# Upstream Alpha158's default infer list is empty, which leaves NaN features that linear models
# cannot take. These upstream processors are the configuration Qlib's published Alpha158
# benchmarks use for models that need normalised, complete inputs.
INFER_PROCESSORS: tuple[dict[str, Any], ...] = (
    {"class": "RobustZScoreNorm", "kwargs": {"fields_group": "feature", "clip_outlier": True}},
    {"class": "Fillna", "kwargs": {"fields_group": "feature", "fill_value": 0}},
)

# Installed-wheel source pins (pure Python, platform independent).
_SOURCE_PINS = {
    "data/ops.py": "6f648355725a85a9f17528d864281fc065f8a4f887261a9909f7495d5db42760",
    "data/base.py": "30382dd1a3c47506e61514f37533a3407f63fd01c9a9fd5a12b8c0cce85c5d5c",
    "data/cache.py": "11979d339727d41081d906e633d858c10e6066ccf584c441d4d4b8bb0b914080",
    "contrib/data/loader.py": "814b7f7ab3d418ae3c87ce352220080b239eba2670eac9e38376b794be4075cb",
    "contrib/data/handler.py": "b621481c6009c39066c67c71390fd2bea635f56daf9f2c4e38817eff268e3232",
    "utils/__init__.py": "59d6bd09bdac8a1f47c3939eccfc89094fc6161640af8c2c6ba7d18527581dbd",
    "utils/data.py": "f4f4df90a3fcf410df3225dec24cc2cbc8998c5b5c03c09b55f933f7668feb14",
    "data/dataset/processor.py": "424af44e81c99467171c2d0b7978fb9f95d3b4c8b743a535ff4fe45d708cf517",
    "data/dataset/handler.py": "8fc3732631bc5e199f8c925827fb0dc7775cfc4edcf3d16e2ac591ec71a4ae90",
    "data/dataset/loader.py": "9a3d784f2b8dc0cd535929f8b8db5ed6437b79b6330475d19feb293b64e30c60",
    "data/dataset/utils.py": "c556538a0de06597390001b2e9de361f87af11c96853c67ba9e8af4a88b40024",
}


def upstream_binding() -> dict[str, Any]:
    """Fail closed unless the installed Qlib is the inspected 0.9.7 source."""
    versions = {name: importlib.metadata.version(name) for name in NATIVE_VERSIONS}
    if versions != NATIVE_VERSIONS:
        raise RuntimeError("feature recipe v3 requires the pinned Qlib numerical dependencies")
    root = Path(ops.__file__).resolve().parents[1]
    hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in _SOURCE_PINS}
    if hashes != _SOURCE_PINS:
        raise RuntimeError("feature recipe v3 Qlib source differs from inspected upstream pins")
    if [dict(item) for item in _DEFAULT_LEARN_PROCESSORS] != list(LEARN_PROCESSORS):
        raise RuntimeError("upstream Alpha158 default learn processors changed")
    return {"versions": versions, "source_sha256": hashes}


def alpha158_config() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return upstream Alpha158's expression strings and names, in upstream order."""
    # get_feature_config uses no instance state; an uninitialised handler avoids any loading.
    fields, names = Alpha158.__new__(Alpha158).get_feature_config()
    result = tuple(str(field) for field in fields), tuple(str(name) for name in names)
    if len(result[0]) != 158 or len(set(result[1])) != 158:
        raise RuntimeError("upstream Alpha158 config does not define 158 unique features")
    return result


class _PanelField(Expression):  # type: ignore[misc]  # Upstream Expression is untyped.
    """A provider-shaped raw field: calendar-indexed values; upstream owns all operators."""

    def __init__(self, identity: str, field: str, values: pd.Series) -> None:
        self.identity, self.field, self.values = identity, field, values

    def __str__(self) -> str:
        return f"Alpha158V3Panel[{self.identity}:${self.field}]"

    def _load_internal(
        self, instrument: str, start_index: int, end_index: int, *args: object
    ) -> pd.Series:
        if instrument != self.identity or args != ("day",):
            raise RuntimeError("invalid in-memory feature identity or frequency")
        return self.values.loc[start_index:end_index].copy()

    def get_longest_back_rolling(self) -> int:
        return 0

    def get_extended_window_size(self) -> tuple[int, int]:
        return (0, 0)


class _Operators:
    """Upstream operator registry whose ``Feature`` resolves to this instrument's leaves."""

    def __init__(self, registry: Any, leaves: Mapping[str, _PanelField]) -> None:
        self._registry, self._leaves = registry, leaves

    def Feature(self, name: str) -> _PanelField:  # parse_field emits this name.
        if name not in self._leaves:
            raise RuntimeError(f"Alpha158 references unsupported field ${name}")
        return self._leaves[name]

    def __getattr__(self, name: str) -> Any:
        return getattr(self._registry, name)


def _require_finite(raw: pd.DataFrame) -> None:
    values = raw.loc[:, ["open", "high", "low", "close", "volume"]].to_numpy(dtype="float64")
    if not np.isfinite(values).all():
        raise RuntimeError("feature recipe v3 requires finite OHLCV input")


def upstream_alpha158_features(panel: pl.DataFrame) -> pd.DataFrame:
    """Build the ``(datetime, instrument) x 158`` matrix with upstream expressions only."""
    upstream_binding()
    fields, names = alpha158_config()
    registry = ops.OpsWrapper()
    registry.register(ops.OpsList)
    source = panel.to_pandas()
    if source.empty:
        raise RuntimeError("cannot build Alpha158 features from an empty panel")
    _require_finite(source)
    calendar = pd.DatetimeIndex(pd.Series(source["session_ts"]).drop_duplicates().sort_values())
    frames: list[pd.DataFrame] = []
    for symbol, raw in source.groupby("symbol", sort=True, observed=True):
        raw = raw.sort_values("session_ts", kind="mergesort")
        positions = calendar.get_indexer(pd.DatetimeIndex(raw["session_ts"]))
        first, last = int(positions.min()), int(positions.max())
        dense = raw.set_index("session_ts").reindex(calendar[first : last + 1])
        dense["vwap"] = (dense["high"] + dense["low"] + dense["close"]) / 3.0
        index = pd.RangeIndex(first, last + 1)
        # A Qlib provider stores float32; the leaf holds exactly what a dumped provider would.
        stored = {
            field: pd.Series(dense[field].to_numpy(dtype=np.float32), index=index)
            for field in INPUT_FIELDS
        }
        digest = hashlib.sha256(b"alpha158:3:qlib-0.9.7\0" + str(symbol).encode() + b"\0")
        digest.update(np.asarray(positions, dtype="<i8").tobytes())
        for field in INPUT_FIELDS:
            digest.update(stored[field].to_numpy(dtype="<f4").tobytes())
        identity = digest.hexdigest()
        operators = _Operators(
            registry, {field: _PanelField(identity, field, stored[field]) for field in INPUT_FIELDS}
        )
        columns: dict[str, np.ndarray[Any, Any]] = {}
        with warnings.catch_warnings(), np.errstate(divide="ignore", invalid="ignore"):
            warnings.simplefilter("ignore", RuntimeWarning)
            for field, name in zip(fields, names, strict=True):
                expression = eval(  # upstream's own parse/eval of fixed strings.
                    parse_field(field), {"__builtins__": {}, "Operators": operators}
                )
                # Upstream's own window bookkeeping: no Alpha158 expression may look ahead.
                if expression.get_extended_window_size()[1] != 0:
                    raise RuntimeError(f"Alpha158 expression {name} reads future rows")
                series = expression.load(identity, first, last, "day")
                series = series.astype(np.float32)  # as LocalExpressionProvider.expression
                if not series.index.equals(index):
                    raise RuntimeError("Qlib operator changed the calendar row index")
                columns[name] = series.to_numpy(copy=True)
        frame = pd.DataFrame(columns, index=calendar[first : last + 1])
        frame = frame.loc[pd.DatetimeIndex(raw["session_ts"])]
        frame["instrument"] = str(symbol)
        frame.index.name = "session_ts"
        frames.append(frame.reset_index().set_index(["session_ts", "instrument"]))
    result = pd.concat(frames).sort_index(kind="mergesort")
    result.index.names = ["datetime", "instrument"]
    return result.loc[:, list(names)].astype("float64")


def processor_configuration(
    fit_start_time: pd.Timestamp, fit_end_time: pd.Timestamp
) -> dict[str, list[dict[str, Any]]]:
    """Upstream ``check_transform_proc`` binds the fit window into fit-aware processors."""
    # Deep copies: check_transform_proc updates the kwargs mappings it is given in place.
    return {
        "infer": check_transform_proc(
            copy.deepcopy(list(INFER_PROCESSORS)), fit_start_time, fit_end_time
        ),
        "learn": check_transform_proc(
            copy.deepcopy(list(LEARN_PROCESSORS)), fit_start_time, fit_end_time
        ),
    }


def _json_config(config: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "class": str(item["class"]),
            "kwargs": {
                key: (value.isoformat() if isinstance(value, pd.Timestamp) else value)
                for key, value in dict(item.get("kwargs", {})).items()
            },
        }
        for item in config
    ]


def upstream_fold_frames(
    train: tuple[pd.DataFrame, pd.Series],
    validation: tuple[pd.DataFrame, pd.Series],
    test: pd.DataFrame,
) -> dict[str, Any]:
    """Process one fold through upstream ``DataHandlerLP``; fit on training rows only."""
    upstream_binding()
    train_x, train_y = train
    valid_x, valid_y = validation
    names = list(train_x.columns)
    if list(valid_x.columns) != names or list(test.columns) != names:
        raise RuntimeError("fold feature columns differ between segments")
    train_dates = train_x.index.get_level_values("datetime")
    fit_start, fit_end = pd.Timestamp(train_dates.min()), pd.Timestamp(train_dates.max())
    for label, frame in (("validation", valid_x), ("test", test)):
        if frame.index.get_level_values("datetime").min() <= fit_end:
            raise RuntimeError(f"{label} rows overlap the normalisation fit window")
    segments = [
        (train_x, train_y),
        (valid_x, valid_y),
        (test, pd.Series(np.nan, index=test.index, dtype="float64")),
    ]
    raw = pd.concat(
        [
            pd.concat({"feature": features, "label": labels.to_frame("LABEL0")}, axis=1)
            for features, labels in segments
        ]
    ).sort_index(kind="mergesort")
    if raw.index.has_duplicates:
        raise RuntimeError("fold segments share a (datetime, instrument) row")
    configuration = processor_configuration(fit_start, fit_end)
    with warnings.catch_warnings(), np.errstate(divide="ignore", invalid="ignore"):
        warnings.simplefilter("ignore", RuntimeWarning)
        handler = DataHandlerLP(
            data_loader=StaticDataLoader(raw),
            infer_processors=configuration["infer"],
            learn_processors=configuration["learn"],
            process_type=DataHandlerLP.PTYPE_A,
        )
        learn = handler.fetch(col_set=["feature", "label"], data_key=DataHandlerLP.DK_L)
        infer = handler.fetch(col_set=["feature", "label"], data_key=DataHandlerLP.DK_I)
    normalizer = next(
        processor
        for processor in handler.infer_processors
        if type(processor).__name__ == "RobustZScoreNorm"
    )

    def select(frame: pd.DataFrame, index: pd.Index, group: str) -> pd.DataFrame:
        if not index.isin(frame.index).all():
            raise RuntimeError("upstream processors dropped rows from a fold segment")
        selected = frame.loc[index]
        return (
            selected.loc[:, selected.columns.get_level_values(0) == group]
            .droplevel(0, axis=1)
            .astype("float64")
        )

    def processed_labels(raw_labels: pd.Series) -> pd.Series:
        processed = select(learn, raw_labels.index, "label")["LABEL0"]
        processed.name = raw_labels.name  # keep the legacy series identity for provenance
        return processed

    outputs: dict[str, Any] = {
        "train_features": select(learn, train_x.index, "feature"),
        "validation_features": select(learn, valid_x.index, "feature"),
        "test_features": select(infer, test.index, "feature"),
        "train_labels": processed_labels(train_y),
        "validation_labels": processed_labels(valid_y),
    }
    for name in ("train_features", "validation_features", "test_features"):
        frame = outputs[name]
        if list(frame.columns) != names:
            raise RuntimeError("upstream processors changed the feature column order")
        if not np.isfinite(frame.to_numpy(dtype="float64")).all():
            raise RuntimeError("upstream feature processing produced non-finite values")
    for name in ("train_labels", "validation_labels"):
        labels = outputs[name]
        bad = labels.index.get_level_values("datetime")[~np.isfinite(labels.to_numpy())]
        if len(bad):
            raise RuntimeError(
                "upstream CSZScoreNorm produced non-finite labels (a cross-section with fewer "
                f"than two labels or zero dispersion) at {sorted({str(t) for t in bad})[:5]}"
            )
    center = np.asarray(normalizer.mean_train, dtype="float64")
    state = {
        "method": "qlib_processors_v3",
        "fit_start_time": fit_start.isoformat(),
        "fit_end_time": fit_end.isoformat(),
        "process_type": DataHandlerLP.PTYPE_A,
        "infer_processors": _json_config(configuration["infer"]),
        "learn_processors": _json_config(configuration["learn"]),
        "robust_center": [None if np.isnan(value) else float(value) for value in center],
        "robust_scale": [
            None if np.isnan(value) else float(value)
            for value in np.asarray(normalizer.std_train, dtype="float64")
        ],
    }
    return {**outputs, "state": state, "all_missing": int(np.isnan(center).sum())}
