import argparse
import os
import sys
from datetime import date, timedelta
from typing import NoReturn

from .flex.client import FlexClient, FlexError


def load_dotenv(path: str = ".env") -> None:
    """Minimal, zero-dependency .env loader."""
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = value
    except FileNotFoundError:
        pass


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="py-ibkr",
        description="CLI tool to download and manage IBKR Flex Queries",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Download command
    download_parser = subparsers.add_parser("download", help="Download a Flex Query report")
    download_parser.add_argument(
        "--token",
        "-t",
        default=os.environ.get("IBKR_FLEX_TOKEN"),
        help="IBKR Flex Web Service Token (fallback: IBKR_FLEX_TOKEN env var)",
    )
    download_parser.add_argument(
        "--query-id",
        "-q",
        default=os.environ.get("IBKR_FLEX_QUERY_ID"),
        help="IBKR Flex Query ID (fallback: IBKR_FLEX_QUERY_ID env var)",
    )
    download_parser.add_argument(
        "--output", "-o", help="Output file path (prints to stdout if omitted)"
    )
    download_parser.add_argument(
        "--max-retries", type=int, default=10, help="Maximum retries if report is not ready"
    )
    download_parser.add_argument(
        "--retry-interval", type=int, default=10, help="Seconds between retries (default: 10)"
    )
    download_parser.add_argument(
        "--from-date", help="Optional start date in YYYYMMDD format"
    )
    download_parser.add_argument(
        "--to-date", help="Optional end date in YYYYMMDD format"
    )

    args = parser.parse_args()

    if args.command == "download":
        if not args.token:
            print("Error: --token or IBKR_FLEX_TOKEN env var is required", file=sys.stderr)
            sys.exit(1)
        if not args.query_id:
            print("Error: --query-id or IBKR_FLEX_QUERY_ID env var is required", file=sys.stderr)
            sys.exit(1)
        handle_download(args)
    else:
        parser.print_help()
        sys.exit(1)


def format_date(date_str: str | None) -> str | None:
    """Convert YYYY-MM-DD to YYYYMMDD if needed."""
    if date_str and "-" in date_str:
        return date_str.replace("-", "")
    return date_str


def handle_download(args: argparse.Namespace) -> None:
    client = FlexClient()
    try:
        from_date = format_date(args.from_date)
        to_date = format_date(args.to_date)
        
        # IBKR requires both if either is provided
        if from_date and not to_date:
            to_date = (date.today() - timedelta(days=1)).strftime("%Y%m%d")
        
        msg = f"Requesting Flex Query {args.query_id}"
        if from_date or to_date:
            msg += f" ({from_date or ''} to {to_date or ''})"
        print(f"{msg}...", file=sys.stderr)
        
        data = client.download(
            token=args.token,
            query_id=args.query_id,
            max_retries=args.max_retries,
            retry_interval=args.retry_interval,
            from_date=from_date,
            to_date=to_date,
        )

        if args.output:
            with open(args.output, "wb") as f:
                f.write(data)
            print(f"Report saved to {args.output}", file=sys.stderr)
        else:
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()

    except FlexError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
