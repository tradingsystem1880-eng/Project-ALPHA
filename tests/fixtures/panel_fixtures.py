"""Hand-computed T×N panels shared by the Phase C panel-primitive unit and oracle tests."""

from __future__ import annotations

import numpy as np

# Names A..F; the signal ranks 1..6 on every date.
SIGNAL_3X6 = np.array([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]] * 3)
# Date 0: perfectly aligned (rho = 1); date 1: reversed (rho = -1);
# date 2: outcome ranks 2,1,4,3,6,5 -> sum d^2 = 6 -> rho = 1 - 36/210 = 29/35.
OUTCOME_3X6 = np.array(
    [
        [0.01, 0.02, 0.03, 0.04, 0.05, 0.06],
        [0.06, 0.05, 0.04, 0.03, 0.02, 0.01],
        [0.02, 0.01, 0.04, 0.03, 0.06, 0.05],
    ]
)
EXPECTED_IC_VALUES = (1.0, -1.0, 29 / 35)
EXPECTED_IC_MEAN = 29 / 105
EXPECTED_IC_STD = float(np.std(EXPECTED_IC_VALUES, ddof=1))
# Fama-MacBeth: y_t = (t + 1) + 0.5 f1 - 0.2 f2 on three dates.
FACTOR_1 = np.array([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]] * 3)
FACTOR_2 = np.array([[1.0, 4.0, 2.0, 6.0, 3.0, 5.0]] * 3)
FM_OUTCOME = np.array([(t + 1) + 0.5 * FACTOR_1[t] - 0.2 * FACTOR_2[t] for t in range(3)])
# Orthogonalisation: control c = 1..6, noise e has zero mean and zero covariance with c.
CONTROL = np.array([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]] * 3)
NOISE = np.array([[1.0, -1.0, 0.0, 0.0, -1.0, 1.0]] * 3)
ORTH_SIGNAL = 3.0 + 2.0 * CONTROL + NOISE


def geometric_close_panel(*, n_dates: int = 30, n_names: int = 6, step: float = 0.01) -> np.ndarray:
    """closes[t, i] = 100 * (1 + step * i) ** t: returns are monotone in i at every horizon."""
    t = np.arange(n_dates, dtype=float)[:, None]
    i = np.arange(n_names, dtype=float)[None, :]
    return 100.0 * (1.0 + step * i) ** t
