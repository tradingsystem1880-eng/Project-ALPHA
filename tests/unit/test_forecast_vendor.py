"""Vendored Kronos model code imports cleanly (catches the star-import rewrite)."""

from __future__ import annotations


def test_vendor_module_imports() -> None:
    from alpha_forecast._vendor.kronos import kronos as vendored

    assert hasattr(vendored, "KronosTokenizer")
    assert hasattr(vendored, "Kronos")
    assert hasattr(vendored, "KronosPredictor")


def test_vendor_package_reexports_classes() -> None:
    from alpha_forecast._vendor import kronos as pkg

    assert pkg.KronosPredictor is not None
    assert pkg.Kronos is not None
    assert pkg.KronosTokenizer is not None
