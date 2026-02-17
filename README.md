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

## Command Line Interface

`py-ibkr` includes a zero-dependency CLI for downloading Flex Queries.

```bash
# Download to a file
py-ibkr download --token YOUR_TOKEN --query-id YOUR_QUERY_ID --output report.xml

# Download with date range overrides (ISO format YYYY-MM-DD supported)
py-ibkr download -t YOUR_TOKEN -q YOUR_QUERY_ID --from-date 2023-01-01 --to-date 2023-01-31

# Alternatively, use a .env file (automatically loaded if present):
# IBKR_FLEX_TOKEN=your_token
# IBKR_FLEX_QUERY_ID=your_query_id
py-ibkr download -o report.xml

# Download to stdout (pipe to other tools)
py-ibkr download | xmllint --format -
```

## Setup: Obtaining your Token and Query ID

To use the automated downloader, you must enable the Flex Web Service in your Interactive Brokers account:

1.  Log in to the **IBKR Client Portal**.
2.  Navigate to **Performance & Reports** > **Flex Queries**.
3.  **Obtain Token**: Click the gear icon or **Flex Web Service Configuration**. Enable the service and copy the **Current Token**.
4.  **Obtain Query ID**: Create a new Flex Query (e.g., *Activity*). After saving it, the **Query ID** will be visible in the list of your Flex Queries.

> [!NOTE]
> Flex Queries are typically generated once per day after market close. Trade Confirmations are available with a 5-10 minute delay.

## Usage

### Downloading a Flex Query Report

You can automatically download reports using the `FlexClient`. This requires a Token and Query ID from the IBKR Client Portal.

```python
from py_ibkr import FlexClient, parse

# 1. Initialize the client
client = FlexClient()

# 2. Download the report (handles the request-poll-fetch protocol)
xml_data = client.download(
    token="YOUR_IBKR_TOKEN",
    query_id="YOUR_QUERY_ID"
)

# 3. Parse the downloaded data
response = parse(xml_data)

print(f"Query Name: {response.queryName}")
```

### Parsing a Flex Query File

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
