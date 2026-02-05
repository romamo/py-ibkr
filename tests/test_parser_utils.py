from datetime import date, datetime, time
from decimal import Decimal

from py_ibkr.flex.models import Trade
from py_ibkr.flex.parser import clean_attributes, parse_date, parse_datetime, parse_time


def test_parse_date():
    assert parse_date("20230101") == date(2023, 1, 1)
    assert parse_date("2023-01-01") == date(2023, 1, 1)
    assert parse_date("") is None
    assert parse_date("N/A") is None


def test_parse_time():
    assert parse_time("123000") == time(12, 30, 0)
    assert parse_time("12:30:00") == time(12, 30, 0)
    assert parse_time("") is None


def test_parse_datetime():
    # date;time format
    assert parse_datetime("20230101;123000") == datetime(2023, 1, 1, 12, 30, 0)
    # comma format
    assert parse_datetime("20230101,123000") == datetime(2023, 1, 1, 12, 30, 0)
    # just date
    assert parse_datetime("20230101") == datetime(2023, 1, 1, 0, 0, 0)


def test_clean_attributes_legacy_enums():
    # Test Deposits/Withdrawals mapping
    attrs = {"type": "Deposits/Withdrawals", "amount": "100"}
    # Mock class with type field
    from py_ibkr.flex.models import CashTransaction

    cleaned = clean_attributes(attrs, CashTransaction)
    assert cleaned["type"] == "Deposits & Withdrawals"


def test_clean_attributes_decimal():
    attrs = {"tradePrice": "1,234.56"}
    cleaned = clean_attributes(attrs, Trade)
    assert cleaned["tradePrice"] == Decimal("1234.56")
