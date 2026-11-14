"""Build RD-Agent's daily frames and check generated code for prefix invariance."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

CUTS = (
    ("2020-12-31",)
    + tuple(
        f"{year}-{day}"
        for year in (2021, 2022, 2023)
        for day in ("03-31", "06-30", "09-30", "12-31")
        if f"{year}-{day}" <= "2023-09-30"
    )
    + ("2023-12-24",)
)
README = """# Daily price and volume data

15 Binance USDT spot coins, daily bars. Row d is the bar that opened at 00:00 UTC
on day d and is known at its close. Data ends 2023-12-31; 2024 onward is reserved.

Read with `pd.read_hdf('daily_pv.h5', key='data')`.

| File | Contents |
| --- | --- |
| daily_pv.h5 | DataFrame, key data; sorted (datetime, instrument) index |

| Field | Meaning |
| --- | --- |
| $open, $high, $low, $close | Spot OHLC prices in USDT |
| $volume | Base-asset volume |
| $factor | 1.0, no adjustments |

All fields are float64. Factors are decided after the full day's close and judged
on the return from the next open to the following open, with costs.
"""


def prepare(panel: Path, out: Path) -> dict[str, Any]:
    frame = pd.read_parquet(panel)
    dates = pd.to_datetime(frame["date"], utc=True)
    if (
        dates.isna().any()
        or not dates.eq(dates.dt.normalize()).all()
        or dates.ge(pd.Timestamp("2024-01-01", tz="UTC")).any()
    ):
        raise ValueError("panel must contain midnight dates before the reserved window")
    frame["datetime"] = dates.dt.tz_localize(None)
    frame = frame.set_index(["datetime", "instrument"]).sort_index()
    if frame.index.has_duplicates:
        raise ValueError("duplicate factor data keys")
    frame = (
        frame[["open", "close", "high", "low", "volume"]]
        .rename(columns=lambda c: "$" + c)
        .astype("float64")
    )
    frame["$factor"] = 1.0
    out.mkdir(parents=True, exist_ok=False)
    parts = {
        "full": frame,
        "debug": frame.loc[
            (frame.index.get_level_values(0) >= "2021-01-01")
            & (frame.index.get_level_values(0) <= "2022-12-31")
        ],
    }
    parts.update({f"cuts/{cut}": frame.loc[frame.index.get_level_values(0) <= cut] for cut in CUTS})
    for name, data in parts.items():
        folder = out / name
        folder.mkdir(parents=True)
        data.to_hdf(folder / "daily_pv.h5", key="data", mode="w")
        if name in {"full", "debug"}:
            (folder / "README.md").write_text(README)
    receipt = {
        "schema": "AlphaRdagentFactorDataV1",
        "panel_sha256": hashlib.sha256(panel.read_bytes()).hexdigest(),
        "files": {
            str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(out.rglob("*"))
            if p.is_file()
        },
    }
    (out / "prepare-receipt.json").write_text(json.dumps(receipt, sort_keys=True) + "\n")
    return receipt


def _normalized(frame: pd.DataFrame) -> pd.DataFrame:
    if (
        not isinstance(frame, pd.DataFrame)
        or not isinstance(frame.index, pd.MultiIndex)
        or frame.index.nlevels != 2
        or frame.index.has_duplicates
    ):
        raise ValueError("factor output requires a unique (datetime, instrument) index")
    result = frame.copy()
    dates = pd.to_datetime(result.index.get_level_values(0), utc=True).tz_localize(None)
    result.index = pd.MultiIndex.from_arrays(
        [dates, result.index.get_level_values(1)], names=["datetime", "instrument"]
    )
    return result.sort_index()


def compare_prefix(full: pd.DataFrame, truncated: pd.DataFrame, cut: str) -> dict[str, Any] | None:
    full, truncated = _normalized(full), _normalized(truncated)
    expected = full.loc[full.index.get_level_values(0) <= pd.Timestamp(cut)]
    actual = truncated.loc[truncated.index.get_level_values(0) <= pd.Timestamp(cut)]
    if not expected.index.equals(actual.index) or list(expected.columns) != list(actual.columns):
        return {"cut": cut, "reason": "index or columns changed"}
    for index, (left, right) in enumerate(
        zip(expected.to_numpy().flat, actual.to_numpy().flat, strict=True)
    ):
        a, b = float(left), float(right)
        if math.isnan(a) and math.isnan(b):
            continue
        if (
            not math.isfinite(a)
            or not math.isfinite(b)
            or not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
        ):
            row, col = divmod(index, len(expected.columns))
            return {
                "cut": cut,
                "date": str(expected.index[row][0]),
                "instrument": str(expected.index[row][1]),
                "column": str(expected.columns[col]),
                "reason": "value or NaN position changed",
            }
    return None


def check_prefix_invariance(
    code: bytes, full_values: pd.DataFrame, cuts_dir: Path, python_bin: str, timeout: float
) -> dict[str, Any]:
    checked: list[dict[str, str]] = []
    for cut in CUTS:
        source = cuts_dir / cut / "daily_pv.h5"
        try:
            with tempfile.TemporaryDirectory(prefix="alpha-factor-cut-") as temporary:
                work = Path(temporary)
                (work / "factor.py").write_bytes(code)
                # A copy, not a symlink: resolving a link would lead the code to the full data.
                shutil.copyfile(source.resolve(strict=True), work / "daily_pv.h5")
                result = subprocess.run(
                    [python_bin, "factor.py"],
                    cwd=work,
                    env={
                        "HOME": temporary,
                        "LANG": "C.UTF-8",
                        "PATH": str(Path(python_bin).parent) + ":/usr/bin:/bin",
                    },
                    capture_output=True,
                    timeout=timeout,
                    check=False,
                )
                if result.returncode:
                    raise ValueError(f"truncated factor exit {result.returncode}")
                truncated = pd.read_hdf(work / "result.h5", key="data")
                mismatch = compare_prefix(full_values, truncated, cut)
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
            checked.append({"cut": cut, "status": "ERROR"})
            return {
                "status": "ERROR",
                "cuts": checked,
                "first_mismatch": {"cut": cut, "reason": str(error)},
            }
        checked.append({"cut": cut, "status": "LOOKAHEAD" if mismatch else "PASS"})
        if mismatch:
            return {"status": "LOOKAHEAD", "cuts": checked, "first_mismatch": mismatch}
    return {"status": "PASS", "cuts": checked, "first_mismatch": None}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build RD-Agent's daily frames for the ALPHA-judged factor loop."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--panel", type=Path, required=True)
    prepare_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.panel, args.out)


if __name__ == "__main__":
    main()
