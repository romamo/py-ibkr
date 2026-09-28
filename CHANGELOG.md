# Changelog

All notable changes to this project will be documented in this file.


## [Unreleased]

### Fixed
- `FlexClient` requests no longer hang forever when IBKR stalls: every request now has a timeout (`FlexClient(timeout=60.0)`, seconds per connect or read). A stall raises the new `FlexTimeoutError` (a `FlexError`); previously a read timeout escaped as a bare `TimeoutError`.

### Added
- `download` CLI gains `--timeout` (default 60s); zero or negative values are rejected.

## [0.1.7] - 2026-07-15

### Changed
- `download` CLI caps `--to-date` at the previous day: IBKR has no finalized data for today or the future, so a to-date of today or later is snapped back to yesterday with a note on stderr.

## [0.1.6] - 2026-07-15

### Added
- `download` CLI gains `-v`/`--verbose` (repeatable): `-v` enables INFO logging (request/fetch progress and retry notices), `-vv` enables DEBUG (per-request GET/byte-count traces).
- `FlexClient` now emits structured logging via a module logger; the Flex token is redacted (`t=***`) from any logged URL.

## [0.1.5] - 2026-07-15

### Added
- `FlexLockoutError` for IBKR error 1025 ("too many failed attempts"); treated as terminal and never retried.
- Configurable `--max-retry-interval` CLI option (default 120s) capping the polling backoff.
- CLI snaps weekend `--from-date`/`--to-date` values onto weekdays (Sat/Sun -> Fri/Mon), since IBKR Flex rejects weekend dates with error 1003.

### Changed
- Hardened download polling for slow-to-generate statements: `max_retries` 10 -> 20, base `retry_interval` 10s -> 60s.
- Refactored `FlexClient` internals: single error-code-to-exception mapping table and a unified `poll()` retry helper.
- Added an sdist exclude list to keep internal files out of published artifacts.

## [0.1.4] - 2026-02-28

### Changed
- Integrated Domain Value Objects for `AccountID`, `CurrencyCode`, `Symbol`, `ConID`, etc.
- Implemented `VO.Input` pattern for better developer experience and strict typing.
- Refactored parsing utilities to be "fail-fast" and remove error swallowing.
- Updated `FlexClient` to use strictly typed domain identifiers.
- restored full matrix testing (Python 3.10-3.14) in CI.
- Updated dependencies: added `pydantic-extra-types` and `pycountry`.

## [0.1.3] - 2026-02-18


## [0.1.2] - 2026-02-17 (Broken)
- Partial release (failed due to missing files and PyPI reuse policy).

## [0.1.1] - 2026-02-05

### Added
- Added `CashReport` and `CashReportCurrency` models.

### Changed
- Moved parsing utility functions to `src/py_ibkr/flex/utils.py`.
- Refactored `parser.py` to use `utils.py`.
- Fixed linting issues.

## [0.1.0] - 2026-02-05

### Added
- Initial release of `py-ibkr`.
- Pydantic models for IBKR Flex Query.
- Parser for XML Flex Query reports.
- Support for Trade and CashTransaction models.
- OSS packaging standards (LICENSE, MANIFEST.in, py.typed).
- GitHub Actions for CI and PyPI publication.
