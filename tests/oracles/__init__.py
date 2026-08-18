"""Oracle tier: metamorphic, known-truth and differential checks over the stat primitives.

A primitive lives here only if it is *wrong-detectable*: each test states a relation the
correct implementation must satisfy (scale invariance, monotonicity, a closed form, a
reference implementation, a simulated truth) so that a plausible-but-wrong edit fails.
Markers: ``oracle`` (fast, every gate) and ``slow_oracle`` (nightly + on-touch of quant modules).
"""
