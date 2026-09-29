"""The ``py-ibkr`` command line, built on treaty.

Every run writes one JSON envelope to stdout (``plain`` text at a terminal), exits with a
typed code an agent can branch on, and reads the Flex token from the environment or a
file, never from argv. ``py-ibkr manifest`` describes the whole interface.
"""

import os
import tempfile
from dataclasses import dataclass
from datetime import date, timedelta
from importlib.metadata import version
from pathlib import Path
from typing import Any

from treaty import App, Ctx, Exit, Flag, Format, ParseError

from .flex.client import (
    FlexAuthError,
    FlexClient,
    FlexError,
    FlexInProgressError,
    FlexLockoutError,
    FlexNotReadyError,
    FlexRateLimitError,
    FlexTimeoutError,
)
from .vo import FlexQueryID, FlexToken


@dataclass(frozen=True, slots=True)
class Settings:
    """Read from ``PY_IBKR_<FIELD>``, then ``./.py-ibkr.toml``, then the user config."""

    # Plain str: settings are inspected before app.scalar() can register FlexQueryID.
    query_id: str | None = None
    base_url: str = FlexClient.BASE_URL


app = App(
    "py-ibkr",
    version=version("py-ibkr"),
    description="Download Interactive Brokers Flex Query reports",
    settings=Settings,
)


def parse_date(raw: str) -> date:
    """Accept ``YYYY-MM-DD`` or IBKR's ``YYYYMMDD``."""
    return date.fromisoformat(raw)


app.scalar(date, parse=parse_date, pattern=r"\d{4}-?\d{2}-?\d{2}", serialize=date.isoformat)
app.scalar(FlexQueryID, parse=FlexQueryID, pattern=r"\d+")
app.scalar(FlexToken, parse=FlexToken)

app.exit_code(
    "FLEX_AUTH_FAILED",
    79,
    description="IBKR rejected the token or query ID (errors 1009, 1012)",
    retryable=False,
    side_effects="none",
    suggestion="Check PY_IBKR_TOKEN (tokens expire) and the query ID in the IBKR portal",
)
app.exit_code(
    "FLEX_LOCKED_OUT",
    80,
    description="IBKR temporarily blocked the account after failed attempts (error 1025)",
    retryable=True,
    side_effects="none",
    suggestion="Wait about 10 minutes and verify the token and query ID before retrying",
    retry_after_ms=600_000,
)
app.exit_code(
    "FLEX_NOT_READY",
    81,
    description="The statement was still generating when polling gave up (errors 1003, 1019)",
    retryable=True,
    side_effects="none",
    suggestion="Retry later, or raise --max-retries",
    retry_after_ms=60_000,
    retry_strategy="exponential_backoff",
)
app.exit_code(
    "FLEX_API_ERROR",
    82,
    description="IBKR returned an unexpected error or an unusable HTTP response",
    retryable=False,
    side_effects="none",
)


@dataclass(frozen=True, slots=True)
class Adjustment:
    """A change made to the requested range so IBKR accepts it."""

    code: str
    message: str
    original: date
    adjusted: date


