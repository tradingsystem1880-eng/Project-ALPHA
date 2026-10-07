"""Current downloads cannot retroactively qualify as historically known data."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from alpha_cli import crypto_data_cmds
from alpha_data.crypto.quality import qualify_crypto_frame


@pytest.mark.bias_guard
def test_defillama_historical_availability_rejects_future_download_and_leaky_twin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetched = datetime(2026, 10, 2, tzinfo=UTC)
    cutoff = datetime(2025, 10, 2, tzinfo=UTC)
    payload = json.dumps({"tvl": [{"date": 1756684800, "totalLiquidityUSD": 100.0}]}).encode()
    monkeypatch.setattr(crypto_data_cmds, "fetch_defillama_public", lambda _: payload)
    acquisition = crypto_data_cmds._fetch_defillama("protocol_tvl", "aave", fetched_at=fetched)
    plan = acquisition.plan
    frame = plan.parser(payload)

    def check(knowledge: datetime, availability: str | None) -> bool:
        report = qualify_crypto_frame(
            plan.dataset,
            frame,
            artifact_sha256="a" * 64,
            observed_column=plan.observed_column,
            key_columns=plan.key_columns,
            knowledge_time=knowledge,
            as_of=cutoff,
            availability_column=availability,
        )
        return report.state == "qualified"

    assert not check(fetched, plan.availability_column)
    assert not check(cutoff, plan.availability_column)
    # Must-fail leaky twin: discarding capture time falsely admits reconstructed history.
    assert check(cutoff, None)
