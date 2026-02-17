import sys
from unittest.mock import MagicMock, patch

import pytest

from py_ibkr.cli import main


def test_cli_help(capsys):
    with patch.object(sys, "argv", ["py-ibkr", "--help"]):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 0
    
    captured = capsys.readouterr()
    assert "CLI tool to download and manage IBKR Flex Queries" in captured.out


@patch("py_ibkr.cli.FlexClient")
def test_cli_download_to_stdout(mock_client_class, capsys):
    mock_client = MagicMock()
    mock_client.download.return_value = b"<xml>data</xml>"
    mock_client_class.return_value = mock_client

    with patch.object(sys, "argv", ["py-ibkr", "download", "--token", "tok", "--query-id", "qid"]):
        main()
    
    # Check that data was written to stdout buffer
    # Since we use sys.stdout.buffer.write, it's hard to capture with capsys
    # But we can verify the client was called correctly
    mock_client.download.assert_called_once_with(
        token="tok", query_id="qid", max_retries=10, retry_interval=10, from_date=None, to_date=None
    )


@patch("py_ibkr.cli.FlexClient")
def test_cli_download_with_dates(mock_client_class, capsys):
    mock_client = MagicMock()
    mock_client.download.return_value = b"<xml>data</xml>"
    mock_client_class.return_value = mock_client

    with patch.object(sys, "argv", ["py-ibkr", "download", "-t", "tok", "-q", "qid", "--from-date", "20230101", "--to-date", "20230131"]):
        main()
    
    mock_client.download.assert_called_once_with(
        token="tok", query_id="qid", max_retries=10, retry_interval=10, from_date="20230101", to_date="20230131"
    )


@patch("py_ibkr.cli.FlexClient")
@patch("py_ibkr.cli.date")
def test_cli_download_from_date_only(mock_date, mock_client_class):
    # Return a real date object so subtraction works
    from datetime import date as real_date
    mock_date.today.return_value = real_date(2024, 1, 1)

    mock_client = MagicMock()
    mock_client.download.return_value = b"<xml>data</xml>"
    mock_client_class.return_value = mock_client

    
    with patch.object(sys, "argv", ["py-ibkr", "download", "-t", "tok", "-q", "qid", "--from-date", "2023-12-01"]):
        main()
    
    # Observe that to_date defaults to yesterday (20231231)
    mock_client.download.assert_called_once_with(
        token="tok", query_id="qid", max_retries=10, retry_interval=10, from_date="20231201", to_date="20231231"
    )


@patch("py_ibkr.cli.FlexClient")
def test_cli_download_with_iso_dates(mock_client_class, capsys):
    mock_client = MagicMock()
    mock_client.download.return_value = b"<xml>data</xml>"
    mock_client_class.return_value = mock_client

    with patch.object(sys, "argv", ["py-ibkr", "download", "-t", "tok", "-q", "qid", "--from-date", "2023-01-01", "--to-date", "2023-01-31"]):
        main()
    
    # Observe the converted dates
    mock_client.download.assert_called_once_with(
        token="tok", query_id="qid", max_retries=10, retry_interval=10, from_date="20230101", to_date="20230131"
    )


@patch("py_ibkr.cli.FlexClient")
@patch("builtins.open", new_callable=MagicMock)
def test_cli_download_to_file(mock_open, mock_client_class):
    mock_client = MagicMock()
    mock_client.download.return_value = b"<xml>data</xml>"
    mock_client_class.return_value = mock_client

    mock_file = MagicMock()
    mock_open.return_value.__enter__.return_value = mock_file

    with patch.object(sys, "argv", ["py-ibkr", "download", "-t", "tok", "-q", "qid", "-o", "out.xml"]):
        main()
    
    mock_client.download.assert_called_once()
    # open('.env') then open('out.xml', 'wb')
    assert mock_open.call_args_list[-1] == (("out.xml", "wb"),)
    mock_file.write.assert_called_once_with(b"<xml>data</xml>")


@patch("py_ibkr.cli.FlexClient")
def test_cli_download_env_vars(mock_client_class, capsys):
    mock_client = MagicMock()
    mock_client.download.return_value = b"<xml>env-data</xml>"
    mock_client_class.return_value = mock_client

    env = {
        "IBKR_FLEX_TOKEN": "env-tok",
        "IBKR_FLEX_QUERY_ID": "env-qid"
    }

    with patch.dict("os.environ", env):
        with patch.object(sys, "argv", ["py-ibkr", "download"]):
            main()
    
    mock_client.download.assert_called_once_with(
        token="env-tok", query_id="env-qid", max_retries=10, retry_interval=10, from_date=None, to_date=None
    )


def test_load_dotenv(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("IBKR_FLEX_TOKEN=file-tok\nIBKR_FLEX_QUERY_ID='file-qid'\n# Comment\nINVALID LINE")
    
    import os
    from py_ibkr.cli import load_dotenv
    
    # Ensure env vars are not set
    if "IBKR_FLEX_TOKEN" in os.environ:
        del os.environ["IBKR_FLEX_TOKEN"]
    if "IBKR_FLEX_QUERY_ID" in os.environ:
        del os.environ["IBKR_FLEX_QUERY_ID"]
        
    load_dotenv(str(env_file))
    
    assert os.environ["IBKR_FLEX_TOKEN"] == "file-tok"
    assert os.environ["IBKR_FLEX_QUERY_ID"] == "file-qid"
