import os
from pathlib import Path

import pytest

from py_ibkr import parse

SAMPLE_ENV = "PY_IBKR_SAMPLE_XML"


def test_parse_real_xml():
    sample = os.environ.get(SAMPLE_ENV)
    if sample is None:
        pytest.skip(f"Set {SAMPLE_ENV} to a Flex statement to run this test")

    response = parse(str(Path(sample)))

    assert len(response.FlexStatements) > 0

    stmt = response.FlexStatements[0]
    assert stmt.accountId
    assert len(stmt.Trades) > 0
    assert len(stmt.CashTransactions) > 0

    trade = stmt.Trades[0]
    assert trade.symbol
    assert trade.tradeDate

    cash = stmt.CashTransactions[0]
    assert cash.amount is not None