def resolve_range(
    from_date: date | None, to_date: date | None, today: date
) -> tuple[date | None, date | None, list[Adjustment]]:
    """Fit a requested range to what IBKR Flex accepts.

    IBKR needs both ends or neither, has no finalized data for today or later, and
    rejects weekend dates. A missing end becomes yesterday, a later one is capped at
    yesterday, and weekend ends move inward onto weekdays. Raises ``ParseError`` when
    no weekday with finalized data is left.
    """
    if from_date is None and to_date is None:
        return None, None, []
    if from_date is None:
        raise ParseError(
            "--to-date needs --from-date",
            context={"field": "from_date"},
            suggestion="add --from-date, the first day of the range",
        )

    yesterday = today - timedelta(days=1)
    adjustments: list[Adjustment] = []
    end = yesterday if to_date is None else to_date
    if end > yesterday:
        adjustments.append(
            Adjustment(
                "TO_DATE_CAPPED",
                f"IBKR data ends at the previous day; to-date capped at {yesterday}",
                end,
                yesterday,
            )
        )
        end = yesterday

    start = from_date
    if start.weekday() >= 5:  # Sat/Sun -> next Monday
        monday = start + timedelta(days=7 - start.weekday())
        adjustments.append(
            Adjustment(
                "WEEKEND_ADJUSTED",
                f"{start} is a {start:%A}; IBKR accepts weekdays only, moved to {monday}",
                start,
                monday,
            )
        )
        start = monday
    if end.weekday() >= 5:  # Sat/Sun -> previous Friday
        friday = end - timedelta(days=end.weekday() - 4)
        adjustments.append(
            Adjustment(
                "WEEKEND_ADJUSTED",
                f"{end} is a {end:%A}; IBKR accepts weekdays only, moved to {friday}",
                end,
                friday,
            )
        )
        end = friday

    if start > end:
        raise ParseError(
            f"No weekday with finalized IBKR data between {from_date} and "
            f"{to_date or yesterday} (IBKR data ends at {yesterday})",
            context={"field": "from_date", "from_date": start, "to_date": end},
            suggestion="choose a range that includes a weekday before today",
        )
    return start, end, adjustments


@dataclass(frozen=True, slots=True)
class DownloadArgs:
    output: Path = Flag(short="o", description="File to write the XML report to")
    token: FlexToken = Flag(description="IBKR Flex Web Service token")
    query_id: FlexQueryID | None = Flag(
        default=None,
        short="q",
        description="Flex Query ID; defaults to the query_id setting (PY_IBKR_QUERY_ID)",
    )
    from_date: date | None = Flag(
        default=None, description="First day of the range, YYYY-MM-DD or YYYYMMDD"
    )
    to_date: date | None = Flag(
        default=None, description="Last day of the range; defaults to yesterday"
    )
    max_retries: int = Flag(default=20, description="Polls before giving up on a pending report")
    retry_interval: int = Flag(
        default=60, description="Base seconds between polls, doubling each time"
    )
    max_retry_interval: int = Flag(default=120, description="Upper bound in seconds on a poll wait")
    request_timeout: float = Flag(
        default=60.0, description="Seconds to wait for IBKR to connect or send data per request"
    )

    def __post_init__(self) -> None:
        errors = []
        for name in ("max_retries", "max_retry_interval"):
            if getattr(self, name) < 1:
                errors.append(ParseError(f"{name} must be at least 1", context={"field": name}))
        if self.retry_interval < 0:
            errors.append(
                ParseError(
                    "retry_interval must not be negative", context={"field": "retry_interval"}
                )
            )
        if self.request_timeout <= 0:
            errors.append(
                ParseError("request_timeout must be positive", context={"field": "request_timeout"})
            )
        try:
            resolve_range(self.from_date, self.to_date, date.today())
        except ParseError as e:
            errors.append(e)
        if errors:
            raise ParseError.combine(errors)


@dataclass(frozen=True, slots=True)
class Downloaded:
    path: Path
    bytes: int
    query_id: FlexQueryID
    from_date: date | None
    to_date: date | None


def render_downloaded(data: dict[str, Any]) -> str:
    period = ""
    if data["from_date"] is not None:
        period = f" for {data['from_date']} to {data['to_date']}"
    return f"Saved {data['bytes']} bytes to {data['path']}{period}\n"


def setting_query_id(settings: Settings) -> FlexQueryID:
    """The query_id setting, which the handler checks since settings skip scalars."""
    if settings.query_id is None:
        raise Exit.PRECONDITION(
            "No Flex Query ID",
            suggestion="pass --query-id or set PY_IBKR_QUERY_ID",
        )
    if not settings.query_id.isdigit():
        raise Exit.PRECONDITION(
            f"The query_id setting must be digits, got {settings.query_id!r}",
            suggestion="fix PY_IBKR_QUERY_ID or query_id in .py-ibkr.toml",
        )
    return FlexQueryID(settings.query_id)


