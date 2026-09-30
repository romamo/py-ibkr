import io
import json
import threading
from collections.abc import Iterator
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from treaty import ParseError

from py_ibkr.cli import app, resolve_range

TOKEN = "tok-SECRET-123"
STATEMENT = (
    b'<FlexQueryResponse queryName="q" type="AF"><FlexStatements count="0"/></FlexQueryResponse>'
)


def flex_error(code: str, message: str) -> bytes:
    return (
        f"<FlexStatementResponse><Status>Warn</Status><ErrorCode>{code}</ErrorCode>"
        f"<ErrorMessage>{message}</ErrorMessage></FlexStatementResponse>"
    ).encode()


class FakeIBKR(BaseHTTPRequestHandler):
    """Flex Web Service stand-in; the query ID selects the scenario."""

    requests: list[dict[str, list[str]]]
    release: threading.Event

    def do_GET(self) -> None:
        url = urlparse(self.path)
        params = parse_qs(url.query)
        self.requests.append({"path": [url.path], **params})
        query = params["q"][0]
        if url.path.endswith("/SendRequest"):
            body = self.send_request(query)
        else:
            body = self.get_statement(query)
        if body is None:
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_request(self, query: str) -> bytes | None:
        if query == "500":
            self.send_error(500)
            return None
        if query == "777":  # stall: never answer
            self.release.wait()
            return None
        if query in {"1008", "1009", "1025", "1019"}:
            return flex_error(query, f"error {query}")
        return (
            b"<FlexStatementResponse><Status>Success</Status>"
            b"<ReferenceCode>" + query.encode() + b"</ReferenceCode></FlexStatementResponse>"
        )

    def get_statement(self, reference: str) -> bytes:
        if reference == "1003":
            return flex_error("1003", "Statement generation in progress")
        return STATEMENT

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def ibkr() -> Iterator[tuple[str, list[dict[str, list[str]]]]]:
    requests: list[dict[str, list[str]]] = []
    release = threading.Event()
    handler = type("Handler", (FakeIBKR,), {"requests": requests, "release": release})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/FlexWebService", requests
    release.set()
    server.shutdown()
    server.server_close()


@pytest.fixture
def env(tmp_path: Path, ibkr: tuple[str, list[dict[str, list[str]]]]) -> dict[str, str]:
    """An isolated environment: fake IBKR, token set, state and config under tmp_path."""
    base_url, _ = ibkr
    return {
        "HOME": str(tmp_path),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_STATE_HOME": str(tmp_path / "state"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "PY_IBKR_TOKEN": TOKEN,
        "PY_IBKR_BASE_URL": base_url,
    }


def run(argv: list[str], env: dict[str, str], *, tty: bool = False) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = app.run(argv, stdout=out, stderr=err, env=env, isatty=tty)
    return code, out.getvalue(), err.getvalue()


def envelope(stdout: str) -> dict:
    """The response envelope: the last stdout line (heartbeats may precede it)."""
    return json.loads(stdout.strip().splitlines()[-1])


def test_download_writes_report(tmp_path, env, ibkr):
    _, requests = ibkr
    report = tmp_path / "report.xml"
    code, out, err = run(["download", "-o", str(report), "-q", "123"], env)

    assert code == 0, out
    assert report.read_bytes() == STATEMENT
    body = envelope(out)
    assert body["ok"] is True
    assert body["data"] == {
        "path": str(report),
        "bytes": len(STATEMENT),
        "query_id": "123",
        "from_date": None,
        "to_date": None,
    }
    assert requests[0]["t"] == [TOKEN]
    assert "fd" not in requests[0]
    assert TOKEN not in out + err


def test_download_overwrites_existing_file(tmp_path, env):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    report = inbox / "report.xml"
    report.write_bytes(b"old")
    code, _, _ = run(["download", "-o", str(report), "-q", "123"], env)
    assert code == 0
    assert report.read_bytes() == STATEMENT
    assert [p.name for p in inbox.iterdir()] == ["report.xml"]  # no temp file left
    assert report.stat().st_mode & 0o777 == 0o600


