"""Stable byte/error contracts for the control-plane JSON codec."""

from __future__ import annotations

import json

import pytest

from alpha_cli import control_store as store
from alpha_core import DataError


def test_compact_sorted_bytes_and_sequence_normalization() -> None:
    value = {"z": "é", "a": (True, None, 1.25)}
    assert store._json_object(value, "payload") == {"z": "é", "a": [True, None, 1.25]}
    assert store._canonical_json(value, "payload") == '{"a":[true,null,1.25],"z":"\\u00e9"}'


def test_byte_limit_boundary() -> None:
    assert len(store._canonical_json("x" * 65534, "payload").encode()) == 65536
    with pytest.raises(DataError) as error:
        store._canonical_json("x" * 65535, "payload")
    assert str(error.value) == "invalid control payload: JSON exceeds 65536 bytes"


def test_nesting_boundary() -> None:
    value: object = None
    for _ in range(16):
        value = [value]
    assert store._clean_json(value, label="payload") == value
    with pytest.raises(DataError) as error:
        store._clean_json([value], label="payload")
    assert str(error.value) == "invalid control payload: JSON nesting exceeds 16 levels"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), object(), b"bytes"])
def test_invalid_values_fail_loud(value: object) -> None:
    with pytest.raises(DataError) as error:
        store._clean_json(value, label="payload")
    assert str(error.value) == "invalid control payload: expected finite JSON values"


@pytest.mark.parametrize("key", ["", "a\x00b", 1])
def test_invalid_mapping_keys_fail_loud(key: object) -> None:
    with pytest.raises(DataError) as error:
        store._clean_json({key: 1}, label="payload")
    assert str(error.value) == "invalid control payload: JSON keys must be non-empty strings"


def test_decode_rejects_nontext_and_retains_parse_cause() -> None:
    with pytest.raises(DataError) as error:
        store._decode_json(1, "stored payload")
    assert str(error.value) == "corrupt control store: stored payload is not text"
    with pytest.raises(DataError) as error:
        store._decode_json("{", "stored payload")
    assert str(error.value) == "corrupt control store: invalid stored payload"
    assert isinstance(error.value.__cause__, json.JSONDecodeError)
    assert store._decode_json('{"a":[true,null]}', "stored payload") == {"a": [True, None]}


def test_canonical_json_retains_encoding_cause() -> None:
    with pytest.raises(DataError) as error:
        store._canonical_json(object(), "payload")
    assert str(error.value) == "invalid control payload: expected finite JSON values"
    assert isinstance(error.value.__cause__, TypeError)


def test_facade_exports_the_same_codec_functions() -> None:
    from alpha_cli import _control_json

    assert store._canonical_json is _control_json._canonical_json
    assert store._clean_json is _control_json._clean_json
    assert store._json_object is _control_json._json_object
    assert store._decode_json is _control_json._decode_json
    assert store._MAX_JSON_BYTES == _control_json._MAX_JSON_BYTES == 65536
