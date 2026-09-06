"""``alpha scan`` — run a saved rule set across stored symbols and keep deduplicated alerts.

A scan is one JSON file at ``data_dir/scans/<name>.json`` naming a saved rule set (``alpha rules``)
and a universe: an explicit symbol list or ``stored`` (every symbol with bars at run time). ``run``
evaluates ``alpha_strategies.rules.rule_signal`` on each symbol's point-in-time bars (``load_bars``
with the ``--as-of`` cutoff, the same firewall a backtest uses) and reports the signal on the last
bar with every operand's value. ``check`` compares a run with the previous check's state and
appends only *changed* signals to ``data_dir/scans/alerts.jsonl`` — the file the live desk watches
(``_activity`` area ``alerts``). Read-only over the store, ``authority: none``: a scan proves an
idea's current state, never that it is worth trading.

``universe_as_of`` is the wall-clock time the universe was listed: a ``stored`` universe is the
symbols present *now*, which says nothing about what was listed on the evaluated bar. A
scan is a screen, not a survivorship-safe backtest.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

import typer

from alpha_core import DataError
from alpha_core.config import AlphaSettings

scan_app = typer.Typer(help="Rule scans over stored symbols and their deduplicated alerts.")

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_ALERT_LIMIT_DEFAULT = 200


def scans_dir(data_dir: Path) -> Path:
    return data_dir / "scans"


def alerts_path(data_dir: Path) -> Path:
    return scans_dir(data_dir) / "alerts.jsonl"


def scan_path(data_dir: Path, name: str) -> Path:
    if not _NAME_RE.match(name):
        raise DataError(
            f"scan name {name!r} must be 1-64 lowercase letters, digits, '-' or '_' "
            "(it names a file under data_dir/scans/)"
        )
    return scans_dir(data_dir) / f"{name}.json"


def _state_path(data_dir: Path, name: str) -> Path:
    return scans_dir(data_dir) / "state" / f"{name}.json"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", "utf-8")
    os.replace(tmp, path)


def load_scan(data_dir: Path, name: str) -> dict[str, Any]:
    path = scan_path(data_dir, name)
    if not path.is_file():
        raise DataError(f"no saved scan {name!r} (expected {path}); run `alpha scan save` first")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataError(f"scan {name!r} is not valid JSON: {exc}") from exc
    return validate_scan(payload)


def validate_scan(payload: object) -> dict[str, Any]:
    """Strict shape: ``{name, rules, universe: {kind: stored} | {kind: list, symbols: [...]}}``."""
    if not isinstance(payload, dict):
        raise DataError("scan must be an object")
    unknown = sorted(set(payload) - {"name", "rules", "universe"})
    if unknown:
        raise DataError(f"scan has unknown keys {unknown}")
    name, rules, universe = payload.get("name"), payload.get("rules"), payload.get("universe")
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise DataError("scan.name must be a lowercase slug")
    if not isinstance(rules, str) or not _NAME_RE.match(rules):
        raise DataError("scan.rules must name a saved rule set (alpha rules save NAME)")
    if not isinstance(universe, dict) or universe.get("kind") not in {"stored", "list"}:
        raise DataError("scan.universe must be {kind: 'stored'} or {kind: 'list', symbols: [...]}")
    if universe["kind"] == "list":
        symbols = universe.get("symbols")
        if (
            not isinstance(symbols, list)
            or not symbols
            or any(not isinstance(s, str) or not s.strip() for s in symbols)
        ):
            raise DataError("scan.universe.symbols must be a non-empty list of symbols")
        if set(universe) != {"kind", "symbols"}:
            raise DataError("scan.universe (list) allows only kind and symbols")
        universe = {"kind": "list", "symbols": sorted({s.strip() for s in symbols})}
    else:
        if set(universe) != {"kind"}:
            raise DataError("scan.universe (stored) allows only kind")
    return {"name": name, "rules": rules, "universe": universe}


def _universe(scan: dict[str, Any], data_dir: Path) -> list[str]:
    if scan["universe"]["kind"] == "list":
        return list(scan["universe"]["symbols"])
    from alpha_data.store import ParquetStore

    return ParquetStore(data_dir / "store").list_symbols()


def run_scan(scan: dict[str, Any], *, data_dir: Path, as_of: date | None) -> dict[str, Any]:
    """Evaluate the scan's rule set on every universe symbol's point-in-time bars."""
    from alpha_cli._runner import load_bars
    from alpha_cli.rules_cmds import load_rule_text
    from alpha_strategies.rules import (
        evaluate_rules,
        operand_series,
        rule_spec_from_json,
        spec_sha256,
        trailing_ohlcv,
    )

    spec = rule_spec_from_json(load_rule_text(data_dir, scan["rules"]))
    when = datetime.combine(as_of, time.max, tzinfo=UTC) if as_of else None
    universe_as_of = datetime.now(tz=UTC).replace(microsecond=0).isoformat()
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for symbol in sorted(set(_universe(scan, data_dir))):
        try:
            bars, _snap = load_bars(symbol, data_dir=data_dir, as_of=when)
            if len(bars) < spec.history:
                raise DataError(f"{len(bars)} bars stored, the rule set needs {spec.history}")
            window = trailing_ohlcv(
                [b.high for b in bars],
                [b.low for b in bars],
                [b.close for b in bars],
                history=spec.history,
                symbol=symbol,
            )
            signal = evaluate_rules(spec, window)
        except DataError as exc:
            skipped.append({"symbol": symbol, "reason": str(exc)})
            continue
        values = {
            operand.label: float(operand_series(window, operand)[-1])
            for operand in spec.operands
            if operand.kind != "value"
        }
        last = bars[-1]
        rows.append(
            {
                "symbol": symbol,
                "signal": signal,
                "bar_ts": last.ts.timestamp(),
                "bar_date": last.ts.date().isoformat(),
                "close": last.close,
                "values": values,
            }
        )
    return {
        "scan": scan["name"],
        "rules": scan["rules"],
        "rules_sha256": spec_sha256(spec),
        "as_of": as_of.isoformat() if as_of else None,
        "universe_as_of": universe_as_of,
        "universe": scan["universe"],
        "rows": rows,
        "skipped": skipped,
        "authority": "none",
    }


def diff_alerts(
    previous: dict[str, dict[str, Any]], rows: list[dict[str, Any]], *, scan: str, checked_at: str
) -> list[dict[str, Any]]:
    """Alerts for signals that changed since the last check (a first sighting alerts only when
    the signal is non-zero); the same signal on a newer bar is not news."""
    alerts: list[dict[str, Any]] = []
    for row in rows:
        before = previous.get(row["symbol"])
        prior_signal = before["signal"] if before else None
        if prior_signal == row["signal"] or (prior_signal is None and row["signal"] == 0):
            continue
        alerts.append(
            {
                "ts": checked_at,
                "scan": scan,
                "symbol": row["symbol"],
                "previous": prior_signal,
                "signal": row["signal"],
                "bar_date": row["bar_date"],
                "close": row["close"],
            }
        )
    return alerts


def check_scan(scan: dict[str, Any], *, data_dir: Path) -> dict[str, Any]:
    result = run_scan(scan, data_dir=data_dir, as_of=None)
    state_path = _state_path(data_dir, scan["name"])
    previous: dict[str, dict[str, Any]] = {}
    if state_path.is_file():
        loaded = json.loads(state_path.read_text(encoding="utf-8"))
        previous = loaded.get("signals", {}) if isinstance(loaded, dict) else {}
    checked_at = datetime.now(tz=UTC).replace(microsecond=0).isoformat()
    alerts = diff_alerts(previous, result["rows"], scan=scan["name"], checked_at=checked_at)
    if alerts:
        path = alerts_path(data_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for alert in alerts:
                handle.write(json.dumps(alert, sort_keys=True) + "\n")
    _write_json(
        state_path,
        {
            "checked_at": checked_at,
            "signals": {
                row["symbol"]: {"signal": row["signal"], "bar_date": row["bar_date"]}
                for row in result["rows"]
            },
        },
    )
    return {
        "scan": scan["name"],
        "checked_at": checked_at,
        "rows": len(result["rows"]),
        "skipped": len(result["skipped"]),
        "alerts": alerts,
        "authority": "none",
    }


def read_alerts(data_dir: Path, *, limit: int) -> list[dict[str, Any]]:
    path = alerts_path(data_dir)
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-limit:] if limit > 0 else lines:
        if line.strip():
            out.append(json.loads(line))
    return out


def _saved_scans(data_dir: Path) -> list[dict[str, Any]]:
    directory = scans_dir(data_dir)
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        try:
            scan = load_scan(data_dir, path.stem)
            state_path = _state_path(data_dir, path.stem)
            checked_at = None
            if state_path.is_file():
                state = json.loads(state_path.read_text(encoding="utf-8"))
                checked_at = state.get("checked_at") if isinstance(state, dict) else None
            rows.append({**scan, "checked_at": checked_at})
        except DataError as exc:
            rows.append({"name": path.stem, "error": str(exc)})
    return rows


def _emit(payload: dict[str, Any], json_out: bool, text: str) -> None:
    typer.echo(json.dumps(payload) if json_out else text)


def _bad(exc: DataError) -> typer.BadParameter:
    return typer.BadParameter(str(exc))


@scan_app.command("save")
def save(
    name: str,
    rules: str = typer.Option(..., "--rules", help="saved rule set name (alpha rules save)"),
    symbols: str | None = typer.Option(
        None, "--symbols", help="comma-separated symbols; omit to scan every stored symbol"
    ),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Save (or overwrite) a scan: a rule set plus a universe."""
    from alpha_cli.rules_cmds import load_rule_text

    data_dir = AlphaSettings().data_dir
    universe: dict[str, Any] = (
        {"kind": "list", "symbols": [s for s in symbols.split(",") if s.strip()]}
        if symbols
        else {"kind": "stored"}
    )
    try:
        scan = validate_scan({"name": name, "rules": rules, "universe": universe})
        load_rule_text(data_dir, rules)  # the rule set must exist
        _write_json(scan_path(data_dir, name), scan)
    except DataError as exc:
        raise _bad(exc) from exc
    _emit({**scan, "checked_at": None}, json_out, f"saved scan {name} -> rules {rules}")


