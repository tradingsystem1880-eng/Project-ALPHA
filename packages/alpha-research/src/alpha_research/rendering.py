"""Deterministic Matplotlib rendering for immutable research chart contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO

from alpha_research.artifacts import ResearchChartData

_COLORS = ("#5DADE2", "#F5B041", "#58D68D", "#AF7AC5", "#EC7063", "#AAB7B8")


def _tick_values(chart: ResearchChartData) -> tuple[list[float], list[str]]:
    timestamps = sorted(
        {point.ts.timestamp() for series in chart.series for point in series.points}
    )
    if len(timestamps) <= 5:
        selected = timestamps
    else:
        indexes = {round(index * (len(timestamps) - 1) / 4) for index in range(5)}
        selected = [timestamps[index] for index in sorted(indexes)]
    labels = [
        datetime.fromtimestamp(value, tz=UTC).strftime("%Y-%m-%d\n%H:%M UTC") for value in selected
    ]
    return selected, labels


def render_research_line_chart(chart: ResearchChartData) -> bytes:
    """Render a byte-stable PNG with visible status and embedded teaching metadata.

    Stability is guaranteed only within ALPHA's locked Python, Matplotlib, and font environment.
    The output deliberately contains no creation timestamp.
    """
    from matplotlib import rc_context
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    metadata = {
        "Software": "Project ALPHA alpha_research",
        "Title": chart.title,
        "Watermark": chart.watermark,
        "Question": chart.question,
        "PlainLanguageAnswer": chart.plain_language_answer,
        "Uncertainty": chart.uncertainty,
        "Caveat": chart.caveat,
        "RunID": chart.run_id,
        "ArtifactID": chart.artifact_id,
        "DatasetSHA256": chart.dataset_sha256,
        "ProtocolSHA256": chart.protocol_sha256,
        "ChartContractSHA256": chart.contract_hash,
    }
    style = {
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.facecolor": "#111820",
        "axes.edgecolor": "#607080",
        "axes.labelcolor": "#DCE6EE",
        "figure.facecolor": "#0B1117",
        "savefig.facecolor": "#0B1117",
        "text.color": "#EAF2F8",
        "xtick.color": "#AAB7C4",
        "ytick.color": "#AAB7C4",
    }
    with rc_context(style):  # type: ignore[arg-type]  # matplotlib's rc-key Literal is exhaustive
        figure = Figure(figsize=(8.0, 4.5), dpi=120)
        canvas = FigureCanvasAgg(figure)
        axes = figure.add_subplot(1, 1, 1)
        for index, series in enumerate(sorted(chart.series, key=lambda item: item.series_id)):
            axes.plot(
                [point.ts.timestamp() for point in series.points],
                [point.value for point in series.points],
                color=_COLORS[index % len(_COLORS)],
                label=series.label,
                linewidth=1.8,
            )
        axes.set_xlabel(chart.x_label)
        axes.set_ylabel(chart.y_label)
        axes.grid(visible=True, color="#34495E", linewidth=0.6, alpha=0.65)
        axes.legend(loc="best", frameon=False)
        tick_values, tick_labels = _tick_values(chart)
        axes.set_xticks(tick_values, labels=tick_labels)
        figure.suptitle(chart.title, x=0.1, y=0.975, ha="left", fontsize=13, fontweight="bold")
        figure.text(0.1, 0.915, chart.question, ha="left", va="top", fontsize=8.5)
        figure.text(
            0.1,
            0.025,
            chart.plain_language_answer,
            ha="left",
            va="bottom",
            fontsize=7.5,
            color="#B8C5CF",
        )
        figure.text(
            0.99,
            0.025,
            chart.watermark,
            ha="right",
            va="bottom",
            fontsize=8,
            fontweight="bold",
            color="#F5B041" if chart.evidence_phase == "exploratory" else "#58D68D",
        )
        figure.subplots_adjust(left=0.1, right=0.97, bottom=0.19, top=0.82)
        output = BytesIO()
        canvas.print_png(output, metadata=metadata)  # type: ignore[no-untyped-call]
        figure.clear()
        return output.getvalue()
