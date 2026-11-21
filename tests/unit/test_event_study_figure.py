"""Event study rendering is pure and byte stable."""

import struct

from alpha_cli.spine.event_study_figure import draw_event_study


def draw() -> bytes:
    return draw_event_study(
        paths=[[0.0, 0.01, 0.02], [0.0, -0.01, None]],
        mean=[0.0, 0.0, 0.02],
        drift=[0.0, 0.001, 0.002],
        lower=[0.0, -0.02, -0.03],
        upper=[0.0, 0.02, 0.03],
        horizons=[1, 2],
        primary=2,
        title="Synthetic: 2 separate occurrences (3 matching days)",
    )


def test_dimensions_and_bytes() -> None:
    data = draw()
    assert data == draw()
    assert struct.unpack(">II", data[16:24]) == (1600, 900)
    assert b"Matplotlib" not in data
