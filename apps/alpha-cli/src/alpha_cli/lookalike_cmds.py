"""`alpha lookalike` and `alpha unusual`: shape search and novelty over one stored asset.

Thin glue over `alpha_patterns.lookalike` (the one STUMPY adapter, ADR-0051). Each command reads
the asset point-in-time, writes one result folder (`result.json` with spine-shaped facts and one
figure) and prints the facts. Looking at past matches together with what followed them is a
look at outcomes, so `alpha lookalike` appends an exploratory trial to the spine ledger.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import typer

from alpha_cli._cli_json import emit
from alpha_cli.spine.errors import SpineError, fail
from alpha_core import DataError
from alpha_core.config import AlphaSettings

#: The declared default threshold, in words: a shape correlation of at least this much. It is
#: converted to a distance from the window length alone, never from the data.
DEFAULT_MIN_CORRELATION = 0.80


def _parse_horizons(raw: str) -> tuple[int, ...]:
    try:
        values = tuple(int(part) for part in raw.split(",") if part.strip())
    except ValueError:
        raise typer.BadParameter("--horizons must be comma-separated whole numbers") from None
    if not values or any(value < 1 for value in values):
        raise typer.BadParameter("--horizons must be positive whole numbers")
    return values


def _load(asset: str, timeframe: str, home: Path) -> tuple[Any, Any, Any, Any]:
    from alpha_cli import _runner
    from alpha_cli.chart_cmds import to_ohlcv
    from alpha_cli.spine import reserve
    from alpha_cli.spine.stores import resolve_asset

    resolved = resolve_asset(asset, data_dir=home, timeframe=timeframe)
    held = reserve.hold(resolved.symbol, data_dir=resolved.data_dir, timeframe=timeframe)
    bars, _ = _runner.load_bars(
        resolved.symbol, data_dir=resolved.data_dir, timeframe=timeframe, as_of=held.as_of
    )
    return resolved, bars, to_ohlcv(bars), held


def _identity(kind: str, payload: dict[str, Any], bars: list[Any]) -> str:
    from alpha_cli import _runner

    body = json.dumps(
        {**payload, "kind": kind, "data": _runner.source_fingerprint(bars)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def _fact(
    metric: str, value: Any, basis: str, source: str, result_id: str, labels: list[str], reason: Any
) -> dict[str, Any]:
    return {
        "metric": metric,
        "value": value,
        "run_id": result_id,
        "basis": basis,
        "source": f"result.json:{source}",
        "labels": labels,
        "reason": reason if value is None else None,
    }


def _publish(rdir: Path, document: dict[str, Any], figure: tuple[bytes, bytes]) -> bool:
    """Write the folder once; an existing folder with the same identity is left untouched."""
    from alpha_core.atomic import publish, write_text

    if (rdir / "result.json").exists():
        return False
    rdir.mkdir(parents=True, exist_ok=True)
    publish(rdir / "figure.png", lambda path: path.write_bytes(figure[0]))
    publish(rdir / "figure_annotated.png", lambda path: path.write_bytes(figure[1]))
    write_text(
        rdir / "result.json",
        json.dumps(document, sort_keys=True, indent=2, allow_nan=False) + "\n",
    )
    return True


def _render(spec: Any) -> tuple[bytes, bytes]:
    """The plain chart and the annotated, explained chart, as PNG bytes."""
    from alpha_cli.figures.variants import render_variant

    return render_variant(spec, "plain", "png"), render_variant(spec, "annotated", "png")


def _iso(epoch_ms: float) -> str:
    from datetime import UTC, datetime

    return datetime.fromtimestamp(epoch_ms / 1000.0, tz=UTC).isoformat()


def _error(exc: Exception, command: str) -> SpineError:
    if isinstance(exc, SpineError):
        return exc
    message = str(exc)
    if "not found" in message or "unknown store" in message:
        return SpineError("UNKNOWN_ASSET", message, f"Run alpha {command} with a stored asset.")
    return SpineError(
        "LOOKALIKE_FAILED" if command == "lookalike" else "UNUSUAL_FAILED",
        message,
        f"Run alpha {command} again after correcting the reported input or data error.",
    )


def _lookalike_labels(result: Any, resolved: Any, labels_base: tuple[str, ...]) -> list[str]:
    return [
        f"N={len(result.matches)} matches",
        *labels_base,
        "exploratory",
        "price only, no costs",
        *(["source-defaulted"] if resolved.defaulted else []),
        *(["too few to summarise"] if len(result.matches) < 5 else []),
        *(
            [f"outcomes overlap for {result.overlapping_outcomes} pairs"]
            if result.overlapping_outcomes
            else []
        ),
        *(
            [f"outcomes of {result.outcomes_into_query} matches run into the query's own bars"]
            if result.outcomes_into_query
            else []
        ),
    ]


def _lookalike_trial_row(
    resolved: Any,
    last: int,
    timeframe: str,
    result_id: str,
    settings: dict[str, Any],
    labels: list[str],
) -> dict[str, Any]:
    return {
        "test_id": result_id,
        "name": f"lookalike {resolved.symbol} last {last} {timeframe}",
        "idea": "has price action like this happened before?",
        "rule": "lookalike",
        "symbol": resolved.symbol,
        "store": resolved.store_name,
        "source": resolved.source,
        "run_id": None,
        "result_id": result_id,
        "params": settings,
        "labels": labels,
    }


def _match_items(result: Any) -> list[dict[str, Any]]:
    return [
        {
            "start": _iso(match.start_ts),
            "end": _iso(match.end_ts),
            "distance": match.distance,
            "correlation": match.correlation,
            "what_happened_next": {
                str(outcome.horizon): {"value": outcome.value, "reason": outcome.reason}
                for outcome in match.what_happened_next
            },
        }
        for match in result.matches
    ]


def _lookalike_facts(
    result: Any,
    summaries: Sequence[Any],
    *,
    top: int,
    threshold: float,
    declared: str,
    looks: int,
    result_id: str,
    labels: list[str],
) -> list[dict[str, Any]]:
    def fact(
        metric: str, value: Any, basis: str, source: str, reason: Any = None
    ) -> dict[str, Any]:
        return _fact(metric, value, basis, source, result_id, labels, reason)

    facts = [
        fact(
            "matches",
            len(result.matches),
            f"lookalikes within the threshold, at most {top}, searched before the query",
            "search.matches",
        ),
        fact(
            "matches_within_threshold",
            result.matches_within_threshold,
            "every non-overlapping lookalike within the threshold, before the top cap",
            "search.matches_within_threshold",
        ),
        fact("max_distance", threshold, declared, "search.max_distance"),
        fact(
            "max_distance_correlation",
            result.max_distance_correlation,
            "the shape correlation equal to max_distance for this window length",
            "search.max_distance_correlation",
        ),
        fact(
            "lookalike_looks",
            looks,
            "lookalike trials in the ledger, this one included",
            "trial.looks",
        ),
    ]
    for summary in summaries:
        for name, value in (
            ("median", summary.median),
            ("mean", summary.mean),
            ("share_up", summary.share_up),
        ):
            facts.append(
                fact(
                    f"next_{summary.horizon}_{name}",
                    value,
                    f"what happened next: close-to-close change {summary.horizon} bars "
                    f"after each match completed, over {summary.count} matches; "
                    "descriptive, not a forecast",
                    f"what_happened_next.{summary.horizon}.{name}",
                    summary.reason,
                )
            )
    return facts


def _lookalike_document(
    result: Any,
    summaries: Sequence[Any],
    *,
    resolved: Any,
    settings: dict[str, Any],
    result_id: str,
    threshold: float,
    declared: str,
    trial_index: Any,
    looks: int,
    labels: list[str],
    facts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": "AlphaLookalikeV1",
        "result_id": result_id,
        "question": "Has price action like this happened before?",
        "settings": settings,
        "source": resolved.source,
        "query": {
            "start": _iso(result.query_start_ts),
            "end": _iso(result.query_end_ts),
        },
        "search": {
            "searched": "every stretch ending before the query starts",
            "candidates_searched": result.candidates_searched,
            "constant_candidates_skipped": result.constant_candidates_skipped,
            "matches": len(result.matches),
            "matches_within_threshold": result.matches_within_threshold,
            "max_distance": threshold,
            "max_distance_basis": declared,
            "max_distance_correlation": result.max_distance_correlation,
            "exclusion_bars": result.exclusion,
            "items": _match_items(result),
        },
        "what_happened_next": {
            str(summary.horizon): {
                "count": summary.count,
                "median": summary.median,
                "mean": summary.mean,
                "share_up": summary.share_up,
                "reason": summary.reason,
            }
            for summary in summaries
        },
        "trial": {"trial_index": trial_index, "looks": looks},
        "labels": labels,
        "facts": facts,
    }


def _lookalike_text(
    result: Any,
    summaries: Sequence[Any],
    *,
    resolved: Any,
    last: int,
    timeframe: str,
    result_id: str,
    declared: str,
    labels: list[str],
    rdir: Path,
) -> str:
    lines = [
        f"Lookalike {result_id} — {resolved.symbol}, last {last} {timeframe} bars "
        f"({_iso(result.query_start_ts)[:10]} to {_iso(result.query_end_ts)[:10]})",
        f"Matches: {len(result.matches)} (threshold: shape correlation "
        f"{result.max_distance_correlation:.2f}+; {declared})",
        "START\tEND\tCORRELATION",
        *(
            f"{_iso(match.start_ts)[:10]}\t{_iso(match.end_ts)[:10]}\t{match.correlation:.3f}"
            for match in result.matches
        ),
        "What happened next (descriptive, not a forecast):",
        *(
            f"  {s.horizon} bars: median {s.median:+.2%}, {s.share_up:.0%} rose, of {s.count}"
            if s.median is not None and s.share_up is not None
            else f"  {s.horizon} bars: {s.reason}"
            for s in summaries
        ),
        f"Labels: {', '.join(labels)}",
        f"Figure: {rdir / 'figure.png'}",
        f"Annotated figure: {rdir / 'figure_annotated.png'}",
    ]
    return "\n".join(lines)


def lookalike(
    asset: str = typer.Option(..., help="Symbol or symbol@store, e.g. SPY@alpaca."),
    last: int = typer.Option(30, min=5, help="The query: the latest N bars."),
    timeframe: str = typer.Option("1D", help="Stored bar size, e.g. 1D or 1h."),
    top: int = typer.Option(10, min=1, help="At most this many closest lookalikes."),
    horizons: str = typer.Option("5,10,20", help="Bars after each match to report, e.g. 5,10,20."),
    max_distance: float | None = typer.Option(
        None,
        help="Fixed shape distance a match may not exceed. Default: the distance equal to "
        "shape correlation 0.80 for this window length.",
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit one JSON result object."),
) -> None:
    """Has price action like the latest N bars happened before? (descriptive, not a forecast)"""
    from alpha_cli._lookalike_figures import lookalike_figure
    from alpha_cli.spine.ledger import append_trial, read_trials
    from alpha_patterns.lookalike import (
        LABELS,
        describe_outcomes,
        distance_for_correlation,
        find_lookalikes,
    )

    steps = _parse_horizons(horizons)
    home = AlphaSettings().data_dir
    try:
        resolved, bars, series, held = _load(asset, timeframe, home)
        if len(series) < last:
            raise DataError(f"{resolved.symbol}: need at least {last} bars, got {len(series)}")
        threshold = (
            max_distance
            if max_distance is not None
            else distance_for_correlation(DEFAULT_MIN_CORRELATION, last)
        )
        declared = (
            "--max-distance given by the caller"
            if max_distance is not None
            else f"declared default: shape correlation {DEFAULT_MIN_CORRELATION:.2f}"
        )
        start_ts = float(series.ts[len(series) - last])
        result = find_lookalikes(
            series,
            start_ts,
            last,
            top_k=top,
            exclusion=last,
            max_distance=threshold,
            horizons=steps,
        )
        summaries = describe_outcomes(result)
        settings = {
            "asset": asset,
            "symbol": resolved.symbol,
            "store": resolved.store_name,
            "timeframe": timeframe,
            "window": last,
            "top_k": top,
            "horizons": list(steps),
            "max_distance": threshold,
            "exclusion": last,
        }
        result_id = _identity("lookalike", settings, bars)
        labels = held.label(_lookalike_labels(result, resolved, tuple(LABELS)))
        rdir = home / "lookalike" / result_id
        if (rdir / "result.json").exists():
            labels.append("repeat")
        trial = append_trial(
            home, _lookalike_trial_row(resolved, last, timeframe, result_id, settings, labels)
        )
        looks = sum(1 for row in read_trials(home) if row.get("rule") == "lookalike")
        facts = _lookalike_facts(
            result,
            summaries,
            top=top,
            threshold=threshold,
            declared=declared,
            looks=looks,
            result_id=result_id,
            labels=labels,
        )
        document = _lookalike_document(
            result,
            summaries,
            resolved=resolved,
            settings=settings,
            result_id=result_id,
            threshold=threshold,
            declared=declared,
            trial_index=trial["trial_index"],
            looks=looks,
            labels=labels,
            facts=facts,
        )
        document.update(held.record_fields())
        figure = _render(
            lookalike_figure(
                series,
                result,
                summaries,
                asset=resolved.symbol,
                timeframe=timeframe,
                result_id=result_id,
                looks=looks,
            )
        )
        _publish(rdir, document, figure)
    except (ValueError, OSError, DataError) as exc:
        fail(_error(exc, "lookalike"), json_out)
    output = {
        **document,
        "result_dir": str(rdir),
        "figure": str(rdir / "figure.png"),
        "figure_annotated": str(rdir / "figure_annotated.png"),
    }
    text = _lookalike_text(
        result,
        summaries,
        resolved=resolved,
        last=last,
        timeframe=timeframe,
        result_id=result_id,
        declared=declared,
        labels=labels,
        rdir=rdir,
    )
    emit(output, json_out=json_out, fallback=text + held.note())


def unusual(
    asset: str = typer.Option(..., help="Symbol or symbol@store, e.g. BTC/USDT."),
    window: int = typer.Option(30, min=5, help="Stretch length in bars."),
    timeframe: str = typer.Option("1D", help="Stored bar size, e.g. 1D or 1h."),
    json_out: bool = typer.Option(False, "--json", help="Emit one JSON result object."),
) -> None:
    """How unlike every earlier stretch are the latest N bars? (unusual, not up or down)"""
    from alpha_cli._lookalike_figures import unusual_figure
    from alpha_patterns.lookalike import LABELS, novelty_score

    home = AlphaSettings().data_dir
    try:
        resolved, bars, series, held = _load(asset, timeframe, home)
        result = novelty_score(series, window, as_of=float(series.ts[-1]))
        settings = {
            "asset": asset,
            "symbol": resolved.symbol,
            "store": resolved.store_name,
            "timeframe": timeframe,
            "window": window,
            "warmup": result.warmup,
        }
        result_id = _identity("unusual", settings, bars)
        labels = held.label(
            [
                f"N={result.earlier_scores} earlier windows",
                *LABELS,
                "unusual is not up or down",
                *(["source-defaulted"] if resolved.defaulted else []),
            ]
        )
        rdir = home / "unusual" / result_id
        facts = [
            _fact(
                "novelty_score",
                result.score,
                "distance of the latest window to its closest earlier window (left matrix "
                "profile, z-normalised)",
                "novelty.score",
                result_id,
                labels,
                None,
            ),
            _fact(
                "novelty_correlation",
                result.correlation,
                "shape correlation with that closest earlier window",
                "novelty.correlation",
                result_id,
                labels,
                None,
            ),
            _fact(
                "novelty_percentile",
                result.percentile,
                f"share of {result.earlier_scores} earlier scored windows below the latest",
                "novelty.percentile",
                result_id,
                labels,
                result.percentile_reason,
            ),
        ]
        document = {
            "schema": "AlphaUnusualV1",
            "result_id": result_id,
            "question": "What is unusual right now?",
            "settings": settings,
            "source": resolved.source,
            "novelty": {
                "as_of": _iso(result.as_of_ts),
                "score": result.score,
                "correlation": result.correlation,
                "percentile": result.percentile,
                "percentile_reason": result.percentile_reason,
                "earlier_scores": result.earlier_scores,
                "warmup_bars": result.warmup,
                "exclusion_zone_bars": result.exclusion_zone,
                "constant_windows": result.constant_windows,
                "basis": "each window against earlier windows only (STUMPY left matrix profile)",
            },
            "labels": labels,
            "facts": facts,
            **held.record_fields(),
        }
        figure = _render(
            unusual_figure(
                series, result, asset=resolved.symbol, timeframe=timeframe, result_id=result_id
            )
        )
        _publish(rdir, document, figure)
    except (ValueError, OSError, DataError) as exc:
        fail(_error(exc, "unusual"), json_out)
    output = {
        **document,
        "result_dir": str(rdir),
        "figure": str(rdir / "figure.png"),
        "figure_annotated": str(rdir / "figure_annotated.png"),
    }
    rank = (
        f"higher than {result.percentile:.0f}% of {result.earlier_scores} earlier windows"
        if result.percentile is not None
        else result.percentile_reason
    )
    lines = [
        f"Unusual {result_id} — {resolved.symbol}, latest {window} {timeframe} bars "
        f"to {_iso(result.as_of_ts)[:10]}",
        f"Score {result.score:.3f} (closest earlier shape correlation {result.correlation:.2f}); "
        f"{rank}",
        f"Labels: {', '.join(labels)}",
        f"Figure: {rdir / 'figure.png'}",
        f"Annotated figure: {rdir / 'figure_annotated.png'}",
    ]
    emit(output, json_out=json_out, fallback="\n".join(lines) + held.note())
