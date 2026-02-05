"""
Example script to parse an IBKR Flex Query XML file.
"""

from pathlib import Path

from py_ibkr import parse


def main():
    # Attempt to locate sample file
    # In a real scenario, provide your own path
    sample_path = Path("path/to/report.xml")

    if not sample_path.exists():
        print(f"Sample file not found at {sample_path}")
        return

    print(f"Parsing {sample_path}...")
    try:
        response = parse(str(sample_path))
        print("Successfully parsed.")
        print("-" * 30)

        for stmt in response.FlexStatements:
            print(f"Account: {stmt.accountId}")
            print(f"Trades Count: {len(stmt.Trades)}")
            print(f"Cash Tx Count: {len(stmt.CashTransactions)}")

            if stmt.Trades:
                last_trade = stmt.Trades[-1]
                print(
                    f"Last Trade: {last_trade.buySell.value} {last_trade.quantity} "
                    f"{last_trade.symbol} @ {last_trade.tradePrice}"
                )

    except Exception as e:
        print(f"Error parsing file: {e}")


if __name__ == "__main__":
    main()
