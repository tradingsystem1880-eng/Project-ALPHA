"""Permutation entropy: how unpredictable the ordering of recent bars has been.

Each length-``d`` window is reduced to its ordinal pattern (which of the ``d!`` rank orderings the
values take); the Shannon entropy of the pattern distribution over a trailing window of
``d! * mult`` patterns, normalised by ``log2(d!)``, is 0 for a perfectly regular series and 1 for
one whose orderings are uniformly random. Everything is trailing.

Provenance: github.com/neurotrader888/PermutationEntropy/perm_entropy.py@890da37 (MIT); adapted:
numpy arrays, ``DataError`` validation, a NaN head instead of an unfilled array. The Lehmer-code
pattern encoding and the normalised entropy are unchanged (parity fixture
``tests/fixtures/neurotrader/entropy.json``). Bandt & Pompe (2002).
"""

from __future__ import annotations

import math

import numpy as np

from alpha_core import DataError
from alpha_patterns.series import FloatArray


def _check(values: FloatArray, d: int) -> FloatArray:
    x = np.asarray(values, dtype=np.float64)
    if x.ndim != 1 or x.size < d:
        raise DataError(f"need a 1-D array of >= {d} values, got shape {x.shape}")
    if not bool(np.all(np.isfinite(x))):
        raise DataError("permutation entropy input contains non-finite values")
    if d < 2:
        raise DataError(f"embedding dimension d must be >= 2, got {d}")
    return x


def ordinal_patterns(values: FloatArray, d: int) -> FloatArray:
    """Pattern code in ``[0, d!)`` of the window ending at each bar; NaN for the first ``d-1``."""
    x = _check(values, d)
    fac = math.factorial(d)
    d1 = d - 1
    mults = [fac / math.factorial(i + 1) for i in range(1, d)]
    out = np.full(x.size, np.nan)
    for i in range(d1, x.size):
        window = x[i - d1 : i + 1]
        code = 0.0
        for level in range(1, d):
            count = sum(1 for r in range(level) if window[d1 - level] >= window[d1 - r])
            code += count * mults[level - 1]
        out[i] = int(code)
    return out


def permutation_entropy(values: FloatArray, *, d: int, mult: int) -> FloatArray:
    """Normalised entropy of the last ``d! * mult`` ordinal patterns; NaN until that many exist."""
    x = _check(values, d)
    if mult < 1:
        raise DataError(f"mult must be >= 1, got {mult}")
    fac = math.factorial(d)
    lookback = fac * mult
    codes = ordinal_patterns(x, d)
    out = np.full(x.size, np.nan)
    norm = 1.0 / math.log2(fac)
    for i in range(lookback + d - 1, x.size):
        window = codes[i - lookback + 1 : i + 1].astype(np.intp)
        probs = np.bincount(window, minlength=fac) / lookback
        nz = probs[probs > 0.0]
        out[i] = -norm * float(np.sum(nz * np.log2(nz)))
    return out
