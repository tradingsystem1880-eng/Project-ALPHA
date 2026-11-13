"""Command-line boundaries for the isolated literature worker."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from literature_worker import __main__ as cli


def test_lookup_subcommand_is_rejected(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "sys.argv", ["literature-worker", "lookup", "--provider", "openalex", "--query", "test"]
    )
    fetch = Mock(side_effect=AssertionError("lookup must be rejected before acquisition"))
    monkeypatch.setattr(cli, "fetch_validated", fetch)

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2
    assert "invalid choice: 'lookup'" in capsys.readouterr().err
    fetch.assert_not_called()
