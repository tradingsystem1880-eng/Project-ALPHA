"""Independent reference: upstream Qlib's own provider + Alpha158 handler on a dumped panel.

Run as a separate process (``qlib.init`` mutates process-global configuration):

    python upstream_alpha158_reference.py PANEL.parquet PROVIDER_DIR OUTPUT.parquet

The panel is written in Qlib's file-provider layout (``calendars/day.txt``,
``instruments/all.txt``, ``features/<code>/<field>.day.bin`` as little-endian float32 with the
start calendar index first), exactly as upstream's ``scripts/dump_bin.py`` lays it out. Nothing
from ``alpha_qlib_worker`` is imported: features come from ``qlib.contrib.data.handler.Alpha158``
loading through ``qlib.data.D`` with no processors.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

FIELDS = ("open", "high", "low", "close", "volume", "vwap")


def dump_provider(panel: pd.DataFrame, root: Path) -> pd.DatetimeIndex:
    calendar = pd.DatetimeIndex(sorted(panel["session_ts"].unique()))
    (root / "calendars").mkdir(parents=True)
    (root / "instruments").mkdir()
    (root / "calendars" / "day.txt").write_text(
        "".join(f"{day:%Y-%m-%d}\n" for day in calendar), encoding="utf-8"
    )
    lines = []
    for symbol, rows in panel.groupby("symbol", sort=True):
        positions = calendar.get_indexer(pd.DatetimeIndex(rows["session_ts"]))
        first, last = int(positions.min()), int(positions.max())
        lines.append(f"{symbol}\t{calendar[first]:%Y-%m-%d}\t{calendar[last]:%Y-%m-%d}\n")
        dense = rows.set_index("session_ts").reindex(calendar[first : last + 1])
        target = root / "features" / str(symbol).lower()
        target.mkdir(parents=True)
        for field in FIELDS:
            np.hstack([[first], dense[field].to_numpy(dtype="float64")]).astype("<f").tofile(
                target / f"{field}.day.bin"
            )
    (root / "instruments" / "all.txt").write_text("".join(lines), encoding="utf-8")
    return calendar


def main(panel_path: str, provider: str, output: str) -> None:
    panel = pd.read_parquet(panel_path)
    panel["session_ts"] = pd.DatetimeIndex(panel["session_ts"]).tz_localize(None)
    root = Path(provider)
    calendar = dump_provider(panel, root)

    import qlib
    from qlib.contrib.data.handler import Alpha158

    qlib.init(
        provider_uri=str(root), region="cn", kernels=1, expression_cache=None, dataset_cache=None
    )
    handler = Alpha158(
        instruments="all",
        start_time=calendar[0],
        end_time=calendar[-1],
        infer_processors=[],
        learn_processors=[],
    )
    features = handler.fetch(col_set="feature")
    features.reset_index().to_parquet(output)


if __name__ == "__main__":
    main(*sys.argv[1:])
