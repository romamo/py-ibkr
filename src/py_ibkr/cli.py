import argparse
import logging
import os
import sys
from datetime import date, datetime, timedelta
from typing import Literal

from .flex.client import FlexClient, FlexError


def setup_logging(verbosity: int) -> None:
    """Configure the root logger from a -v/-vv count.

    0 (default) -> WARNING, 1 (-v) -> INFO, 2+ (-vv) -> DEBUG. The client is
    stdlib-only (``urllib``), so there are no noisy third-party loggers to silence.
    """
    if verbosity >= 2:
        level = logging.DEBUG
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    elif verbosity == 1:
        level = logging.INFO
        fmt = "[%(levelname)s] %(message)s"
    else:
        level = logging.WARNING
        fmt = "%(message)s"

    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
        force=True,
    )


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


def positive_float(value: str) -> float:
    """argparse type for a strictly positive number of seconds."""
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError(f"must be positive, got {value}")
    return number


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="py-ibkr",
        description="CLI tool to download and manage IBKR Flex Queries",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Increase verbosity (-v for INFO, -vv for DEBUG)",
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
        "--max-retries", type=int, default=20, help="Maximum retries if report is not ready"
    )
    download_parser.add_argument(
        "--retry-interval",
        type=int,
        default=60,
        help="Base seconds between retries, grows exponentially (default: 60)",
    )
    download_parser.add_argument(
        "--max-retry-interval",
        type=int,
        default=120,
        help="Upper bound in seconds on the backoff wait (default: 120)",
    )
    download_parser.add_argument(
        "--timeout",
        type=positive_float,
        default=60.0,
        help="Seconds to wait for IBKR to connect or send data per request (default: 60)",
    )
    download_parser.add_argument("--from-date", help="Optional start date in YYYYMMDD format")
    download_parser.add_argument("--to-date", help="Optional end date in YYYYMMDD format")

    args = parser.parse_args()
    setup_logging(args.verbose)

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


def to_business_day(date_str: str, roll: Literal["back", "forward"]) -> str:
    """Snap a YYYYMMDD date onto a weekday, since IBKR Flex rejects weekend dates.

    ``roll="back"`` moves Sat/Sun to the prior Friday (use for a range end);
    ``roll="forward"`` moves Sat/Sun to the next Monday (use for a range start).
    """
    day = datetime.strptime(date_str, "%Y%m%d").date()
    weekday = day.weekday()  # Mon=0 .. Sun=6
    if weekday < 5:
        return date_str

    if roll == "back":
        adjusted = day - timedelta(days=weekday - 4)  # Sat->-1, Sun->-2 => Friday
    elif roll == "forward":
        adjusted = day + timedelta(days=7 - weekday)  # Sat->+2, Sun->+1 => Monday
    else:
        raise ValueError(f"Invalid roll direction: {roll!r} (expected 'back' or 'forward')")

    result = adjusted.strftime("%Y%m%d")
    print(
        f"Note: {date_str} is a {day.strftime('%A')}; "
        f"IBKR Flex accepts weekdays only, adjusted to {result} "
        f"({adjusted.strftime('%A')}).",
        file=sys.stderr,
    )
    return result


def handle_download(args: argparse.Namespace) -> None:
    client = FlexClient(timeout=args.timeout)
    try:
        from_date = format_date(args.from_date)
        to_date = format_date(args.to_date)

        yesterday = (date.today() - timedelta(days=1)).strftime("%Y%m%d")

        # IBKR requires both if either is provided
        if from_date and not to_date:
            to_date = yesterday

        # IBKR has no finalized data for today or the future: cap the end at the
        # previous day. (YYYYMMDD strings compare correctly as fixed-width.)
        if to_date and to_date > yesterday:
            print(
                f"Note: to-date {to_date} is today or later; "
                f"IBKR data ends at the previous day, capping at {yesterday}.",
                file=sys.stderr,
            )
            to_date = yesterday

        # IBKR Flex rejects weekend dates: snap onto the enclosing weekdays.
        if from_date:
            from_date = to_business_day(from_date, roll="forward")
        if to_date:
            to_date = to_business_day(to_date, roll="back")

        msg = f"Requesting Flex Query {args.query_id}"
        if from_date or to_date:
            msg += f" ({from_date or ''} to {to_date or ''})"
        print(f"{msg}...", file=sys.stderr)

        data = client.download(
            token=args.token,
            query_id=args.query_id,
            max_retries=args.max_retries,
            retry_interval=args.retry_interval,
            max_retry_interval=args.max_retry_interval,
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
