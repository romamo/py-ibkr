# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`py-ibkr` is a Pydantic-based parser and downloader for Interactive Brokers (IBKR) Flex Query XML reports. It replaces the legacy `ibflex` library with strict Pydantic v2 models and fail-fast parsing. Published to PyPI; requires Python 3.14+ (treaty's floor).

## Commands

```bash
uv sync --all-extras --dev      # install deps (incl. dev: ruff, mypy, pytest)
uv run pytest                   # run all tests
uv run pytest tests/test_parser_utils.py::test_parse_date   # run a single test
uv run ruff check .             # lint (rules: E, F, I, UP, B; line-length 100)
uv run mypy src                 # type-check
uv build                        # build wheel + sdist
uv run --isolated --no-project --with dist/*.whl tests/smoke_test.py   # smoke-test built artifact
```

CI (`.github/workflows/ci.yml`) runs `uv run pytest` on push/PR. Publishing (`publish.yml`) triggers on `v*` tags: builds, smoke-tests both wheel and sdist, then `uv publish` to PyPI via trusted publishing.

## Architecture

Package root is `src/py_ibkr/` with the `flex/` subpackage holding all IBKR-specific logic. The public API is re-exported from `__init__.py` (top-level) which pulls from `flex/__init__.py`.

**Two independent capabilities:**

1. **Parsing** (`flex/parser.py`, `flex/models.py`, `flex/utils.py`, `flex/enums.py`) — turns Flex Query XML into typed models. `parse()` (aliased from `parse_xml_file`) is the entry point.
2. **Downloading** (`flex/client.py`) — `FlexClient.download()` implements IBKR's two-step request-poll-fetch protocol using only stdlib `urllib` (zero runtime deps for the client).

**Parsing flow:** `parse_xml_file` → `parse_flex_query_response` → `parse_flex_statement`. XML is walked with `xml.etree.ElementTree`; each element's attributes pass through `clean_attributes(attrs, model_class)` before constructing the Pydantic model. `clean_attributes` is the central coercion layer — it inspects the target field's annotation string to decide how to convert the raw XML string (date/time/datetime/bool/Decimal), applies legacy enum fixups (e.g. `Deposits/Withdrawals` → `Deposits & Withdrawals`, `ACAT` → `ACATS`, multi-value `orderType` → `MULTIPLE`), and splits code sequences. Unknown XML attributes are silently skipped (models use `extra="ignore"`), which is how the parser stays forward-compatible with new IBKR fields.

**Download protocol** (`FlexClient`): `send_request` (Stage 1) returns a `ReferenceCode`; `get_statement` (Stage 2) fetches the report. `download()` orchestrates both with exponential backoff. IBKR error codes map to typed exceptions: `FlexRateLimitError` (1008), `FlexAuthError` (1009/1012), `FlexNotReadyError` (1003), `FlexInProgressError` (1019), all subclassing `FlexError`.

**CLI** (`cli.py`, entry point `py-ibkr`): a [treaty](https://github.com/romamo/treaty) app with one `download` command over `FlexClient`. stdout is a JSON envelope (plain at a terminal); the XML goes to `-o`. The token is a treaty secret (`PY_IBKR_TOKEN`, `--token-from-file`, `--token-from-env`, never argv); `query_id` and `base_url` are treaty `Settings` (`PY_IBKR_<FIELD>` or `.py-ibkr.toml`). There is no `.env` loading. `resolve_range` fits dates to IBKR (weekdays only, data ends yesterday) and runs in `DownloadArgs.__post_init__`, so bad ranges exit 2 before any request. `FlexError` subclasses map to exit codes: `RATE_LIMITED` 11, `TIMEOUT` 10, and app codes 79-82 declared with `app.exit_code`. `uv run treaty audit py_ibkr.cli:app` checks the declarations. Tests drive `app.run(argv, env=...)` against a local fake IBKR server via `PY_IBKR_BASE_URL`.

## Conventions specific to this codebase

- **Value Objects** (`vo.py`): domain identifiers (`AccountID`, `Symbol`, `ConID`, `CurrencyCode`, `FlexToken`, `FlexQueryID`, `ReferenceCode`) are Pydantic `RootModel` string VOs, not primitives. Follow the **Namespace `.Input` pattern**: model fields and function signatures accept `VO.Input` (a `TYPE_CHECKING` union like `AccountID | str`) for DX, while internal logic stays strictly typed. When adding a new domain identifier, add both the VO class and its `<Name>Input` alias in `vo.py`.
- **Fail-fast parsing**: `utils.py` parsers return `None` only for known empty sentinels (`""`, `"0"`, `"N/A"`) and otherwise `raise ValueError` on unrecognized formats. Do not add broad `except` clauses or swallow parse errors.
- **Model field typing**: all model fields are `X | None = None` (or `Field(default_factory=list)`), because any XML attribute may be absent. `clean_attributes` decides conversion by substring-matching the annotation string (`"datetime"`, `"date"`, `"Decimal"`, `"bool"`), so field annotations must contain the expected type name.
- **Adding IBKR fields**: add the field to the relevant model in `models.py`; parsing picks it up automatically via `clean_attributes`. New enum values go in `enums.py`.
