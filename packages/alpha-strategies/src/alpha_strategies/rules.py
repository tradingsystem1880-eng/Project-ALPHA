"""Owner-authored rule strategies (spec 2026-09-01 §4.2, Phase 5 S4): a strict, canonical JSON
``RuleSpec`` that says when to *be* long or short, evaluated statelessly over a fixed trailing
history.

Design choices, each deliberate:

- **State, not events.** A rule side is a conjunction of comparisons that must hold on the decision
  bar (``sma:20 > sma:50``, ``rsi:14 < 30``). There is no "crosses" or order state, so the same
  function answers the engine, the Tier-1 surrogate and a scan identically, and a decision depends
  on nothing but the last ``history`` bars.
- **Fixed trailing window.** Every evaluation sees exactly ``history`` bars. EMA/RSI recursions are
  history-length dependent, so pinning the window is what makes the engine and the surrogate agree
  bar for bar and keeps the decision point-in-time by construction.
- **Indicators come from ``alpha_patterns``** (the same functions ``alpha chart overlays`` draws),
  never re-implemented here; a value that is still warming up on the decision bar is a
  ``DataError``, not a silent zero.
- **Canonical bytes.** ``canonical_json`` is the identity the run manifest carries and the run id
  hashes; two specs with the same meaning serialise to the same bytes.

Sources are limited to ``high``/``low``/``close`` because that is the history the vol-target base
strategy keeps; volume and open rules can be added when the base keeps them.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

from alpha_core import DataError
from alpha_patterns import OHLCV, atr, ema, macd, rolling_mean, rolling_std, rsi

RULES_SPEC_VERSION = 1
MAX_CONDITIONS_PER_SIDE = 12
MAX_NAME_LENGTH = 80
MAX_HISTORY = 2_000

Source = Literal["high", "low", "close"]
SOURCES: tuple[Source, ...] = ("high", "low", "close")
Op = Literal[">", "<", ">=", "<="]
OPS: tuple[Op, ...] = (">", "<", ">=", "<=")

#: indicator -> parameter count; the same table ``alpha chart overlays`` accepts.
INDICATOR_ARITY: Mapping[str, int] = {
    "sma": 1,
    "ema": 1,
    "bbands": 2,
    "rsi": 1,
    "atr": 1,
    "macd": 3,
}
#: multi-series indicators need a field; single-series ones must not carry one.
INDICATOR_FIELDS: Mapping[str, tuple[str, ...]] = {
    "bbands": ("upper", "middle", "lower"),
    "macd": ("line", "signal", "histogram"),
}

FloatArray = np.ndarray


def _fmt(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else repr(float(value))


@dataclass(frozen=True)
class Operand:
    """One side of a comparison: a price source, an indicator series, or a constant."""

    kind: Literal["source", "indicator", "value"]
    source: Source | None = None
    indicator: str | None = None
    params: tuple[float, ...] = ()
    field: str | None = None
    value: float | None = None

    @property
    def label(self) -> str:
        if self.kind == "source":
            return str(self.source)
        if self.kind == "value":
            return _fmt(float(self.value or 0.0))
        head = ":".join([str(self.indicator), *(_fmt(p) for p in self.params)])
        return f"{head}:{self.field}" if self.field else head

    @property
    def bars_needed(self) -> int:
        """Bars required before this operand has a finite value on the last bar."""
        if self.kind != "indicator":
            return 1
        p = [int(v) for v in self.params]
        if self.indicator == "rsi":
            return p[0] + 1
        if self.indicator == "macd":
            return p[1] + p[2] - 1
        return p[0]

    def to_json(self) -> dict[str, object]:
        if self.kind == "source":
            return {"source": self.source}
        if self.kind == "value":
            return {"value": self.value}
        params = [int(p) if float(p).is_integer() else float(p) for p in self.params]
        out: dict[str, object] = {"indicator": self.indicator, "params": params}
        if self.field is not None:
            out["field"] = self.field
        return out


@dataclass(frozen=True)
class Condition:
    left: Operand
    op: Op
    right: Operand

    @property
    def label(self) -> str:
        return f"{self.left.label} {self.op} {self.right.label}"

    def to_json(self) -> dict[str, object]:
        return {"left": self.left.to_json(), "op": self.op, "right": self.right.to_json()}


@dataclass(frozen=True)
class RuleSpec:
    """Be long while every ``long_when`` holds; be short while every ``short_when`` holds."""

    name: str
    long_when: tuple[Condition, ...]
    short_when: tuple[Condition, ...]
    history: int
    version: int = RULES_SPEC_VERSION

    @property
    def operands(self) -> tuple[Operand, ...]:
        return tuple(
            operand
            for condition in (*self.long_when, *self.short_when)
            for operand in (condition.left, condition.right)
        )

    @property
    def warmup(self) -> int:
        """Bars needed before every operand is finite on the decision bar."""
        return max(operand.bars_needed for operand in self.operands)

    def to_json(self) -> dict[str, object]:
        return {
            "version": self.version,
            "name": self.name,
            "history": self.history,
            "long_when": [condition.to_json() for condition in self.long_when],
            "short_when": [condition.to_json() for condition in self.short_when],
        }


def default_history(warmup: int) -> int:
    """Long enough for the EMA/RSI recursions to have forgotten their seed: 4 × warm-up, never
    below 60 and never above ``MAX_HISTORY``."""
    return min(max(4 * warmup, 60), MAX_HISTORY)


# --- parsing --------------------------------------------------------------------------------------


def _require_mapping(value: object, where: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise DataError(f"{where} must be an object, got {type(value).__name__}")
    return value


def _reject_unknown(payload: Mapping[str, object], allowed: set[str], where: str) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise DataError(f"{where} has unknown keys {unknown}; allowed {sorted(allowed)}")


def _number(value: object, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DataError(f"{where} must be a number, got {value!r}")
    if not math.isfinite(value):
        raise DataError(f"{where} must be finite, got {value!r}")
    return float(value)


def _window(value: object, where: str) -> float:
    number = _number(value, where)
    if not number.is_integer() or number < 2:
        raise DataError(f"{where} must be a whole number of bars >= 2, got {value!r}")
    return number


def parse_operand(payload: object, where: str) -> Operand:
    raw = _require_mapping(payload, where)
    if "source" in raw:
        _reject_unknown(raw, {"source"}, where)
        if raw["source"] not in SOURCES:
            raise DataError(f"{where}.source must be one of {list(SOURCES)}, got {raw['source']!r}")
        return Operand(kind="source", source=raw["source"])
    if "value" in raw:
        _reject_unknown(raw, {"value"}, where)
        return Operand(kind="value", value=_number(raw["value"], f"{where}.value"))
    if "indicator" in raw:
        _reject_unknown(raw, {"indicator", "params", "field"}, where)
        name = raw["indicator"]
        if not isinstance(name, str) or name not in INDICATOR_ARITY:
            raise DataError(
                f"{where}.indicator must be one of {sorted(INDICATOR_ARITY)}, got {name!r}"
            )
        params_raw = raw.get("params", [])
        if not isinstance(params_raw, Sequence) or isinstance(params_raw, str):
            raise DataError(f"{where}.params must be a list")
        if len(params_raw) != INDICATOR_ARITY[name]:
            raise DataError(
                f"{where}: {name} takes {INDICATOR_ARITY[name]} parameter(s), got {len(params_raw)}"
            )
        params: list[float] = []
        for index, item in enumerate(params_raw):
            label = f"{where}.params[{index}]"
            if name == "bbands" and index == 1:
                width = _number(item, label)
                if width <= 0:
                    raise DataError(f"{label} (Bollinger width) must be > 0, got {item!r}")
                params.append(width)
            else:
                params.append(_window(item, label))
        if name == "macd" and not params[0] < params[1]:
            raise DataError(f"{where}: macd fast window must be shorter than slow")
        fields = INDICATOR_FIELDS.get(name)
        field = raw.get("field")
        if fields is None and field is not None:
            raise DataError(f"{where}: {name} has a single series; drop 'field'")
        if fields is not None and field not in fields:
            raise DataError(f"{where}: {name} needs field in {list(fields)}, got {field!r}")
        return Operand(
            kind="indicator",
            indicator=name,
            params=tuple(params),
            field=str(field) if field is not None else None,
        )
    raise DataError(f"{where} must have exactly one of 'source', 'indicator', 'value'")


def parse_condition(payload: object, where: str) -> Condition:
    raw = _require_mapping(payload, where)
    _reject_unknown(raw, {"left", "op", "right"}, where)
    for key in ("left", "op", "right"):
        if key not in raw:
            raise DataError(f"{where} is missing {key!r}")
    op = raw["op"]
    if op not in OPS:
        raise DataError(f"{where}.op must be one of {list(OPS)}, got {op!r}")
    left = parse_operand(raw["left"], f"{where}.left")
    right = parse_operand(raw["right"], f"{where}.right")
    if left.kind == "value" and right.kind == "value":
        raise DataError(f"{where} compares two constants; one side must read the market")
    return Condition(left=left, op=op, right=right)


def _side(payload: Mapping[str, object], key: str) -> tuple[Condition, ...]:
    raw = payload.get(key, [])
    if not isinstance(raw, Sequence) or isinstance(raw, str):
        raise DataError(f"{key} must be a list of conditions")
    if len(raw) > MAX_CONDITIONS_PER_SIDE:
        raise DataError(f"{key} has {len(raw)} conditions; the limit is {MAX_CONDITIONS_PER_SIDE}")
    return tuple(parse_condition(item, f"{key}[{index}]") for index, item in enumerate(raw))


def parse_rule_spec(payload: object) -> RuleSpec:
    """Strict parse of a rule-spec object; every defect is a ``DataError`` naming its path."""
    raw = _require_mapping(payload, "rule spec")
    _reject_unknown(raw, {"version", "name", "long_when", "short_when", "history"}, "rule spec")
    version = raw.get("version", RULES_SPEC_VERSION)
    if version != RULES_SPEC_VERSION:
        raise DataError(f"rule spec version must be {RULES_SPEC_VERSION}, got {version!r}")
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise DataError("rule spec needs a non-empty 'name'")
    if len(name) > MAX_NAME_LENGTH:
        raise DataError(f"rule spec name is longer than {MAX_NAME_LENGTH} characters")
    long_when = _side(raw, "long_when")
    short_when = _side(raw, "short_when")
    if not long_when and not short_when:
        raise DataError("rule spec needs at least one condition in long_when or short_when")
    warmup = max(
        operand.bars_needed
        for condition in (*long_when, *short_when)
        for operand in (condition.left, condition.right)
    )
    history_raw = raw.get("history", default_history(warmup))
    history = _number(history_raw, "history")
    if not history.is_integer() or history < warmup or history > MAX_HISTORY:
        raise DataError(
            f"history must be a whole number of bars between {warmup} (the longest indicator) "
            f"and {MAX_HISTORY}, got {history_raw!r}"
        )
    return RuleSpec(
        name=name.strip(),
        long_when=long_when,
        short_when=short_when,
        history=int(history),
    )


def canonical_json(spec: RuleSpec) -> str:
    """The one serialisation of a spec: sorted keys, no whitespace, no NaN."""
    return json.dumps(spec.to_json(), sort_keys=True, separators=(",", ":"), allow_nan=False)


def spec_sha256(spec: RuleSpec) -> str:
    return hashlib.sha256(canonical_json(spec).encode("utf-8")).hexdigest()


def rule_spec_from_json(text: str) -> RuleSpec:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DataError(f"rule spec is not valid JSON: {exc}") from exc
    return parse_rule_spec(payload)


# --- evaluation -----------------------------------------------------------------------------------


def operand_series(series: OHLCV, operand: Operand) -> FloatArray:
    """The operand's value on every bar of ``series``; warm-up bars are NaN, never a guess."""
    n = len(series)
    if operand.kind == "source":
        return np.asarray(getattr(series, str(operand.source)), dtype=np.float64)
    if operand.kind == "value":
        return np.full(n, float(operand.value or 0.0), dtype=np.float64)
    p = [int(v) if float(v).is_integer() else float(v) for v in operand.params]
    name = operand.indicator
    if name == "sma":
        values, warm = rolling_mean(series.close, int(p[0])), int(p[0]) - 1
    elif name == "ema":
        values, warm = ema(series.close, int(p[0])), int(p[0]) - 1
    elif name == "rsi":
        values, warm = rsi(series.close, int(p[0])), int(p[0])
    elif name == "atr":
        values, warm = atr(series, int(p[0])), int(p[0]) - 1
    elif name == "bbands":
        w, k = int(p[0]), float(p[1])
        mid = rolling_mean(series.close, w)
        sd = rolling_std(series.close, w)
        band = {"upper": mid + k * sd, "middle": mid, "lower": mid - k * sd}
        values, warm = band[str(operand.field)], w - 1
    else:
        fast, slow, signal = (int(v) for v in p)
        out = macd(series.close, fast=fast, slow=slow, signal=signal)
        picked = {"line": out.line, "signal": out.signal, "histogram": out.histogram}
        values = picked[str(operand.field)]
        warm = slow - 1 if operand.field == "line" else slow + signal - 2
    values = np.asarray(values, dtype=np.float64).copy()
    values[: min(warm, n)] = np.nan
    return values


