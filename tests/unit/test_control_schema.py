"""Byte-equivalence pins for the schema-only extraction; migration behavior tests remain."""

import hashlib

from alpha_cli import _control_schema, control_store


def test_extracted_sql_preserves_historical_bytes_and_facade() -> None:
    expected = {
        "_SCHEMA": "60cd4c5ce263708356b7e9acb98428f228bdc87be464f616438cf68b0feb4fdd",
        "_SCHEMA_V2": "68957347599cd5a5244108a37976804b8dcd64a23129b3d47d5cc6375258673c",
        "_SCHEMA_V3": "9e1d4db12207706ada559fc85f31e9ef6b7961eeb6089aa0d215ecad5d40df98",
        "_SCHEMA_V4": "61f7c6696fa5cd027e068619a67491863ceafbdad47b4953cf1650fccb05a8b7",
        "_SCHEMA_V5_RECEIPT": "fa07597badfc94ea0aecfe1a50db74f00c29e186261ae0908f5ca79105e8a640",
        "_SCHEMA_V5": "d29b8973a7bee9f5afe88c47369e050eb511c43e46754c8bd62d35fc8233ab2f",
        "_GOVERNANCE_BACKFILL": "704371965b7fc68a9d0fb08bbe78b2156f5bd4345666d6b2cdda247914cf6657",
    }
    for name, digest in expected.items():
        sql = getattr(_control_schema, name)
        assert getattr(control_store, name) == sql
        assert hashlib.sha256(sql.encode()).hexdigest() == digest
