"""Inputs of the investigation tools: a recorded rule test's returns and a market to compare.

The strategy's returns come from the diagnostic pass's own full-sample path
(``diagnose.full_sample``) on the bars the run used; a run whose stored history no longer
reproduces it fails loud instead of describing a different history.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING, Any

from alpha_cli import _runner
from alpha_cli.run_store import find_run_dir, read_manifest
from alpha_cli.spine.errors import SpineError
from alpha_cli.spine.run import assemble_run_spec
from alpha_cli.spine.spec import Costs, IdeaSpec
from alpha_cli.spine.stores import periods_per_year, resolve_asset
from alpha_cli.toolbox.reference import vintage_fingerprint
from alpha_cli.toolbox.reserve import RESERVED_DAY
from alpha_validation.attribution import MIN_BARS
from alpha_validation.metrics import to_returns

if TYPE_CHECKING:
    import polars as pl

    from alpha_core import Bar, CorporateAction
    from alpha_validation.metrics import FloatArray


@dataclass(frozen=True)
class RunSeries:
    """A rule-test run's identity and its full-sample equity on the bars the run used."""

    home: Path
    run_id: str
    manifest: dict[str, Any]
    asset: str
    ppy: int
    dates: tuple[datetime, ...]
    equity: tuple[float, ...]
    # The engine samples equity at each bar's open, so a fair market return is open-to-open.
    opens: dict[datetime, float]
    benchmark_equity: dict[datetime, float]
    positions: tuple[bool, ...] = ()

    def reserve_labels(self) -> tuple[str, ...]:
        last = self.manifest["metadata"].get("last_ts")
        end = max(self.dates[-1], datetime.fromisoformat(last)) if last else self.dates[-1]
        return ("reserved-period-seen",) if end.date() >= RESERVED_DAY else ()


RUN_KINDS = frozenset(("run_returns", "run_positions", "run_bars", "reference_factors"))


STORED_FILES = {
    "stored_equity": "equity_curve.parquet",
    "stored_benchmark": "benchmark_comparison.parquet",
    "run_trades": "trades.parquet",
}
# Stored buy-and-hold kinds a tool may read: the engine's price-only line, or the rule test's
# line on the strategy's own dividend rule (entitled before the ex-date open, paid on pay date).
HOLD_KINDS = frozenset(("passive_open_to_open_price_only", "passive_open_to_open_with_dividends"))


@dataclass(frozen=True)
class Target:
    run_id: str
    directory: Path
    manifest: dict[str, Any]

    @property
    def kinds(self) -> frozenset[str]:
        return RUN_KINDS.union(
            k for k, name in STORED_FILES.items() if (self.directory / name).is_file()
        )

    @property
    def last_ts(self) -> datetime:
        return datetime.fromisoformat(self.manifest["metadata"]["last_ts"])

    @property
    def ppy(self) -> int:
        annualisation = self.manifest["spine"].get("annualisation", {})
        value = self.manifest["metadata"].get(
            "periods_per_year", annualisation.get("periods_per_year")
        )
        if type(value) is not int or value < 1:
            raise ValueError("manifest.json requires a positive integer periods_per_year")
        return value

    def reserve_labels(self) -> tuple[str, ...]:
        return ("reserved-period-seen",) if self.last_ts.date() >= RESERVED_DAY else ()

    def table(self, kind: str, *columns: str) -> pl.DataFrame:
        import polars as pl

        name = STORED_FILES[kind]
        try:
            return pl.read_parquet(
                self.directory / name, columns=list(columns) if columns else None
            )
        except pl.exceptions.PolarsError as exc:
            raise ValueError(f"Cannot read {name}: {exc}") from exc

    def dates(self, frame: pl.DataFrame, kind: str) -> list[datetime]:
        dates: list[datetime] = frame["ts"].to_list()
        name = STORED_FILES[kind]
        if not dates or any(not isinstance(ts, datetime) or ts.utcoffset() is None for ts in dates):
            raise ValueError(f"{name} requires dated observations with a timezone")
        if any(before >= after for before, after in pairwise(dates)):
            raise ValueError(f"{name} requires strictly increasing dates")
        if dates[-1] > self.last_ts:
            raise ValueError(f"{name} extends beyond the recorded run period")
        return dates

    def scored_returns(self) -> FloatArray:
        """One after-cost return per interval in the immutable walk-forward equity file."""
        import numpy as np

        frame = self.table("stored_equity", "ts", "equity")
        if frame.height:
            self.dates(frame, "stored_equity")
        equity = frame["equity"].to_numpy()
        if equity.size < 2:
            if not np.isfinite(equity).all() or np.any(equity <= 0):
                raise ValueError("Stored equity must be finite and positive")
            return np.empty(0, dtype=np.float64)
        return to_returns(equity)

    @property
    def labels(self) -> list[str]:
        return list(self.manifest["spine"].get("labels", []))

    def ledger_fields(self) -> dict[str, Any]:
        spine = self.manifest["spine"]
        return {
            "test_id": spine.get("test_id"),
            "name": spine.get("name"),
            "symbol": self.manifest["metadata"]["symbol"],
            "store": spine.get("store"),
        }

    def prepare(
        self, home: Path, needs: tuple[str, ...], settings: dict[str, Any]
    ) -> tuple[Market | None, dict[str, Any]]:
        from alpha_cli.ml_contract import sha256_file

        files = [STORED_FILES[kind] for kind in needs if kind in STORED_FILES]
        for name in files:
            if not (self.directory / name).is_file():
                raise ValueError(f"Run {self.run_id} is missing {name}")
        if not self.kinds.issuperset(needs):
            raise ValueError(f"Target {self.run_id} cannot supply {needs}")
        market = comparison(
            home,
            self,
            settings.get("benchmark") or settings.get("market"),
            attribution="benchmark" in settings,
        )
        hashes = {
            "manifest": sha256_file(self.directory / "manifest.json"),
            "source": self.manifest.get("source_fingerprint"),
        }
        hashes.update({name: sha256_file(self.directory / name) for name in files})
        if market:
            hashes.update(market=market.fingerprint, market_asset=market.name)
        if "reference_factors" in needs:
            hashes.update(vintage_fingerprint(home))
        return market, hashes


