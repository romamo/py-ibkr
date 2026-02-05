from datetime import date
from decimal import Decimal

from py_ibkr.flex.enums import BuySell, CashAction
from py_ibkr.flex.models import CashTransaction, Trade


def test_trade_model_instantiation():
    trade = Trade(
        transactionType="ExchTrade",
        buySell="BUY",
        quantity=Decimal("10"),
        symbol="AAPL",
        tradeDate=date(2023, 1, 1),
    )
    assert trade.buySell == BuySell.BUY
    assert trade.quantity == Decimal("10")
    assert trade.symbol == "AAPL"


def test_cash_transaction_model_instantiation():
    cash = CashTransaction(type="Dividends", amount=Decimal("50.00"), currency="USD")
    assert cash.type == CashAction.DIVIDEND
    assert cash.amount == Decimal("50.00")
