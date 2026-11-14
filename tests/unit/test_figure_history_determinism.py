"""Hash-bound image bytes must not depend on earlier renders or Matplotlib styles."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.style
import numpy as np
import pytest
from cycler import cycler

from alpha_research.figures.render import RenderOptions, default_size, render_figure
from alpha_research.figures.spec import FigureSpec, LineMark, Panel
from alpha_research.figures.theme import load_theme
from alpha_research.rendering import render_research_line_chart
from alpha_validation import tearsheet
from tests.unit.test_research_chart_rendering import _chart, _series

_RESEARCH_SHA256 = "18538bf605320bdfe580031d611b79cd745cd102f7af5247ea62c4bb804098b7"
_TEARSHEET_SHA256 = "7d0caab1f81acd42b08c4ace3d0413adcf46fb74922cd111150627f2b7ce6e2b"


def _defaults() -> dict[Any, Any]:
    return {key: value for key, value in matplotlib.rcParamsDefault.items() if key != "backend"}


def _research() -> bytes:
    return render_research_line_chart(_chart((_series("event", 0.01), _series("control", 0.0))))


def _figure(fmt: str) -> bytes:
    assert fmt in {"svg", "png"}
    start = datetime(2024, 1, 1, tzinfo=UTC).timestamp()
    x = tuple(start + index * 86400 for index in range(4))
    spec = FigureSpec(
        figure_id="history-determinism",
        title="Two time series",
        subtitle="Fixed reference inputs",
        x_label="Date (UTC)",
        x_kind="time",
        panels=(
            Panel(
                panel_id="price",
                y_label="Price",
                y_unit="price",
                marks=(LineMark(x=x, y=(10.0, 12.0, 11.0, 14.0)),),
            ),
            Panel(
                panel_id="return",
                y_label="Return (ratio)",
                y_unit="ratio",
                marks=(LineMark(x=x, y=(0.0, 0.2, 0.1, 0.4)),),
            ),
        ),
        question="Did both series rise?",
        plain_language_answer="Both finish above their starting value.",
        uncertainty="Illustrative fixed values.",
        caveat="No market evidence.",
    )
    return render_figure(
        spec,
        RenderOptions(
            theme=load_theme(), size=default_size(2), fmt="svg" if fmt == "svg" else "png"
        ),
    )


def _tearsheet(path: Path) -> bytes:
    count = 120
    returns = np.random.default_rng(7).normal(0.0005, 0.01, count)
    start = datetime(2020, 1, 1, tzinfo=UTC)
    timestamps = [start + timedelta(days=index) for index in range(count)]
    tearsheet.render_returns_tearsheet(
        returns,
        timestamps,
        title="ALPHA deterministic export",
        summary_rows=(("Run", "0123456789abcdef"),),
        output_path=path,
    )
    return path.read_bytes()


def _tick_size() -> None:
    matplotlib.rcParams["xtick.major.size"] = 6.0


def _quantstats_restyle() -> None:
    import quantstats_lumi._plotting.core as core

    importlib.reload(core)


def _canvas_colours() -> None:
    matplotlib.rcParams.update({"axes.facecolor": "#ffeedd", "grid.color": "#ff0000"})


def _ggplot() -> None:
    matplotlib.style.use("ggplot")


def _local_config() -> None:
    matplotlib.rcParams.update(
        {
            "font.size": 17,
            "lines.linewidth": 4,
            "timezone": "Pacific/Kiritimati",
            "axes.prop_cycle": cycler(color=["red", "green"]),
            "text.hinting": "none",
        }
    )


def _other_figures() -> None:
    from matplotlib import pyplot

    render_research_line_chart(_chart((_series("earlier", 0.05),)))
    _figure("png")
    figure = pyplot.figure()
    pyplot.close(figure)


_POLLUTIONS = (_tick_size, _quantstats_restyle, _ggplot, _local_config, _other_figures)


@pytest.mark.parametrize("pollute", _POLLUTIONS, ids=lambda fn: fn.__name__)
@pytest.mark.parametrize("writer", ("research", "svg", "png"))
def test_figure_bytes_ignore_process_history(writer: str, pollute: Callable[[], None]) -> None:
    render = _research if writer == "research" else lambda: _figure(writer)
    with matplotlib.rc_context(_defaults()):
        before = render()
        if writer == "research":
            assert hashlib.sha256(before).hexdigest() == _RESEARCH_SHA256
        with matplotlib.rc_context():
            pollute()
            after = render()
        assert after == before


@pytest.mark.parametrize(
    "pollute", (_canvas_colours, _ggplot, _local_config), ids=lambda fn: fn.__name__
)
def test_tearsheet_bytes_ignore_process_history(
    tmp_path: Path,
    pollute: Callable[[], None],
) -> None:
    with matplotlib.rc_context(_defaults()):
        _quantstats_restyle()
        before = _tearsheet(tmp_path / "before.html")
        assert hashlib.sha256(before).hexdigest() == _TEARSHEET_SHA256
        with matplotlib.rc_context():
            pollute()
            after = _tearsheet(tmp_path / "after.html")
        assert after == before


def test_tearsheet_preserves_process_rcparams(tmp_path: Path) -> None:
    # A fresh process, so this tear sheet is the first import of QuantStats and its
    # import-time restyling would show if it leaked; backend selection is excluded.
    script = (
        "import sys; from pathlib import Path; import matplotlib; "
        "from tests.unit.test_figure_history_determinism import _tearsheet; "
        "keep = lambda: {k: repr(v) for k, v in matplotlib.rcParams.items() "
        "if k not in ('backend', 'backend_fallback')}; "
        "assert 'quantstats_lumi' not in sys.modules; "
        "before = keep(); _tearsheet(Path(sys.argv[1])); "
        "changed = sorted(k for k, v in keep().items() if before[k] != v); "
        "assert not changed, changed"
    )
    subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "tearsheet.html")],
        check=True,
        cwd=Path(__file__).resolve().parents[2],
    )


def test_research_preserves_backend() -> None:
    backend = matplotlib.get_backend()
    try:
        matplotlib.use("svg")
        _research()
        assert matplotlib.get_backend() == "svg"
    finally:
        matplotlib.use(backend)


def test_quantstats_style_matches_fresh_import(tmp_path: Path) -> None:
    script = (
        "import json, matplotlib; import quantstats_lumi; "
        "print(json.dumps({key: repr(value) for key, value in matplotlib.rcParams.items() "
        "if key != 'backend'}))"
    )
    config = tmp_path / "matplotlibrc"
    config.write_text("", encoding="utf-8")
    fresh = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "MATPLOTLIBRC": str(config)},
    )
    with matplotlib.rc_context():
        _local_config()
        before = dict(matplotlib.rcParams)
        style = tearsheet._quantstats_style()
        assert "backend" not in style
        assert {key: repr(value) for key, value in style.items()} == json.loads(fresh.stdout)
        assert dict(matplotlib.rcParams) == before