def _holds(condition: Condition, series: OHLCV) -> bool:
    left = float(operand_series(series, condition.left)[-1])
    right = float(operand_series(series, condition.right)[-1])
    if not (math.isfinite(left) and math.isfinite(right)):
        raise DataError(
            f"rule '{condition.label}' has no finite value on the decision bar "
            f"(history {len(series)} bars); lengthen 'history'"
        )
    if condition.op == ">":
        return left > right
    if condition.op == "<":
        return left < right
    if condition.op == ">=":
        return left >= right
    return left <= right


def evaluate_rules(spec: RuleSpec, series: OHLCV) -> int:
    """The ``{-1, 0, 1}`` signal on the last bar of exactly ``spec.history`` bars.

    Both sides true is a conflict and means flat: a rule set that cannot make up its mind does not
    get to hold a position. The exact-length check is the point-in-time guarantee — a caller
    cannot hand in more history than the spec declares and change a past decision.
    """
    if len(series) != spec.history:
        raise DataError(
            f"rules evaluate over exactly {spec.history} trailing bars, got {len(series)}"
        )
    long = bool(spec.long_when) and all(_holds(c, series) for c in spec.long_when)
    short = bool(spec.short_when) and all(_holds(c, series) for c in spec.short_when)
    if long == short:
        return 0
    return 1 if long else -1