def resolve(home: Path, run_id: str) -> Target:
    rdir = find_run_dir(home, run_id)
    if rdir is None:
        raise SpineError(
            "UNKNOWN_RUN",
            f"Unknown completed run {run_id!r}.",
            "Run alpha results --json to list recorded runs.",
        )
    manifest = read_manifest(rdir)
    if not isinstance(manifest.get("spine"), dict) or not (rdir / "spec.json").is_file():
        raise SpineError(
            "NOT_A_RULE_TEST",
            f"Run {run_id} was not made by alpha test.",
            "Run alpha results --json to list rule-test runs.",
        )
    return Target(run_id, rdir, manifest)


def load_run(home: Path, target: Target) -> RunSeries:
    from alpha_cli.spine.diagnose import full_sample
    from alpha_cli.spine.diagnostics import buy_and_hold
    from alpha_cli.spine.facts import read_json

    rdir, manifest, run_id = target.directory, target.manifest, target.run_id
    stored = read_json(rdir / "spec.json")
    meta = manifest["metadata"]
    resolved = resolve_asset(f"{meta['symbol']}@{manifest['spine']['store']}", data_dir=home)
    last = datetime.fromisoformat(meta["last_ts"])
    # A held-back run records its cut-off; bars and dividends known after it are never read.
    cutoff = _runner.parse_as_of(manifest.get("research_cutoff"))
    # Bars added after the run are left out, so the tool describes the run's own history.
    bars = [
        bar
        for bar in _runner.load_bars(resolved.symbol, data_dir=resolved.data_dir, as_of=cutoff)[0]
        if bar.ts <= last
    ]
    dividends = _runner.load_dividends(resolved.symbol, data_dir=resolved.data_dir, as_of=cutoff)
    changed = SpineError(
        "RUN_DATA_CHANGED",
        f"The stored history of {resolved.symbol} no longer reproduces run {run_id}.",
        "Run alpha test again from the saved spec, then run alpha tool on the new run.",
    )
    if _runner.source_fingerprint(bars, dividends=dividends) != manifest.get("source_fingerprint"):
        raise changed
    idea = IdeaSpec.model_validate({k: v for k, v in stored.items() if k != "spec_sha256"})
    if idea.costs_class_default:
        # The class row was chosen when the run was made; replay with the numbers it stored.
        used = manifest["spine"]["costs"]
        idea = idea.model_copy(
            update={"costs": Costs(fee_bps=used["fee_bps"], slippage_bps=used["slippage_bps"])}
        )
    ppy = periods_per_year([bar.ts for bar in bars])
    spec = assemble_run_spec(idea, resolved.symbol, ppy, len(bars))
    full, dates, equity = full_sample(bars, dividends, spec)
    expected = read_json(rdir / "diagnostics.json").get("full_sample", {}).get("total_return")
    if expected is not None and not math.isclose(
        equity[-1] / equity[0] - 1, expected, rel_tol=1e-9, abs_tol=1e-12
    ):
        raise changed
    states = {row.ts: row.net_exposure != 0 for row in full.portfolio_state_trace}
    if not set(dates) <= states.keys():
        raise ValueError("portfolio state trace does not cover the full-sample dates")
    if tuple(bar.ts for bar in bars) != dates:
        raise ValueError("full equity timestamps must match the loaded bars")
    return RunSeries(
        home=home,
        run_id=run_id,
        manifest=manifest,
        asset=f"{resolved.symbol}@{resolved.store_name}",
        ppy=ppy,
        dates=dates,
        equity=tuple(float(value) for value in equity),
        opens={bar.ts: float(bar.open) for bar in bars},
        benchmark_equity=dict(zip(dates, buy_and_hold(bars, dividends), strict=True)),
        positions=tuple(states[ts] for ts in dates),
    )


