from pathlib import Path

import wheel_smoke


def test_modules_derive_from_workspace_manifests() -> None:
    root = Path(__file__).resolve().parents[2]
    modules = wheel_smoke.workspace_modules(root)
    assert len(modules) == 12
    assert "alpha_study" in modules
    assert "alpha_options" not in modules


def test_import_probe_checks_install_origin() -> None:
    assert "is_relative_to" in wheel_smoke.IMPORT_PROBE
    assert "__file__" in wheel_smoke.IMPORT_PROBE
