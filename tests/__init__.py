"""Makes ``tests`` importable, so test modules can share a fixture helper.

``tests/figure_runs.py`` builds synthetic run directories that several test files need.
Without this marker each of them would have to reimplement it, which is how the figure
tests ended up depending on the gitignored ``data/`` corpus in the first place -- and
skipping in silence on CI as a result.
"""
