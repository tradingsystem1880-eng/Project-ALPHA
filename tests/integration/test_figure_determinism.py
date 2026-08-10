"""A figure that cannot reproduce its own bytes cannot be content-addressed.

Every check runs in *fresh subprocesses*. That is not ceremony: the two nastiest sources
of drift -- matplotlib's per-process ``svg.hashsalt`` UUID and its module-level font and
rcParam caches -- are invisible to a same-process comparison.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_SCRIPT = textwrap.dedent(
    """
    import sys
    from pathlib import Path

    import alpha_research.figures as F

    fmt = sys.argv[2]
    n = 240
    ts = tuple(1_420_070_400.0 + i * 86_400.0 for i in range(n))
    equity = tuple(1.0 + 0.0004 * i + 0.02 * ((i * 37) % 11 - 5) / 5 for i in range(n))
    peak, drawdown = -1e18, []
    for value in equity:
        peak = max(peak, value)
        drawdown.append(value / peak - 1.0)

    spec = F.FigureSpec(
        figure_id="equity_underwater",
        title="Equity and drawdown",
        subtitle="SPY  -  ts_momentum  -  240 sessions",
        x_label="Date (UTC)",
        x_kind="time",
        panels=(
            F.Panel(
                panel_id="equity",
                y_label="Growth of 1 (x initial)",
                y_unit="multiple",
                height_ratio=2.6,
                marks=(
                    F.LineMark(x=ts, y=equity, role="subject", label="Strategy"),
                    F.RuleMark(orientation="horizontal", position=1.0, role="reference",
                               label="Start", width=0.9),
                ),
            ),
            F.Panel(
                panel_id="drawdown",
                y_label="Drawdown (%)",
                y_unit="percent",
                y_percent=True,
                legend=False,
                marks=(F.LineMark(x=ts, y=tuple(drawdown), role="down", fill_to=0.0),),
            ),
        ),
        question="How did capital grow, and how deep were the holes?",
        plain_language_answer="Equity rose steadily with shallow, frequent drawdowns.",
        uncertainty="One realised path; not a distribution.",
        caveat="Net of modelled fees only.",
        caption="run 0123456789abcdef - snapshot deadbeef - UTC",
    )
    options = F.RenderOptions(
        theme=F.load_theme(), size=F.default_size(2), fmt=fmt
    )
    Path(sys.argv[1]).write_bytes(F.render_figure(spec, options))
    """
)


def _render(target: Path, fmt: str, env: dict[str, str] | None = None) -> bytes:
    environment = {**os.environ, **(env or {})}
    subprocess.run([sys.executable, "-c", _SCRIPT, str(target), fmt], check=True, env=environment)
    return target.read_bytes()


@pytest.mark.parametrize("fmt", ["svg", "png"])
def test_two_fresh_processes_render_identical_bytes(tmp_path: Path, fmt: str) -> None:
    first = _render(tmp_path / f"first.{fmt}", fmt)
    second = _render(tmp_path / f"second.{fmt}", fmt)
    assert first == second


def test_a_hostile_user_matplotlibrc_cannot_change_the_output(tmp_path: Path) -> None:
    """The reason rcParams are seeded from ``rcParamsDefault`` rather than ``rcParams``.

    Without that reset a developer's personal matplotlib config silently rewrites every
    published figure -- different font size, white background, extra grid.
    """
    baseline = _render(tmp_path / "baseline.svg", "svg")

    home = tmp_path / "hostile-home"
    (home / ".config" / "matplotlib").mkdir(parents=True)
    (home / ".config" / "matplotlib" / "matplotlibrc").write_text(
        "font.size: 22\nfigure.facecolor: white\naxes.grid: False\nsvg.fonttype: none\n",
        encoding="utf-8",
    )
    hostile = _render(
        tmp_path / "hostile.svg",
        "svg",
        env={"HOME": str(home), "MPLCONFIGDIR": str(home / ".config" / "matplotlib")},
    )
    assert hostile == baseline


@pytest.mark.parametrize("seed", ["0", "1"])
def test_hash_randomisation_does_not_reach_the_output(tmp_path: Path, seed: str) -> None:
    baseline = _render(tmp_path / "baseline.svg", "svg", env={"PYTHONHASHSEED": "0"})
    other = _render(tmp_path / f"seed-{seed}.svg", "svg", env={"PYTHONHASHSEED": seed})
    assert other == baseline


@pytest.mark.parametrize("timezone", ["UTC", "Asia/Tokyo", "America/New_York"])
def test_the_host_timezone_never_shifts_a_date_label(tmp_path: Path, timezone: str) -> None:
    baseline = _render(tmp_path / "baseline.svg", "svg", env={"TZ": "UTC"})
    shifted = _render(tmp_path / "shifted.svg", "svg", env={"TZ": timezone})
    assert shifted == baseline


def test_no_creation_timestamp_is_embedded(tmp_path: Path) -> None:
    svg = _render(tmp_path / "stamp.svg", "svg")
    png = _render(tmp_path / "stamp.png", "png")
    assert b"dc:date" not in svg
    assert b"Matplotlib" not in png


def test_nothing_is_rasterised_into_the_svg(tmp_path: Path) -> None:
    """An embedded raster blob would defeat both scaling and byte stability."""
    svg = _render(tmp_path / "vector.svg", "svg")
    assert b"<image" not in svg


def test_a_different_render_option_produces_different_bytes(tmp_path: Path) -> None:
    """The negative case: proves the cache key has something real to key on."""
    assert _render(tmp_path / "a.svg", "svg") != _render(tmp_path / "a.png", "png")