def test_verbose_logs_the_request(tmp_path, env):
    argv = ["download", "-o", str(tmp_path / "r.xml"), "-q", "123", "--verbose"]
    code, _, err = run([*argv, "--from-date", "2026-01-05", "--to-date", "2026-01-09"], env)
    assert code == 0
    logged = [json.loads(line) for line in err.splitlines() if "Requesting" in line]
    assert logged[0]["fields"] == {
        "query_id": "123",
        "from_date": "2026-01-05",
        "to_date": "2026-01-09",
    }


def test_download_sends_adjusted_range(tmp_path, env, ibkr):
    _, requests = ibkr
    # 2026-01-31 is a Saturday: the end rolls back to Friday 2026-01-30.
    argv = ["download", "-o", str(tmp_path / "r.xml"), "-q", "123"]
    code, out, _ = run([*argv, "--from-date", "20260101", "--to-date", "2026-01-31"], env)

    assert code == 0, out
    assert requests[0]["fd"] == ["20260101"]
    assert requests[0]["td"] == ["20260130"]
    body = envelope(out)
    assert body["data"]["from_date"] == "2026-01-01"
    assert body["data"]["to_date"] == "2026-01-30"
    assert [w["code"] for w in body["warnings"]] == ["WEEKEND_ADJUSTED"]
    assert body["warnings"][0]["context"] == {"original": "2026-01-31", "adjusted": "2026-01-30"}


def test_query_id_from_setting(tmp_path, env, ibkr):
    _, requests = ibkr
    code, out, _ = run(
        ["download", "-o", str(tmp_path / "r.xml")], {**env, "PY_IBKR_QUERY_ID": "456"}
    )
    assert code == 0, out
    assert requests[0]["q"] == ["456"]


def test_plain_output_at_terminal(tmp_path, env):
    report = tmp_path / "r.xml"
    code, out, _ = run(["download", "-o", str(report), "-q", "123"], env, tty=True)
    assert code == 0
    assert out == f"Saved {len(STATEMENT)} bytes to {report}\n"


@pytest.mark.parametrize(
    "query,exit_code,error_code",
    [
        ("1008", 11, "RATE_LIMITED"),
        ("1009", 79, "FLEX_AUTH_FAILED"),
        ("1025", 80, "FLEX_LOCKED_OUT"),
        ("1019", 81, "FLEX_NOT_READY"),
        ("1003", 81, "FLEX_NOT_READY"),
        ("500", 82, "FLEX_API_ERROR"),
    ],
)
def test_ibkr_errors_map_to_exit_codes(tmp_path, env, query, exit_code, error_code):
    report = tmp_path / "r.xml"
    argv = ["download", "-o", str(report), "-q", query, "--max-retries", "2"]
    code, out, _ = run([*argv, "--retry-interval", "0"], env)

    assert code == exit_code, out
    assert envelope(out)["error"]["code"] == error_code
    assert not report.exists()


def test_polling_reports_progress(tmp_path, env):
    argv = ["download", "-o", str(tmp_path / "r.xml"), "-q", "1003", "--verbose"]
    code, _, err = run([*argv, "--max-retries", "3", "--retry-interval", "0"], env)
    assert code == 81
    progress = [line for line in err.splitlines() if "retrying in" in line]
    assert len(progress) == 2


def test_request_timeout_maps_to_timeout(tmp_path, env):
    argv = ["download", "-o", str(tmp_path / "r.xml"), "-q", "777"]
    code, out, _ = run([*argv, "--request-timeout", "0.5"], env)
    assert code == 10
    assert envelope(out)["error"]["code"] == "TIMEOUT"


def test_token_on_command_line_is_refused(tmp_path, env):
    argv = ["download", "-o", str(tmp_path / "r.xml"), "-q", "1", "--token", TOKEN]
    code, out, _ = run(argv, env)
    assert code == 2
    assert TOKEN not in out


def test_token_from_file(tmp_path, env, ibkr):
    _, requests = ibkr
    token_file = tmp_path / "token"
    token_file.write_text("from-file\n")
    no_token = {k: v for k, v in env.items() if k != "PY_IBKR_TOKEN"}
    argv = ["download", "-o", str(tmp_path / "r.xml"), "-q", "1"]
    code, out, _ = run([*argv, "--token-from-file", str(token_file)], no_token)
    assert code == 0, out
    assert requests[0]["t"] == ["from-file"]


