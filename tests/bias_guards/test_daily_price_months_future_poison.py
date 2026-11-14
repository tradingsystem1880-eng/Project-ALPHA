"""Later archive prices cannot enter an earlier completed-day query."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from alpha_core import DataError
from tests.fixtures.daily_price_months import manifest_ids, month_start, publish_month
from tests.unit.test_crypto_price_snapshot_months import query
from tests.unit.test_crypto_price_snapshot_query import _store

pytestmark = pytest.mark.bias_guard


def test_later_month_poison_does_not_change_earlier_rows(tmp_path: Path) -> None:
    store = _store(tmp_path)
    january, february, march = [publish_month(store, 2020, month) for month in (1, 2, 3)]
    poisoned = publish_month(store, 2020, 3, price=999_999)
    ids, end = manifest_ids(january, february), month_start(2020, 3)
    original = query(store, [january, february, march], ids=ids, end=end)
    twin = query(store, [january, february, poisoned], ids=ids, end=end)
    assert original.rows == twin.rows
    assert (
        query(store, [january, february, march]).rows
        != query(store, [january, february, poisoned]).rows
    )


def test_february_capture_before_leap_day_completion_fails(tmp_path: Path) -> None:
    store = _store(tmp_path)
    january = publish_month(store, 2020, 1)
    qualified = publish_month(store, 2020, 2)
    february = publish_month(store, 2020, 2, fetched=month_start(2020, 3) - timedelta(hours=1))
    # Independently claim qualification so the query must enforce the receipt clock,
    # even when the normalized manifest claims these otherwise identical bars are sound.
    _, payload = store.read_verified_normalized(
        qualified.normalized_manifest["manifest_id"], max_bytes=32 * 1024 * 1024
    )
    manifest = store.publish_normalized(
        payload,
        dataset=february.receipt.dataset,
        input_manifest_ids=(str(february.raw_manifest["manifest_id"]),),
        quality=qualified.quality,
    )
    february = replace(february, normalized_manifest=manifest, quality=qualified.quality)
    with pytest.raises(DataError, match="raw capture predates completed candle"):
        query(store, [january, february])
