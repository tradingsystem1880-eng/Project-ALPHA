import zipfile
from pathlib import Path

import pytest
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


def test_web_wheel_without_the_built_spa_fails_with_the_build_command(tmp_path: Path) -> None:
    bare = tmp_path / "alpha_web-1.0.0-py3-none-any.whl"
    with zipfile.ZipFile(bare, "w") as archive:
        archive.writestr("alpha_web/__init__.py", "")
    with pytest.raises(RuntimeError, match="npm run build"):
        wheel_smoke.require_spa(bare)
    built = tmp_path / "built" / bare.name
    built.parent.mkdir()
    with zipfile.ZipFile(built, "w") as archive:
        archive.writestr(wheel_smoke.SPA_ENTRY, "<div id='root'></div>")
    wheel_smoke.require_spa(built)
