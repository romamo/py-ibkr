import logging
import sys
from unittest.mock import MagicMock, patch

import pytest

from py_ibkr.cli import main, setup_logging, to_business_day


@pytest.mark.parametrize(
    "verbosity,expected",
    [(0, logging.WARNING), (1, logging.INFO), (2, logging.DEBUG), (3, logging.DEBUG)],
)
def test_setup_logging_levels(verbosity, expected):
    setup_logging(verbosity)
    assert logging.getLogger().level == expected


def test_to_business_day_keeps_weekdays():
    # 2026-01-30 is a Friday; both roll directions leave it untouched.
    assert to_business_day("20260130", roll="back") == "20260130"
    assert to_business_day("20260130", roll="forward") == "20260130"


def test_to_business_day_rolls_back_to_friday():
    assert to_business_day("20260131", roll="back") == "20260130"  # Sat -> Fri
    assert to_business_day("20260201", roll="back") == "20260130"  # Sun -> Fri


def test_to_business_day_rolls_forward_to_monday():
    assert to_business_day("20260131", roll="forward") == "20260202"  # Sat -> Mon
    assert to_business_day("20260201", roll="forward") == "20260202"  # Sun -> Mon


def test_to_business_day_rejects_bad_direction():
    with pytest.raises(ValueError, match="Invalid roll direction"):
        to_business_day("20260131", roll="sideways")


@patch("py_ibkr.cli.FlexClient")
def test_cli_download_adjusts_weekend_range(mock_client_class, capsys):
    # Asking for all of January 2026: end 2026-01-31 is a Saturday.
    mock_client = MagicMock()
    mock_client.download.return_value = b"<xml>data</xml>"
    mock_client_class.return_value = mock_client

    with patch.object(
        sys,
        "argv",
        [
            "py-ibkr",
            "download",
            "-t",
            "tok",
            "-q",
            "qid",
            "--from-date",
            "2026-01-01",
            "--to-date",
            "2026-01-31",
        ],
    ):
        main()

    # 2026-01-01 is a Thursday (kept); 2026-01-31 (Sat) rolls back to 2026-01-30 (Fri).
    _, kwargs = mock_client.download.call_args
    assert kwargs["from_date"] == "20260101"
    assert kwargs["to_date"] == "20260130"
    assert "adjusted to 20260130" in capsys.readouterr().err


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
        token="tok",
        query_id="qid",
        max_retries=20,
        retry_interval=60,
        max_retry_interval=120,
        from_date=None,
        to_date=None,
    )


@patch("py_ibkr.cli.FlexClient")
def test_cli_download_with_dates(mock_client_class, capsys):
    mock_client = MagicMock()
    mock_client.download.return_value = b"<xml>data</xml>"
    mock_client_class.return_value = mock_client

    with patch.object(
        sys,
        "argv",
        [
            "py-ibkr",
            "download",
            "-t",
            "tok",
            "-q",
            "qid",
            "--from-date",
            "20230102",
            "--to-date",
            "20230131",
        ],
    ):
        main()

    mock_client.download.assert_called_once_with(
        token="tok",
        query_id="qid",
        max_retries=20,
        retry_interval=60,
        max_retry_interval=120,
        from_date="20230102",
        to_date="20230131",
    )


@patch("py_ibkr.cli.FlexClient")
@patch("py_ibkr.cli.date")
def test_cli_download_from_date_only(mock_date, mock_client_class):
    # Return a real date object so subtraction works
    from datetime import date as real_date

    # today=Thu so yesterday (Wed) is already a weekday and needs no adjustment
    mock_date.today.return_value = real_date(2024, 1, 4)

    mock_client = MagicMock()
    mock_client.download.return_value = b"<xml>data</xml>"
    mock_client_class.return_value = mock_client

    with patch.object(
        sys, "argv", ["py-ibkr", "download", "-t", "tok", "-q", "qid", "--from-date", "2023-12-01"]
    ):
        main()

    # Observe that to_date defaults to yesterday (20240103); from_date 2023-12-01 is a Friday
    mock_client.download.assert_called_once_with(
        token="tok",
        query_id="qid",
        max_retries=20,
        retry_interval=60,
        max_retry_interval=120,
        from_date="20231201",
        to_date="20240103",
    )


@patch("py_ibkr.cli.FlexClient")
def test_cli_download_with_iso_dates(mock_client_class, capsys):
    mock_client = MagicMock()
    mock_client.download.return_value = b"<xml>data</xml>"
    mock_client_class.return_value = mock_client

    with patch.object(
        sys,
        "argv",
        [
            "py-ibkr",
            "download",
            "-t",
            "tok",
            "-q",
            "qid",
            "--from-date",
            "2023-01-02",
            "--to-date",
            "2023-01-31",
        ],
    ):
        main()

    # Observe the converted dates
    mock_client.download.assert_called_once_with(
        token="tok",
        query_id="qid",
        max_retries=20,
        retry_interval=60,
        max_retry_interval=120,
        from_date="20230102",
        to_date="20230131",
    )


@patch("py_ibkr.cli.FlexClient")
@patch("builtins.open", new_callable=MagicMock)
def test_cli_download_to_file(mock_open, mock_client_class):
    mock_client = MagicMock()
    mock_client.download.return_value = b"<xml>data</xml>"
    mock_client_class.return_value = mock_client

    mock_file = MagicMock()
    mock_open.return_value.__enter__.return_value = mock_file

    with patch.object(
        sys, "argv", ["py-ibkr", "download", "-t", "tok", "-q", "qid", "-o", "out.xml"]
    ):
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

    env = {"IBKR_FLEX_TOKEN": "env-tok", "IBKR_FLEX_QUERY_ID": "env-qid"}

    with patch.dict("os.environ", env):
        with patch.object(sys, "argv", ["py-ibkr", "download"]):
            main()

    mock_client.download.assert_called_once_with(
        token="env-tok",
        query_id="env-qid",
        max_retries=20,
        retry_interval=60,
        max_retry_interval=120,
        from_date=None,
        to_date=None,
    )


def test_load_dotenv(tmp_path):
    env_file = tmp_path / ".env"
    env_text = "IBKR_FLEX_TOKEN=file-tok\nIBKR_FLEX_QUERY_ID='file-qid'\n# Comment\nINVALID LINE"
    env_file.write_text(env_text)

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