@dataclass(frozen=True)
class Joined:
    name: str
    same_asset: bool
    dates: list[datetime]
    strategy: Any
    market: Any
    ppy: int
    counts: dict[str, int]


@dataclass(frozen=True)
class Market:
    name: str
    bars: dict[datetime, Bar]
    dividends: tuple[CorporateAction, ...]
    fingerprint: str


def comparison(
    home: Path, target: Target, asset: str | None, *, attribution: bool = False
) -> Market | None:
    if asset is None:
        return None
    resolved = resolve_asset(asset, data_dir=home)
    name = f"{resolved.symbol}@{resolved.store_name}"
    meta = target.manifest["metadata"]
    if name == f"{meta['symbol']}@{target.manifest['spine']['store']}":
        return None
    last = datetime.fromisoformat(meta["last_ts"])
    bars, _ = _runner.load_bars(resolved.symbol, data_dir=resolved.data_dir, as_of=last)
    selected = {bar.ts: bar for bar in bars if bar.ts <= last}
    from alpha_cli.ml_contract import canonical_json_bytes

    opens = {ts.isoformat(): float(bar.open) for ts, bar in selected.items()}
    digest = hashlib.sha256(canonical_json_bytes(opens))
    dividends: tuple[CorporateAction, ...] = ()
    if attribution:
        dividends = tuple(
            _runner.load_dividends(resolved.symbol, data_dir=resolved.data_dir, as_of=last)
        )
        digest.update(_runner.source_fingerprint([], dividends=dividends).encode())
    return Market(name, selected, dividends, digest.hexdigest())


@dataclass(frozen=True)
class Inputs:
    source: RunSeries | Target
    market: Market | None = None
    seed: int = 0
    home: Path | None = None

    @property
    def run(self) -> RunSeries:
        if not isinstance(self.source, RunSeries):
            raise ValueError("This tool requires a full-sample replay")
        return self.source

    @property
    def data_home(self) -> Path:
        if self.home is None:
            raise ValueError("This tool requires the data home")
        return self.home

    @property
    def stored(self) -> Target:
        if not isinstance(self.source, Target):
            raise ValueError("This tool requires stored run files")
        return self.source


def join_market(inputs: Inputs, *, attribution: bool = False) -> Joined:
    """Align both legs on shared opens before turning their levels into interval returns."""
    from alpha_cli.spine.diagnostics import buy_and_hold

    series, other = inputs.run, inputs.market
    name = other.name if other else series.asset
    market_dates = other.bars.keys() if other else series.opens.keys()
    common = [date for date in series.dates if date in market_dates]
    inside = sum(series.dates[0] <= ts <= series.dates[-1] for ts in market_dates)
    counts = {
        "run_bars": len(series.dates),
        "other_bars_in_run_window": inside,
        "shared_bars": len(common),
        "run_bars_dropped": len(series.dates) - len(common),
        "other_bars_dropped": inside - len(common),
    }
    if len(common) < MIN_BARS + 1:
        raise SpineError(
            "TOO_FEW_BARS",
            f"Run {series.run_id} and {name} share {len(common)} bar timestamps; "
            f"{MIN_BARS + 1} are needed.",
            "Run alpha tool again with a benchmark or market that covers the run's dates.",
        )
    equity = dict(zip(series.dates, series.equity, strict=True))
    if other:
        bars = [other.bars[ts] for ts in common]
        levels = buy_and_hold(bars, other.dividends) if attribution else [bar.open for bar in bars]
    else:
        market = series.benchmark_equity if attribution else series.opens
        levels = [market[ts] for ts in common]
    return Joined(
        name=name,
        same_asset=name == series.asset,
        dates=common,
        strategy=to_returns([equity[date] for date in common]),
        market=to_returns(levels),
        ppy=series.ppy if len(common) == len(series.dates) else periods_per_year(common),
        counts=counts,
    )


def regime_flags(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Observations on a causal regime split, never a verdict."""
    flags = []
    for row in rows:
        if row["share_of_time"] >= 0.95:
            flags.append(
                {
                    "flag": "one-regime-dominates",
                    "detail": (
                        f"The model put {row['share_of_time']:.0%} of bars in the {row['name']} "
                        "regime, so this market history shows no clear calm/turbulent split."
                    ),
                }
            )
        share = row["share_of_log_return"]
        if share is not None and share >= 0.8:
            flags.append(
                {
                    "flag": "return-concentrated-in-regime",
                    "detail": (
                        f"{share:.0%} of the strategy's total log return was earned in the "
                        f"{row['name']} regime, which covers {row['share_of_time']:.0%} of bars."
                    ),
                }
            )
    return flags
