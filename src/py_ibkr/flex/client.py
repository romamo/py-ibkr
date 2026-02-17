import time
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

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


class FlexClient:
    """
    Official IBKR Flex Web Service API Client (Zero Dependencies).
    
    This client implements the two-step protocol for downloading Flex Queries:
    1. SendRequest: Tells IBKR to generate the report.
    2. GetStatement: Fetches the generated report.
    """

    BASE_URL = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
    
    def __init__(self, user_agent: str = "python/py-ibkr"):
        self.user_agent = user_agent

    def _get(self, url: str) -> bytes:
        """Internal helper for standard GET requests using urllib."""
        req = Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urlopen(req) as response:
                return response.read()
        except HTTPError as e:
            raise FlexError(f"HTTP Error {e.code}: {e.reason}") from e
        except URLError as e:
            raise FlexError(f"URL Error: {e.reason}") from e

    def download(
        self, 
        token: str, 
        query_id: str, 
        max_retries: int = 10, 
        retry_interval: int = 10,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> bytes:
        """
        Download a Flex Query report.
        
        Args:
            token: IBKR Flex Web Service Token.
            query_id: ID of the Flex Query template.
            max_retries: Maximum number of times to poll for the report if not ready.
            retry_interval: Seconds to wait between retries.
            from_date: Optional start date in YYYYMMDD format.
            to_date: Optional end date in YYYYMMDD format.
            
        Returns:
            The raw XML content as bytes.
        """
        for i in range(max_retries):
            try:
                reference_code = self.send_request(token, query_id, from_date=from_date, to_date=to_date)
                break
            except FlexInProgressError:
                if i == max_retries - 1:
                    raise
                time.sleep(retry_interval)
        
        for i in range(max_retries):
            try:
                return self.get_statement(token, reference_code)
            except FlexNotReadyError:
                if i == max_retries - 1:
                    raise
                time.sleep(retry_interval)
        
        raise FlexNotReadyError("Maximum retries exceeded while waiting for report to be ready.")

    def send_request(
        self, 
        token: str, 
        query_id: str, 
        from_date: str | None = None, 
        to_date: str | None = None
    ) -> str:
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
            return code
        
        error_code = root.findtext("ErrorCode")
        error_msg = root.findtext("ErrorMessage")
        
        if error_code == "1008":
            raise FlexRateLimitError(f"IBKR Rate Limit Exceeded: {error_msg}")
        if error_code in ("1009", "1012"):
            raise FlexAuthError(f"IBKR Authentication Error: {error_msg}")
        if error_code == "1019":
            raise FlexInProgressError(f"Statement generation in progress: {error_msg}")
        
        raise FlexError(f"Flex API Error {error_code}: {error_msg}")

    def get_statement(self, token: str, reference_code: str) -> bytes:
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
                error_code = root.findtext("ErrorCode")
                error_msg = root.findtext("ErrorMessage")
                
                if error_code == "1003":
                    raise FlexNotReadyError(f"Statement not ready: {error_msg}")
                if error_code == "1008":
                    raise FlexRateLimitError(f"IBKR Rate Limit Exceeded: {error_msg}")
                
                raise FlexError(f"Flex API Error {error_code}: {error_msg}")
        
        return content
