"""Figure builders: exposure."""

from __future__ import annotations

from alpha_cli.figures import _sources as src
from alpha_cli.figures._common import BuildContext, _day, _truncation, pct
from alpha_core import DataError
from alpha_research.figures import (
    BarMark,
    FigureSpec,
    LineMark,
    Mark,
    Panel,
    TableMark,
    ZoneMark,
)


def drawdown_episodes(ctx: BuildContext) -> FigureSpec:
    from alpha_validation import drawdown_episodes as compute

    frame = src.require(ctx.rdir, "equity_curve.parquet", "ts")
    ts = src.epochs(frame["ts"])
    equity = src.rebase(src.floats(frame["equity"], name="equity"))
    episodes = compute(equity, top=5)
    if not episodes:
        raise DataError("this run never drew down; there are no episodes to show")
    zones: list[Mark] = [LineMark(x=ts, y=equity, role="subject", label="Equity")]
    rows: list[tuple[str, ...]] = []
    for rank, episode in enumerate(episodes, start=1):
        end_index = episode.recovery_index if episode.recovery_index is not None else len(ts) - 1
        zones.append(
            ZoneMark(
                x0=ts[episode.peak_index],
                x1=ts[end_index],
                role="down",
                alpha=0.16,
                label="Drawdown window" if rank == 1 else None,
            )
        )
        rows.append(
            (
                str(rank),
                pct(episode.depth),
                _day(ts[episode.peak_index]),
                _day(ts[episode.trough_index]),
                _day(ts[episode.recovery_index]) if episode.recovery_index is not None else "open",
                f"{episode.length}",
                "-" if episode.recovery_length is None else f"{episode.recovery_length}",
            )
        )
    unrecovered = sum(1 for item in episodes if item.recovery_index is None)
    return ctx.spec(
        "drawdown_episodes",
        x_label="Date (UTC)",
        artifacts=("equity_curve.parquet",),
        answer=(
            f"The worst drawdown was {pct(episodes[0].depth)} over {episodes[0].length} sessions"
            + (
                "; it had not recovered by the end of the window."
                if unrecovered
                else f", recovering in {episodes[0].recovery_length} sessions."
            )
        ),
        panels=(
            Panel(
                panel_id="equity",
                y_label="Growth of 1 (x initial)",
                y_unit="multiple",
                height_ratio=2.0,
                marks=tuple(zones),
            ),
            Panel(
                panel_id="table",
                y_label="Episodes (count)",
                y_unit="count",
                legend=False,
                height_ratio=1.1,
                marks=(
                    TableMark(
                        columns=(
                            "#",
                            "Depth",
                            "Peak",
                            "Trough",
                            "Recovered",
                            "To trough",
                            "To recover",
                        ),
                        rows=tuple(rows),
                    ),
                ),
            ),
        ),
    )


def exposure_turnover(ctx: BuildContext) -> FigureSpec:
    frame = src.require(ctx.rdir, "exposure_turnover.parquet", "start_ts")
    picked = src.sample(frame.height)
    view = frame[picked]
    ts = src.epochs(view["start_ts"])
    exposure_ok = bool(view["exposure_available"].to_list()[0])
    turnover_ok = bool(view["turnover_available"].to_list()[0])
    if not exposure_ok and not turnover_ok:
        raise DataError("neither exposure nor turnover is available for this run")
    panels: list[Panel] = []
    if exposure_ok:
        gross = tuple(v or 0.0 for v in src.optional_floats(view["gross_exposure"]))
        net = tuple(v or 0.0 for v in src.optional_floats(view["net_exposure"]))
        panels.append(
            Panel(
                panel_id="exposure",
                y_label="Exposure (x net liquidation)",
                y_unit="ratio",
                y_zero_rule=True,
                marks=(
                    LineMark(x=ts, y=gross, role="subject", label="Gross"),
                    LineMark(x=ts, y=net, role="neutral", label="Net", fill_to=0.0),
                ),
            )
        )
    else:
        panels.append(
            Panel(
                panel_id="exposure",
                y_label="Exposure (x net liquidation)",
                y_unit="ratio",
                legend=False,
                note=str(
                    view["exposure_unavailable_reason"].to_list()[0] or "exposure unavailable"
                ),
                marks=(LineMark(x=ts, y=tuple(0.0 for _ in ts), role="substrate"),),
            )
        )
    if turnover_ok:
        turnover = tuple(v or 0.0 for v in src.optional_floats(view["turnover"]))
        panels.append(
            Panel(
                panel_id="turnover",
                y_label="Turnover (x net liquidation)",
                y_unit="ratio",
                legend=False,
                marks=(BarMark(x=ts, y=turnover, role="neutral", alpha=0.8),),
            )
        )
    else:
        panels.append(
            Panel(
                panel_id="turnover",
                y_label="Turnover (x net liquidation)",
                y_unit="ratio",
                legend=False,
                note=str(
                    view["turnover_unavailable_reason"].to_list()[0] or "turnover unavailable"
                ),
                marks=(LineMark(x=ts, y=tuple(0.0 for _ in ts), role="substrate"),),
            )
        )
    if exposure_ok:
        gross_values = [v or 0.0 for v in src.optional_floats(view["gross_exposure"])]
        peak = max(gross_values)
        answer = f"Gross exposure peaked at {peak:.2f}x net liquidation."
    else:
        answer = "Exposure is not recorded for this run type."
    return ctx.spec(
        "exposure_turnover",
        x_label="Date (UTC)",
        artifacts=("exposure_turnover.parquet",),
        truncation=_truncation(frame.height, len(picked), "sessions"),
        answer=answer,
        panels=tuple(panels),
    )