def write_atomic(path: Path, data: bytes) -> None:
    """Write via a temp file in the same directory, so a failure leaves no partial file.

    The file is created owner-only (0600), as ``mkstemp`` does: it holds account data.
    """
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):  # only when the write or the rename failed
            os.unlink(tmp)


@app.command(
    "download",
    description="Download a Flex Query report as XML",
    # Only reads from IBKR; the one local write is the file the caller names with -o.
    danger_level="safe",
    exit_codes=[
        "RATE_LIMITED",
        "FLEX_AUTH_FAILED",
        "FLEX_LOCKED_OUT",
        "FLEX_NOT_READY",
        "FLEX_API_ERROR",
    ],
    has_network_io=True,
    # IBKR can take many minutes to generate a statement; polling is bounded by
    # --max-retries and each request by --request-timeout. Callers may pass --timeout.
    timeout=None,
    heartbeat=True,
    examples=[
        ("Download the query's default period", "py-ibkr download -o report.xml"),
        (
            "Download January 2026",
            "py-ibkr download -o jan.xml --from-date 2026-01-01 --to-date 2026-01-31",
        ),
        (
            "Read the token from a file",
            "py-ibkr download -o report.xml --token-from-file ~/.ibkr-token -q 123456",
        ),
    ],
    renderers={Format.PLAIN: render_downloaded},
    id_field="path",
)
def download(args: DownloadArgs, ctx: Ctx, settings: Settings) -> Downloaded:
    query_id = args.query_id if args.query_id is not None else setting_query_id(settings)
    if not args.output.parent.is_dir():
        raise Exit.PRECONDITION(
            f"Output directory {args.output.parent} does not exist",
            context={"path": str(args.output)},
        )

    from_date, to_date, adjustments = resolve_range(args.from_date, args.to_date, date.today())
    for a in adjustments:
        ctx.warn(
            a.code, a.message, original=a.original.isoformat(), adjusted=a.adjusted.isoformat()
        )

    def on_retry(error: FlexError, wait: int, attempt: int, max_retries: int) -> None:
        ctx.progress(f"{error}; retrying in {wait}s", done=attempt, total=max_retries)

    ctx.log(
        "Requesting Flex Query",
        query_id=str(query_id),
        from_date=None if from_date is None else from_date.isoformat(),
        to_date=None if to_date is None else to_date.isoformat(),
    )
    client = FlexClient(timeout=args.request_timeout, base_url=settings.base_url)
    try:
        data = client.download(
            token=args.token,
            query_id=query_id,
            max_retries=args.max_retries,
            retry_interval=args.retry_interval,
            max_retry_interval=args.max_retry_interval,
            from_date=None if from_date is None else f"{from_date:%Y%m%d}",
            to_date=None if to_date is None else f"{to_date:%Y%m%d}",
            on_retry=on_retry,
        )
    except FlexRateLimitError as e:
        raise Exit.RATE_LIMITED(
            str(e),
            retry_after_ms=60_000,  # IBKR allows about 10 Flex requests a minute per token
            suggestion="Wait a minute, then retry",
        ) from e
    except FlexAuthError as e:
        raise Exit.FLEX_AUTH_FAILED(str(e)) from e
    except FlexLockoutError as e:
        raise Exit.FLEX_LOCKED_OUT(str(e)) from e
    except (FlexNotReadyError, FlexInProgressError) as e:
        raise Exit.FLEX_NOT_READY(str(e), context={"max_retries": args.max_retries}) from e
    except FlexTimeoutError as e:
        raise Exit.TIMEOUT(str(e), context={"request_timeout": args.request_timeout}) from e
    except FlexError as e:
        raise Exit.FLEX_API_ERROR(str(e)) from e

    write_atomic(args.output, data)
    return Downloaded(args.output, len(data), query_id, from_date, to_date)


def main() -> None:
    app.main()


if __name__ == "__main__":
    main()
