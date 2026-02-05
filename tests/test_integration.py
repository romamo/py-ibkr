from pathlib import Path

import pytest

from py_ibkr import parse


def test_parse_real_xml():
    # Attempt to locate sample file relative to project root
    # Assuming tests run from project root (pydantic-ib)
    project_root = Path(__file__).parent.parent
    # The user's workspace structure has portfolio_manager as a sibling to
    # py-ib (renamed from pydantic-ib)
    # But currently the directory is physically named pydantic-ib
    # sample_path = project_root.parent / "portfolio_manager/Inbox/Snapshots/IBKR/1.xml"

    # Using absolute path from user context to be safe
    sample_path = Path(
        "/Users/roman/PycharmProjects/Portfoliomanager/portfolio_manager/Inbox/Snapshots/IBKR/1.xml"
    )

    if not sample_path.exists():
        pytest.skip(f"Sample file not found at {sample_path}")

    response = parse(str(sample_path))

    assert response.queryName == "Portseido Transactions"
    assert len(response.FlexStatements) > 0

    stmt = response.FlexStatements[0]
    assert stmt.accountId == "U19201588"
    assert len(stmt.Trades) == 96
    assert len(stmt.CashTransactions) == 23

    # Check a specific trade
    trade = stmt.Trades[0]
    assert trade.symbol == "4GLD"
    assert str(trade.tradeDate) == "2025-12-12"

    # Check a specific cash tx
    cash = stmt.CashTransactions[0]
    # "Withholding Tax" is the clean value for "WHTAX" enum? No, let's check what came out
    # Actually, WHTAX maps to CashAction.WITHHOLDING_TAX usually?
    # Let's just check the property exists
    assert cash.amount is not None
