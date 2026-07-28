"""The live read: what every condition says about XRP right now, and what that is worth.

The study says what these conditions were worth historically. This says which of them are true
today, on the last bar in the data, so the two can be put side by side.

Two rules keep this from becoming a horoscope:

* **Every live condition is printed with its measured lift and interval**, not just its on/off
  state. A condition that is true today and historically worthless is reported as true and
  worthless, in the same row. Listing which conditions are "firing" without their track record is
  precisely the move this whole project exists to avoid.
* **The confluence count is reported with its measured direction.** On XRP that direction is
  negative — more bullish conditions has historically meant a *lower* forward hit rate — so the
  stack is shown with the sign the data gives it rather than the sign intuition expects.

The last bar is not today. The data ends where the mirrors end, and the gap is stated.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from research.xrp_deep import config as C
from research.xrp_deep.conditions import build_conditions, screen
from research.xrp_deep.deepdive import CONFLUENCE_BULLISH
from research.xrp_deep.directionality import run as run_directionality
from research.xrp_deep.panel import build_panel
from research.xrp_deep.study import run_study

OUT = Path(__file__).resolve().parent / "out"


@dataclass(frozen=True)
class LiveRow:
    """One condition's current state next to what it was historically worth."""

    condition: str
    family: str
    live: bool
    up_lift: float
    down_lift: float
    directional_edge: float
    verdict: str
    survived_fdr: bool

    def line(self) -> str:
        state = "ON " if self.live else "off"
        flag = " *FDR" if self.survived_fdr else ""
        return (
            f"  {state} {self.condition:24} {self.family:10} "
            f"up {self.up_lift:>+6.1%}  down {self.down_lift:>+6.1%}  "
            f"edge {self.directional_edge:>+6.1%}  {self.verdict}{flag}"
        )


def build_scorecard(horizon: int = C.PRIMARY_HORIZON) -> dict[str, Any]:
    panel = build_panel()
    conditions, _ = screen(build_conditions(panel))
    last = len(panel) - 1

    direc = {(r.condition, r.horizon): r for r in run_directionality(panel)}
    survivors = {c.condition for c in run_study(panel).survivors}

    rows: list[LiveRow] = []
    for cond in conditions:
        info = direc.get((cond.key, horizon))
        if info is None:
            continue
        rows.append(
            LiveRow(
                condition=cond.key,
                family=cond.family,
                live=bool(cond.mask[last] and cond.valid[last]),
                up_lift=info.up_lift,
                down_lift=info.down_lift,
                directional_edge=info.directional_edge,
                verdict=info.verdict,
                survived_fdr=cond.key in survivors,
            )
        )

    by_key = {c.key: c for c in conditions}
    stack = [k for k in CONFLUENCE_BULLISH if k in by_key]
    live_stack = [k for k in stack if by_key[k].mask[last] and by_key[k].valid[last]]

    features = panel.features
    return {
        "last_date": panel.dates[-1],
        "last_close": float(panel.bars.close[last]),
        "rows": rows,
        "confluence_live": len(live_stack),
        "confluence_total": len(stack),
        "confluence_live_conditions": live_stack,
        "readings": {
            name: float(features[name][last])
            for name in (
                "price_over_sma200",
                "price_over_sma50",
                "rsi_14",
                "adx",
                "bandwidth_pct",
                "vol_pct",
                "donchian_position",
                "range_position_365",
                "drawdown_from_ath",
                "corr_btc_90",
                "ratio_over_ma",
                "variance_ratio_5",
                "hurst_returns",
                "cmf",
                "mfi",
            )
            if name in features and np.isfinite(features[name][last])
        },
    }


def main() -> int:
    card = build_scorecard()
    rows: list[LiveRow] = card["rows"]
    live = [r for r in rows if r.live]

    print("=" * 104)
    print(f"XRP LIVE SCORECARD — last bar {card['last_date']}, close {card['last_close']:.4f}")
    print("=" * 104)
    print("\n  The data ends where the mirrors end. This is the last bar available, not today.")

    print("\n  READINGS")
    for name, value in card["readings"].items():
        print(f"    {name:22} {value:>10.4f}")

    print(f"\n  CONDITIONS CURRENTLY TRUE: {len(live)} of {len(rows)}")
    print(f"  (each shown with its measured {C.PRIMARY_HORIZON}-day effect — state without")
    print("   track record is a horoscope)\n")
    for row in sorted(live, key=lambda r: r.directional_edge, reverse=True):
        print(row.line())

    print("\n  BULLISH-CONFLUENCE STACK")
    n_live, n_total = card["confluence_live"], card["confluence_total"]
    print(
        f"    {n_live} of {n_total} bullish conditions are on: {card['confluence_live_conditions']}"
    )
    print("    Measured direction of this stack on XRP: NEGATIVE (z=-3.98 on independent counts).")
    print("    More bullish conditions has historically meant a LOWER 30-day forward hit rate —")
    print(f"    58% at zero conditions, 27% at ten. {n_live} of {n_total} is therefore a")
    print("    mildly constructive reading, not a weak one.")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "scorecard.json").write_text(
        json.dumps(
            {
                "last_date": card["last_date"],
                "last_close": card["last_close"],
                "confluence_live": n_live,
                "confluence_total": n_total,
                "confluence_live_conditions": card["confluence_live_conditions"],
                "readings": card["readings"],
                "live_conditions": [
                    {
                        "condition": r.condition,
                        "family": r.family,
                        "up_lift": r.up_lift,
                        "down_lift": r.down_lift,
                        "directional_edge": r.directional_edge,
                        "verdict": r.verdict,
                        "survived_fdr": r.survived_fdr,
                    }
                    for r in live
                ],
            },
            indent=2,
            default=float,
        )
    )
    print(f"\nwrote {OUT / 'scorecard.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
