import logging
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from typing import NoReturn, TypeVar
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..vo import FlexQueryID, FlexToken, ReferenceCode

T = TypeVar("T")

logger = logging.getLogger(__name__)


def _redact(url: str) -> str:
    """Mask the Flex token in a URL before logging it."""
    return re.sub(r"(t=)[^&]+", r"\1***", url)


class FlexError(Exception):
    """Base exception for Flex API errors."""

    pass


class FlexRateLimitError(FlexError):
    """Raised when IBKR rate limit is exceeded (Error 1008)."""

    pass


class FlexNotReadyError(FlexError):
    """Raised when the report is not yet ready (Error 1003)."""

    pass


class FlexAuthError(FlexError):
    """Raised when token or query ID is invalid (Error 1009/1012)."""

    pass


class FlexInProgressError(FlexError):
    """Raised when another statement is currently being generated (Error 1019)."""

    pass


class FlexLockoutError(FlexError):
    """Raised when IBKR temporarily blocks the account after too many failed attempts (Error 1025).

    This is a terminal error: it is NOT retried, since retrying deepens the lockout.
    Wait several minutes (typically ~10) and verify the token/query configuration
    before trying again.
    """

    pass


# Maps an IBKR error code to (exception class, message template). The template's
# {msg} is filled with IBKR's ErrorMessage. Unknown codes fall back to FlexError.
_ERROR_EXCEPTIONS: dict[str, tuple[type[FlexError], str]] = {
    "1003": (FlexNotReadyError, "Statement not ready: {msg}"),
    "1008": (FlexRateLimitError, "IBKR Rate Limit Exceeded: {msg}"),
    "1009": (FlexAuthError, "IBKR Authentication Error: {msg}"),
    "1012": (FlexAuthError, "IBKR Authentication Error: {msg}"),
    "1019": (FlexInProgressError, "Statement generation in progress: {msg}"),
    "1025": (
        FlexLockoutError,
        "IBKR temporarily blocked after too many failed attempts: {msg}. "
        "Wait several minutes and verify your token/query configuration before retrying.",
    ),
}


def _raise_for_error(root: ET.Element) -> NoReturn:
    """Raise the typed exception for the error described by a Flex response element."""
    error_code = root.findtext("ErrorCode")
    error_msg = root.findtext("ErrorMessage")
    entry = _ERROR_EXCEPTIONS.get(error_code or "")
    if entry is not None:
        exc_class, template = entry
        raise exc_class(template.format(msg=error_msg))
    raise FlexError(f"Flex API Error {error_code}: {error_msg}")


class FlexClient:
    """
    Official IBKR Flex Web Service API Client (Zero Dependencies).

    This client implements the two-step protocol for downloading Flex Queries:
    1. SendRequest: Tells IBKR to generate the report.
    2. GetStatement: Fetches the generated report.
    """

    BASE_URL = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"

    def __init__(self, user_agent: str = "python/py-ibkr v1.0.0"):
        self.user_agent = user_agent

    def _get(self, url: str) -> bytes:
        """Internal helper for standard GET requests using urllib."""
        logger.debug("GET %s", _redact(url))
        req = Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urlopen(req) as response:
                data = response.read()
                logger.debug("Received %d bytes", len(data))
                return data
        except HTTPError as e:
            raise FlexError(f"HTTP Error {e.code}: {e.reason}") from e
        except URLError as e:
            raise FlexError(f"URL Error: {e.reason}") from e

    def download(
        self,
        token: FlexToken.Input,
        query_id: FlexQueryID.Input,
        max_retries: int = 20,
        retry_interval: int = 60,
        max_retry_interval: int = 120,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> bytes:
        """
        Download a Flex Query report.

        Args:
            token: IBKR Flex Web Service Token.
            query_id: ID of the Flex Query template.
            max_retries: Maximum number of times to poll for the report if not ready.
            retry_interval: Base seconds to wait between retries (grows exponentially).
            max_retry_interval: Upper bound (seconds) on the exponential backoff wait.
            from_date: Optional start date in YYYYMMDD format.
            to_date: Optional end date in YYYYMMDD format.

        Returns:
            The raw XML content as bytes.
        """

        def poll(operation: Callable[[], T], retryable: tuple[type[FlexError], ...]) -> T:
            # Retry the first max_retries-1 attempts; the final attempt runs
            # unconditionally so its exception propagates.
            for i in range(max_retries - 1):
                try:
                    return operation()
                except retryable as e:
                    wait = min(retry_interval * (2**i), max_retry_interval)
                    logger.info(
                        "%s; retrying in %ds (attempt %d/%d)",
                        e,
                        wait,
                        i + 1,
                        max_retries,
                    )
                    time.sleep(wait)
            return operation()

        # Stage 1: Send Request (retry while another statement is generating, 1019)
        logger.info("Requesting Flex Query %s", query_id)
        reference_code = poll(
            lambda: self.send_request(token, query_id, from_date=from_date, to_date=to_date),
            (FlexInProgressError,),
        )
        # Stage 2: Get Statement (retry while not ready, 1003, or generating, 1019)
        logger.info("Fetching statement for reference code %s", reference_code)
        return poll(
            lambda: self.get_statement(token, reference_code),
            (FlexNotReadyError, FlexInProgressError),
        )

    def send_request(
        self,
        token: FlexToken.Input,
        query_id: FlexQueryID.Input,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> ReferenceCode:
        """
        Step 1: Send a request to generate a Flex Query.

        Returns the reference code for the generated report.
        """
        url = f"{self.BASE_URL}/SendRequest?t={token}&q={query_id}&v=3"
        if from_date:
            url += f"&fd={from_date}"
        if to_date:
            url += f"&td={to_date}"

        content = self._get(url)

        root = ET.fromstring(content)
        status = root.findtext("Status")

        if status == "Success":
            code = root.findtext("ReferenceCode")
            if not code:
                raise FlexError("ReferenceCode missing in success response")
            return ReferenceCode(code)

        _raise_for_error(root)

    def get_statement(self, token: FlexToken.Input, reference_code: ReferenceCode.Input) -> bytes:
        """
        Step 2: Retrieve the generated Flex Query statement.
        """
        url = f"{self.BASE_URL}/GetStatement?t={token}&q={reference_code}&v=3"

        content = self._get(url)

        # Check if the response is an error XML instead of the actual data
        stripped_content = content.strip()
        if stripped_content.startswith(b"<FlexStatementResponse"):
            root = ET.fromstring(stripped_content)
            status = root.findtext("Status")
            if status != "Success":
                _raise_for_error(root)

        return content
