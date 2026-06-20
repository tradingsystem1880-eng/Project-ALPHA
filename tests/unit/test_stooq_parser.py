"""Pure Stooq CSV parser (offline) — the live fetch is network-gated."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from alpha_core import DataError
from alpha_data.adapters.stooq_adapter import parse_stooq_csv

_CSV = (
    "Date,Open,High,Low,Close,Volume\n"
    "2020-01-02,100.0,101.0,99.5,100.5,1000000\n"
    "2020-01-03,100.5,102.0,100.0,101.5,1200000\n"
)


def test_parses_valid_csv() -> None:
    result = parse_stooq_csv(_CSV, "spy.us")
    assert result.symbol == "spy.us"
    assert result.actions == []  # provider-adjusted: no separate corporate actions
    assert result.bars.height == 2
    assert result.bars["ts"][0] == datetime(2020, 1, 2, tzinfo=UTC)
    assert result.bars["close"][1] == 101.5


def test_missing_volume_column_defaults_to_zero() -> None:
    csv = "Date,Open,High,Low,Close\n2020-01-02,100.0,101.0,99.5,100.5\n"
    result = parse_stooq_csv(csv, "^spx")
    assert result.bars["volume"][0] == 0.0


def test_missing_volume_field_defaults_to_zero() -> None:
    csv = "Date,Open,High,Low,Close,Volume\n2020-01-02,100.0,101.0,99.5,100.5,N/D\n"
    result = parse_stooq_csv(csv, "x")
    assert result.bars["volume"][0] == 0.0


def test_header_is_case_insensitive_and_bom_tolerant() -> None:
    csv = "﻿DATE,OPEN,HIGH,LOW,CLOSE,VOLUME\n2020-01-02,100,101,99,100,5\n"
    result = parse_stooq_csv(csv, "x")
    assert result.bars.height == 1


def test_missing_required_column_fails_loud() -> None:
    with pytest.raises(DataError):
        parse_stooq_csv("Date,Open,High,Close,Volume\n2020-01-02,1,2,1,5\n", "x")  # no Low


def test_bad_number_fails_loud() -> None:
    with pytest.raises(DataError):
        parse_stooq_csv("Date,Open,High,Low,Close,Volume\n2020-01-02,abc,2,1,1,5\n", "x")


def test_ohlc_inconsistency_fails_loud() -> None:
    # high below open violates a Bar invariant
    with pytest.raises(DataError):
        parse_stooq_csv("Date,Open,High,Low,Close,Volume\n2020-01-02,100,90,80,85,5\n", "x")


def test_empty_csv_fails_loud() -> None:
    with pytest.raises(DataError):
        parse_stooq_csv("", "x")
    with pytest.raises(DataError):
        parse_stooq_csv("Date,Open,High,Low,Close,Volume\n", "x")  # header only
