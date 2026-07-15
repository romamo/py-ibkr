from unittest.mock import MagicMock, patch

import pytest

from py_ibkr import (
    FlexAuthError,
    FlexClient,
    FlexInProgressError,
    FlexLockoutError,
    FlexNotReadyError,
    FlexRateLimitError,
)
from py_ibkr.flex.client import _redact


def test_redact_masks_token():
    url = "https://example.com/Flex?t=SECRET123&q=987&v=3"
    redacted = _redact(url)
    assert "SECRET123" not in redacted
    assert "t=***" in redacted
    # Other query params are left intact.
    assert "q=987" in redacted
    assert "v=3" in redacted


class TestFlexClient:
    @patch("py_ibkr.flex.client.urlopen")
    def test_send_request_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b"""
        <FlexStatementResponse>
            <Status>Success</Status>
            <ReferenceCode>123456789</ReferenceCode>
        </FlexStatementResponse>
        """
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        client = FlexClient()
        code = client.send_request("token", "query_id")
        assert str(code) == "123456789"

        # Verify URL construction with dates
        client.send_request("token", "query_id", from_date="20230101", to_date="20230131")
        args, kwargs = mock_urlopen.call_args
        url = args[0].get_full_url()
        assert "fd=20230101" in url
        assert "td=20230131" in url

    @patch("py_ibkr.flex.client.urlopen")
    def test_send_request_rate_limit(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b"""
        <FlexStatementResponse>
            <Status>Warn</Status>
            <ErrorCode>1008</ErrorCode>
            <ErrorMessage>Rate limit exceeded</ErrorMessage>
        </FlexStatementResponse>
        """
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        client = FlexClient()
        with pytest.raises(FlexRateLimitError, match="Rate limit exceeded"):
            client.send_request("token", "query_id")

    @patch("py_ibkr.flex.client.urlopen")
    def test_send_request_auth_error(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b"""
        <FlexStatementResponse>
            <Status>Warn</Status>
            <ErrorCode>1009</ErrorCode>
            <ErrorMessage>Invalid token</ErrorMessage>
        </FlexStatementResponse>
        """
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        client = FlexClient()
        with pytest.raises(FlexAuthError, match="Invalid token"):
            client.send_request("token", "query_id")

    @patch("py_ibkr.flex.client.urlopen")
    def test_send_request_lockout(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b"""
        <FlexStatementResponse>
            <Status>Warn</Status>
            <ErrorCode>1025</ErrorCode>
            <ErrorMessage>Too many failed attempts</ErrorMessage>
        </FlexStatementResponse>
        """
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        client = FlexClient()
        with pytest.raises(FlexLockoutError, match="Too many failed attempts"):
            client.send_request("token", "query_id")

    @patch("py_ibkr.flex.client.urlopen")
    @patch("time.sleep", return_value=None)
    def test_download_lockout_is_terminal(self, mock_sleep, mock_urlopen):
        # A 1025 during Stage 1 must not be retried: fail fast, no sleeps.
        mock_response = MagicMock()
        mock_response.read.return_value = (
            b"<FlexStatementResponse><Status>Warn</Status>"
            b"<ErrorCode>1025</ErrorCode>"
            b"<ErrorMessage>Too many failed attempts</ErrorMessage></FlexStatementResponse>"
        )
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        client = FlexClient()
        with pytest.raises(FlexLockoutError):
            client.download("token", "query_id")

        assert mock_urlopen.call_count == 1
        mock_sleep.assert_not_called()

    @patch("py_ibkr.flex.client.urlopen")
    def test_get_statement_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b"<FlexQueryResponse>data</FlexQueryResponse>"
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        client = FlexClient()
        data = client.get_statement("token", "12345")
        assert data == b"<FlexQueryResponse>data</FlexQueryResponse>"

    @patch("py_ibkr.flex.client.urlopen")
    def test_get_statement_not_ready(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b"""
        <FlexStatementResponse>
            <Status>Warn</Status>
            <ErrorCode>1003</ErrorCode>
            <ErrorMessage>Statement not ready</ErrorMessage>
        </FlexStatementResponse>
        """
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        client = FlexClient()
        with pytest.raises(FlexNotReadyError, match="Statement not ready"):
            client.get_statement("token", "12345")

    @patch("py_ibkr.flex.client.urlopen")
    @patch("time.sleep", return_value=None)
    def test_download_with_retry(self, mock_sleep, mock_urlopen):
        # Step 1: SendRequest success
        mock_resp1 = MagicMock()
        mock_resp1.read.return_value = (
            b"<FlexStatementResponse><Status>Success</Status>"
            b"<ReferenceCode>123</ReferenceCode></FlexStatementResponse>"
        )
        mock_resp1.__enter__.return_value = mock_resp1

        # Step 2: GetStatement not ready then success
        mock_resp_not_ready = MagicMock()
        mock_resp_not_ready.read.return_value = (
            b"<FlexStatementResponse><Status>Warn</Status>"
            b"<ErrorCode>1003</ErrorCode></FlexStatementResponse>"
        )
        mock_resp_not_ready.__enter__.return_value = mock_resp_not_ready

        mock_resp_success = MagicMock()
        mock_resp_success.read.return_value = b"<FlexQueryResponse>data</FlexQueryResponse>"
        mock_resp_success.__enter__.return_value = mock_resp_success

        mock_urlopen.side_effect = [mock_resp1, mock_resp_not_ready, mock_resp_success]

        client = FlexClient()
        data = client.download("token", "query_id", max_retries=2, retry_interval=0)

        assert data == b"<FlexQueryResponse>data</FlexQueryResponse>"
        assert mock_urlopen.call_count == 3
        assert mock_sleep.call_count == 1

    @patch("py_ibkr.flex.client.urlopen")
    @patch("time.sleep", return_value=None)
    def test_download_retry_on_in_progress(self, mock_sleep, mock_urlopen):
        # First call to send_request returns 1019
        # Second call to send_request returns success
        # Third call to get_statement returns data
        mock_urlopen.side_effect = [
            MagicMock(
                __enter__=MagicMock(
                    return_value=MagicMock(
                        read=MagicMock(
                            return_value=b"""
                <FlexStatusResponse>
                    <Status>Warn</Status>
                    <ErrorCode>1019</ErrorCode>
                    <ErrorMessage>Statement generation in progress</ErrorMessage>
                </FlexStatusResponse>
            """
                        )
                    )
                )
            ),
            MagicMock(
                __enter__=MagicMock(
                    return_value=MagicMock(
                        read=MagicMock(
                            return_value=b"""
                <FlexStatusResponse>
                    <Status>Success</Status>
                    <ReferenceCode>12345</ReferenceCode>
                </FlexStatusResponse>
            """
                        )
                    )
                )
            ),
            MagicMock(
                __enter__=MagicMock(
                    return_value=MagicMock(read=MagicMock(return_value=b"<xml>data</xml>"))
                )
            ),
        ]

        client = FlexClient()
        data = client.download("token", "query_id")

        assert data == b"<xml>data</xml>"
        assert mock_urlopen.call_count == 3
        mock_sleep.assert_called_once_with(60)

    @patch("py_ibkr.flex.client.urlopen")
    def test_get_statement_in_progress(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b"""
        <FlexStatementResponse>
            <Status>Warn</Status>
            <ErrorCode>1019</ErrorCode>
            <ErrorMessage>Statement generation in progress</ErrorMessage>
        </FlexStatementResponse>
        """
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        client = FlexClient()
        with pytest.raises(FlexInProgressError, match="Statement generation in progress"):
            client.get_statement("token", "12345")

    @patch("py_ibkr.flex.client.urlopen")
    @patch("time.sleep", return_value=None)
    def test_download_exponential_backoff(self, mock_sleep, mock_urlopen):
        # Step 1: SendRequest success
        mock_resp1 = MagicMock()
        mock_resp1.read.return_value = (
            b"<FlexStatementResponse><Status>Success</Status>"
            b"<ReferenceCode>123</ReferenceCode></FlexStatementResponse>"
        )
        mock_resp1.__enter__.return_value = mock_resp1

        # Step 2: GetStatement in progress (1019) -> not ready (1003) -> success
        mock_resp_1019 = MagicMock()
        mock_resp_1019.read.return_value = (
            b"<FlexStatementResponse><Status>Warn</Status>"
            b"<ErrorCode>1019</ErrorCode></FlexStatementResponse>"
        )
        mock_resp_1019.__enter__.return_value = mock_resp_1019

        mock_resp_1003 = MagicMock()
        mock_resp_1003.read.return_value = (
            b"<FlexStatementResponse><Status>Warn</Status>"
            b"<ErrorCode>1003</ErrorCode></FlexStatementResponse>"
        )
        mock_resp_1003.__enter__.return_value = mock_resp_1003

        mock_resp_success = MagicMock()
        mock_resp_success.read.return_value = b"<xml>data</xml>"
        mock_resp_success.__enter__.return_value = mock_resp_success

        mock_urlopen.side_effect = [
            mock_resp1,
            mock_resp_1019,
            mock_resp_1003,
            mock_resp_success,
        ]

        client = FlexClient()
        # Default retry_interval is 60, backoff capped at max_retry_interval (120)
        client.download("token", "query_id", max_retries=3)

        assert mock_urlopen.call_count == 4
        # Sleep calls should be 60*2^0 = 60, then min(60*2^1, 120) = 120
        mock_sleep.assert_any_call(60)
        mock_sleep.assert_any_call(120)
        assert mock_sleep.call_count == 2
