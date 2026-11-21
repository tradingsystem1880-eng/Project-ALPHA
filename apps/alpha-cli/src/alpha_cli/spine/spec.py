"""Frozen public idea vocabulary and its canonical content identity."""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class Rule(FrozenModel):
    kind: str
    fast: int | None = Field(default=None, ge=1)
    slow: int | None = Field(default=None, ge=2)
    window: int | None = Field(default=None, ge=2)
    lookback: int | None = Field(default=None, ge=1)
    skip: int | None = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def check_names(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        names = {
            "ma_cross": ("fast", "slow"),
            "breakout": ("window",),
            "tsmom": ("lookback", "skip"),
        }
        kind = value.get("kind")
        if kind not in names:
            raise ValueError("unknown rule kind; known: ma_cross, breakout, tsmom")
        allowed = names[kind]
        unknown = set(value) - {"kind", *allowed}
        if unknown:
            raise ValueError(f"unknown parameter(s) {sorted(unknown)}; known: {', '.join(allowed)}")
        value = dict(value)
        if kind == "tsmom":
            value.setdefault("skip", 0)
        missing = [key for key in allowed if value.get(key) is None]
        if missing:
            raise ValueError(f"missing rule parameter(s): {', '.join(missing)}")
        if any(isinstance(value[key], bool) for key in allowed):
            raise ValueError("rule parameters must be integers, not booleans")
        return value

    @model_validator(mode="after")
    def check_order(self) -> Self:
        if self.fast is not None and self.slow is not None and self.fast >= self.slow:
            raise ValueError("fast must be less than slow")
        return self

    @property
    def params(self) -> dict[str, int]:
        return {
            key: value
            for key in ("fast", "slow", "window", "lookback", "skip")
            if (value := getattr(self, key)) is not None
        }

    @model_serializer
    def serialize(self) -> dict[str, Any]:
        return {"kind": self.kind, **self.params}

    @property
    def strategy(self) -> str:
        return {"ma_cross": "ma_crossover", "breakout": "breakout", "tsmom": "ts_momentum"}[
            self.kind
        ]


class Costs(FrozenModel):
    """Costs per side. `costs = "class-default"` asks for the default of the asset class.

    The numbers then stay at the flat placeholder; the run takes the class row. `mode` is left
    out of every dump unless it is set, so no older spec changes its hash.
    """

    fee_bps: float = Field(default=1.0, ge=0)
    slippage_bps: float = Field(default=2.0, ge=0)
    mode: Literal["class-default"] | None = None

    @model_validator(mode="before")
    @classmethod
    def from_word(cls, value: Any) -> Any:
        if isinstance(value, str):
            if value != "class-default":
                raise ValueError('costs must be a table or the word "class-default"')
            return {"mode": value}
        return value

    @model_serializer(mode="wrap")
    def omit_unset_mode(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        if data.get("mode") is None:
            data.pop("mode", None)
        return data


class IdeaSpec(FrozenModel):
    name: str = ""
    idea: str = ""
    assets: tuple[Annotated[str, Field(min_length=1)], ...] = Field(min_length=1)
    rule: Rule
    costs: Costs = Field(default_factory=Costs)
    # Context gate: `{alias: "series@key"}` and an expression over the aliases. A spec without
    # them dumps without these keys, so its hash, run id and stored spec stay as before. The
    # stored spec keeps the text as written; the hash takes the canonical form (see canonical).
    context: dict[str, str] | None = None
    when: str | None = None
    # A link to an idea card. Excluded from dumps, so it is in no hash, run id or stored spec.
    idea_card: str = Field(default="", exclude=True)

    @property
    def costs_class_default(self) -> bool:
        return self.costs.mode == "class-default"

    @model_validator(mode="after")
    def default_name(self) -> Self:
        if not self.name:
            object.__setattr__(
                self, "name", "-".join([self.rule.kind, *map(str, self.rule.params.values())])
            )
        return self

    @model_validator(mode="after")
    def check_gate(self) -> Self:
        if self.context is None and self.when is None:
            return self  # most specs: keep the heavy context code unloaded
        from alpha_cli._context_gate import check_context

        check_context(self.context, self.when)
        return self

    @model_serializer(mode="wrap")
    def omit_absent_gate(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        for key in ("context", "when"):
            if data.get(key) is None:
                data.pop(key, None)
        return data

    def canonical(self) -> str:
        data = self.model_dump(mode="json", exclude_none=True)
        if self.context is not None and self.when is not None:
            # Alias names and spacing are not identity: hash the canonical gate form.
            from alpha_cli._context_gate import canonical_fields

            data.update(canonical_fields(self.context, self.when))
        return json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @property
    def spec_sha256(self) -> str:
        return hashlib.sha256(self.canonical().encode()).hexdigest()


def load_spec(
    path: Path | None,
    *,
    rule: str | None = None,
    param: list[str] | None = None,
    asset: list[str] | None = None,
    name: str | None = None,
    idea: str | None = None,
    fee_bps: float | None = None,
    slippage_bps: float | None = None,
    idea_card: str | None = None,
) -> IdeaSpec:
    """Read one file or an equivalent complete set of flags, never a silent override."""
    if path is not None:
        flags = (rule, param, asset, name, idea, fee_bps, slippage_bps, idea_card)
        if any(value is not None for value in flags):
            raise ValueError("a spec path and rule flags cannot be used together")
        if path.suffix.lower() == ".toml":
            with path.open("rb") as stream:
                return IdeaSpec.model_validate(tomllib.load(stream))
        if path.suffix.lower() == ".json":
            return IdeaSpec.model_validate_json(path.read_text(encoding="utf-8"))
        raise ValueError("spec file must have .toml or .json suffix")
    values: dict[str, Any] = {"kind": rule}
    for item in param or []:
        key, separator, raw = item.partition("=")
        if not separator or not key.strip():
            raise ValueError(f"parameter must be name=value: {item!r}")
        key = key.strip()
        if key in values:
            raise ValueError(f"duplicate parameter {key!r}")
        values[key] = raw
    costs = {
        key: value
        for key, value in {"fee_bps": fee_bps, "slippage_bps": slippage_bps}.items()
        if value is not None
    }
    return IdeaSpec.model_validate(
        {
            "name": name or "",
            "idea": idea or "",
            "idea_card": idea_card or "",
            "assets": asset or [],
            "rule": values,
            "costs": costs,
        }
    )