@scan_app.command("list")
def list_scans(json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    """Every saved scan with its last check time."""
    rows = _saved_scans(AlphaSettings().data_dir)
    if json_out:
        typer.echo(json.dumps({"scans": rows, "authority": "none"}))
    else:
        for row in rows:
            typer.echo(f"{row['name']}: {row.get('rules', row.get('error'))}")
        if not rows:
            typer.echo("no saved scans")


@scan_app.command("show")
def show(name: str, json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    data_dir = AlphaSettings().data_dir
    try:
        scan = load_scan(data_dir, name)
    except DataError as exc:
        raise _bad(exc) from exc
    _emit({**scan, "checked_at": None}, json_out, json.dumps(scan))


@scan_app.command("delete")
def delete(name: str, json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    """Remove a saved scan and its check state; past alerts stay in the log."""
    data_dir = AlphaSettings().data_dir
    try:
        path = scan_path(data_dir, name)
        if not path.is_file():
            raise DataError(f"no saved scan {name!r}")
    except DataError as exc:
        raise _bad(exc) from exc
    path.unlink()
    state = _state_path(data_dir, name)
    if state.is_file():
        state.unlink()
    _emit({"name": name, "deleted": True}, json_out, f"deleted scan {name}")


@scan_app.command("run")
def run(
    name: str,
    as_of: str | None = typer.Option(None, "--as-of", help="evaluate as of YYYY-MM-DD"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Evaluate the scan on point-in-time bars; nothing is written."""
    data_dir = AlphaSettings().data_dir
    try:
        cutoff = date.fromisoformat(as_of) if as_of else None
    except ValueError as exc:
        raise typer.BadParameter(f"--as-of must be YYYY-MM-DD: {exc}") from exc
    try:
        result = run_scan(load_scan(data_dir, name), data_dir=data_dir, as_of=cutoff)
    except DataError as exc:
        raise _bad(exc) from exc
    if json_out:
        typer.echo(json.dumps(result))
        return
    for row in result["rows"]:
        typer.echo(f"{row['symbol']}: {row['signal']:+d} on {row['bar_date']}")
    for item in result["skipped"]:
        typer.echo(f"{item['symbol']}: skipped ({item['reason']})")


@scan_app.command("check")
def check(
    name: str | None = typer.Argument(None, help="scan name; omit to check every saved scan"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Run and append deduplicated alerts for signals that changed since the last check."""
    data_dir = AlphaSettings().data_dir
    try:
        scans = (
            [load_scan(data_dir, name)]
            if name
            else [row for row in _saved_scans(data_dir) if "error" not in row]
        )
        results = [
            check_scan({k: s[k] for k in ("name", "rules", "universe")}, data_dir=data_dir)
            for s in scans
        ]
    except DataError as exc:
        raise _bad(exc) from exc
    payload = {
        "checks": results,
        "alerts": [alert for result in results for alert in result["alerts"]],
        "authority": "none",
    }
    if json_out:
        typer.echo(json.dumps(payload))
    else:
        for alert in payload["alerts"]:
            typer.echo(
                f"{alert['scan']} {alert['symbol']}: {alert['previous']} -> {alert['signal']}"
            )
        typer.echo(f"{len(results)} scan(s) checked, {len(payload['alerts'])} new alert(s)")


@scan_app.command("alerts")
def alerts(
    limit: int = typer.Option(_ALERT_LIMIT_DEFAULT, "--limit", min=1, help="newest N alerts"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """The alert log (oldest first within the tail)."""
    rows = read_alerts(AlphaSettings().data_dir, limit=limit)
    if json_out:
        typer.echo(json.dumps({"alerts": rows, "authority": "none"}))
    else:
        for alert in rows:
            typer.echo(
                f"{alert['ts']} {alert['scan']} {alert['symbol']}: "
                f"{alert['previous']} -> {alert['signal']} ({alert['bar_date']})"
            )
        if not rows:
            typer.echo("no alerts")