def trailing_ohlcv(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    *,
    history: int,
    symbol: str = "RULES",
) -> OHLCV:
    """The last ``history`` bars as an ``OHLCV`` with synthetic daily timestamps.

    Timestamps carry no information a rule may read, so index-spaced ones keep the surrogate (which
    has no clock) and the engine on the same footing. Opens are set to the close and volume to one:
    neither is a permitted source. Inconsistent bars (a high below the close) are ``OHLCV``'s to
    reject — nothing is repaired here.
    """
    if len(closes) < history:
        raise DataError(f"rules need {history} bars of history, have {len(closes)}")
    if not (len(highs) == len(lows) == len(closes)):
        raise DataError("highs, lows and closes must have the same length")
    h = np.asarray(highs[-history:], dtype=np.float64)
    lo = np.asarray(lows[-history:], dtype=np.float64)
    c = np.asarray(closes[-history:], dtype=np.float64)
    return OHLCV(
        ts=np.arange(history, dtype=np.float64) * 86_400_000.0,
        open=c.copy(),
        high=h,
        low=lo,
        close=c,
        volume=np.ones(history, dtype=np.float64),
        symbol=symbol,
    )


def rule_signal(
    spec: RuleSpec, highs: Sequence[float], lows: Sequence[float], closes: Sequence[float]
) -> int:
    """Convenience: build the trailing window and evaluate — the one call the engine, the Tier-1
    surrogate and a scanner all make."""
    return evaluate_rules(spec, trailing_ohlcv(highs, lows, closes, history=spec.history))
