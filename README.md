# py-ibkr

A modern, Pydantic-based parser for Interactive Brokers (IBKR) Flex Query reports.
This version replaces the legacy `ibflex` library with strict type checking and improved support for newer IBKR XML fields.

## Features
- **Pydantic Models**: All data is parsed into typed Pydantic models with validation.
- **Robust Parsing**: Handles "messy" IBKR data (e.g., legacy enums like `Deposits/Withdrawals`, inconsistent date formats).
- **Forward Compatible**: Designed to handle new fields gracefully.

## Installation

```bash
uv pip install py-ibkr
# or
pip install py-ibkr
```

## Usage

### Parsing a Flex Query File

```python
from py_ibkr import parse, FlexQueryResponse

response = parse("path/to/report.xml")

print(f"Query Name: {response.queryName}")

for statement in response.FlexStatements:
    print(f"Account: {statement.accountId}")
    
    # Access Trades
    for trade in statement.Trades:
        print(f"Symbol: {trade.symbol}, Quantity: {trade.quantity}, Price: {trade.tradePrice}")
        
    # Access Cash Transactions
    for cash_tx in statement.CashTransactions:
        print(f"Type: {cash_tx.type}, Amount: {cash_tx.amount}")
```

### Models

You can import models directly for type hinting:

```python
from py_ibkr import Trade, CashTransaction

def process_trade(trade: Trade):
    print(trade.symbol)
```
