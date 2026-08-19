"""Security and closed-command tests for the provider Keychain launcher."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o700)


def test_coingecko_catalog_launcher_injects_only_the_fixed_process(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    capture = tmp_path / "capture"
    _executable(
        fake_bin / "security",
        "#!/bin/sh\nset -eu\nprintf '%s\\n' 'sentinel-secret'\n",
    )
    _executable(
        fake_bin / "uv",
        "#!/bin/sh\nset -eu\n"
        'printf \'%s\\n\' "$ALPHA_COINGECKO_API_KEY" "$@" '
        '> "$ALPHA_LAUNCHER_CAPTURE"\n',
    )
    repository = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [str(repository / "scripts" / "alpha-with-keychain-provider"), "coingecko", "catalog"],
        cwd=repository,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "ALPHA_LAUNCHER_CAPTURE": str(capture),
        },
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "sentinel-secret" not in result.stdout
    assert "sentinel-secret" not in result.stderr
    assert capture.read_text(encoding="utf-8").splitlines() == [
        "sentinel-secret",
        "run",
        "alpha",
        "crypto-data",
        "acquire",
        "coingecko",
        "asset_metadata",
        "all",
        "--base",
        "BTC",
        "--quote",
        "USD",
        "--json",
    ]


def test_unsupported_catalog_action_fails_before_keychain_lookup(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    marker = tmp_path / "security-called"
    _executable(
        fake_bin / "security",
        f"#!/bin/sh\nset -eu\ntouch '{marker}'\nexit 1\n",
    )
    repository = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [str(repository / "scripts" / "alpha-with-keychain-provider"), "tiingo", "catalog"],
        cwd=repository,
        env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"},
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 64
    assert "unsupported provider action" in result.stderr
    assert not marker.exists()


def test_quantpad_archive_launcher_passes_only_explicit_archive_arguments(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    capture = tmp_path / "capture"
    _executable(fake_bin / "security", "#!/bin/sh\nset -eu\nprintf '%s\\n' 'sentinel-secret'\n")
    _executable(
        fake_bin / "uv",
        "#!/bin/sh\nset -eu\n"
        'printf \'%s\\n\' "$QUANTPAD_API_KEY" "$@" > "$ALPHA_LAUNCHER_CAPTURE"\n',
    )
    repository = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            str(repository / "scripts" / "alpha-with-keychain-provider"),
            "quantpad",
            "archive",
            "coverage",
            "AAPL",
            "--json",
        ],
        cwd=repository,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "ALPHA_LAUNCHER_CAPTURE": str(capture),
        },
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "sentinel-secret" not in result.stdout + result.stderr
    assert capture.read_text().splitlines() == [
        "sentinel-secret",
        "run",
        "alpha",
        "quantpad-data",
        "archive",
        "coverage",
        "AAPL",
        "--json",
    ]


def test_coingecko_reference_launcher_uses_fixed_full_market_command(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    capture = tmp_path / "capture"
    _executable(
        fake_bin / "security",
        "#!/bin/sh\nset -eu\nprintf '%s\\n' 'sentinel-secret'\n",
    )
    _executable(
        fake_bin / "uv",
        "#!/bin/sh\nset -eu\n"
        'printf \'%s\\n\' "$ALPHA_COINGECKO_API_KEY" "$@" '
        '> "$ALPHA_LAUNCHER_CAPTURE"\n',
    )
    repository = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [str(repository / "scripts" / "alpha-with-keychain-provider"), "coingecko", "reference"],
        cwd=repository,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "ALPHA_LAUNCHER_CAPTURE": str(capture),
        },
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "sentinel-secret" not in result.stdout
    assert "sentinel-secret" not in result.stderr
    assert capture.read_text(encoding="utf-8").splitlines() == [
        "sentinel-secret",
        "run",
        "alpha",
        "crypto-data",
        "acquire",
        "coingecko",
        "market_reference",
        "all",
        "--base",
        "ALL",
        "--quote",
        "USD",
        "--json",
    ]


def _launch(
    tmp_path: Path, *argv: str, secret: str = "sentinel-secret"
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """Run the launcher against a stubbed `security` and `uv`, capturing the injected argv."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    capture = tmp_path / "capture"
    _executable(fake_bin / "security", f"#!/bin/sh\nset -eu\nprintf '%s\\n' '{secret}'\n")
    _executable(
        fake_bin / "uv",
        "#!/bin/sh\nset -eu\n"
        'printf \'%s\\n\' "$ALPHA_FINNHUB_API_KEY" "$@" > "$ALPHA_LAUNCHER_CAPTURE"\n',
    )
    repository = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [str(repository / "scripts" / "alpha-with-keychain-provider"), *argv],
        cwd=repository,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "ALPHA_LAUNCHER_CAPTURE": str(capture),
        },
        check=False,
        capture_output=True,
        text=True,
    )
    captured = capture.read_text(encoding="utf-8").splitlines() if capture.exists() else []
    return result, captured


def test_finnhub_quote_launcher_injects_only_the_fixed_process(tmp_path: Path) -> None:
    result, captured = _launch(tmp_path, "finnhub", "quote")

    assert result.returncode == 0, result.stderr
    assert "sentinel-secret" not in result.stdout + result.stderr
    assert captured == [
        "sentinel-secret",
        "run",
        "alpha",
        "screener",
        "quote",
        "SPY",
        "--json",
    ]


def test_quote_is_refused_for_other_providers_before_the_keychain_lookup(tmp_path: Path) -> None:
    """The symbol is fixed and the provider is fixed, so `quote` cannot become a data tool."""
    result, captured = _launch(tmp_path, "tiingo", "quote")

    assert result.returncode == 64
    assert "unsupported provider action" in result.stderr
    assert captured == []


def test_quote_refuses_extra_arguments(tmp_path: Path) -> None:
    result, captured = _launch(tmp_path, "finnhub", "quote", "AAPL")

    assert result.returncode == 64
    assert "unexpected provider launcher arguments" in result.stderr
    assert captured == []


def test_finnhub_check_points_at_the_bounded_probe_instead(tmp_path: Path) -> None:
    result, captured = _launch(tmp_path, "finnhub", "check")

    assert result.returncode == 64
    assert "finnhub quote" in result.stderr
    assert captured == []


def test_missing_keychain_item_reports_a_named_failure(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _executable(
        fake_bin / "security",
        "#!/bin/sh\nset -eu\nexit 44\n",
    )
    repository = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [str(repository / "scripts" / "alpha-with-keychain-provider"), "coingecko", "check"],
        cwd=repository,
        env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"},
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 78
    assert "unable to read the coingecko Keychain item" in result.stderr