def test_missing_query_id_is_a_precondition(tmp_path, env, ibkr):
    _, requests = ibkr
    code, out, _ = run(["download", "-o", str(tmp_path / "r.xml")], env)
    assert code == 4
    assert "PY_IBKR_QUERY_ID" in envelope(out)["error"]["suggestion"]
    assert requests == []


def test_bad_query_id_setting_is_a_config_error(tmp_path, env, ibkr):
    _, requests = ibkr
    argv = ["download", "-o", str(tmp_path / "r.xml")]
    code, out, _ = run(argv, {**env, "PY_IBKR_QUERY_ID": "abc"})
    assert code == 2
    error = envelope(out)["error"]
    assert (error["code"], error["phase"]) == ("CONFIG_INVALID", "validation")
    assert error["context"] == {"key": "query_id", "source": "PY_IBKR_QUERY_ID"}
    assert requests == []


def test_missing_output_directory_is_a_precondition(tmp_path, env, ibkr):
    _, requests = ibkr
    code, _, _ = run(["download", "-o", str(tmp_path / "nope" / "r.xml"), "-q", "1"], env)
    assert code == 4
    assert requests == []


@pytest.mark.parametrize(
    "extra",
    [
        ["--max-retries", "0"],
        ["--retry-interval", "-1"],
        ["--request-timeout", "0"],
        ["--to-date", "2026-01-30"],  # without --from-date
        ["--from-date", "2026-01-31", "--to-date", "2026-02-01"],  # a weekend only
        ["--from-date", "2026-02-30"],
        ["-q", "abc"],
    ],
)
def test_invalid_arguments_exit_2_without_network(tmp_path, env, ibkr, extra):
    _, requests = ibkr
    code, out, _ = run(["download", "-o", str(tmp_path / "r.xml"), "-q", "1", *extra], env)
    assert code == 2, out
    assert envelope(out)["error"]["phase"] == "validation"
    assert requests == []


def test_format_id_prints_path(tmp_path, env):
    report = tmp_path / "r.xml"
    code, out, _ = run(["download", "-o", str(report), "-q", "123", "--format", "id"], env)
    assert code == 0
    assert out == f"{report}\n"


def test_manifest_lists_download(env):
    code, out, _ = run(["manifest"], env)
    assert code == 0
    assert "download" in json.dumps(envelope(out)["data"]["commands"])


# resolve_range: 2026-02-04 is a Wednesday, so "yesterday" is Tuesday 2026-02-03.
TODAY = date(2026, 2, 4)


def test_resolve_range_without_dates():
    assert resolve_range(None, None, TODAY) == (None, None, [])


def test_resolve_range_keeps_weekdays():
    start, end, notes = resolve_range(date(2026, 1, 5), date(2026, 1, 30), TODAY)
    assert (start, end, notes) == (date(2026, 1, 5), date(2026, 1, 30), [])


def test_resolve_range_rolls_weekends_inward():
    # Sat 2026-01-03 -> Mon 2026-01-05; Sun 2026-02-01 -> Fri 2026-01-30.
    start, end, notes = resolve_range(date(2026, 1, 3), date(2026, 2, 1), TODAY)
    assert (start, end) == (date(2026, 1, 5), date(2026, 1, 30))
    assert [n.code for n in notes] == ["WEEKEND_ADJUSTED", "WEEKEND_ADJUSTED"]


def test_resolve_range_defaults_end_to_yesterday():
    _, end, notes = resolve_range(date(2026, 1, 5), None, TODAY)
    assert end == date(2026, 2, 3)
    assert notes == []


def test_resolve_range_caps_end_at_yesterday():
    _, end, notes = resolve_range(date(2026, 1, 5), TODAY, TODAY)
    assert end == date(2026, 2, 3)
    assert [n.code for n in notes] == ["TO_DATE_CAPPED"]


def test_resolve_range_rejects_empty_range():
    with pytest.raises(ParseError, match="No weekday"):
        resolve_range(TODAY, None, TODAY)


def test_resolve_range_needs_from_date():
    with pytest.raises(ParseError, match="needs --from-date"):
        resolve_range(None, date(2026, 1, 5), TODAY)
