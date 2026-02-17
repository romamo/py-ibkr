# Changelog

All notable changes to this project will be documented in this file.


## [0.1.2] - 2026-02-17

### Fixed
- CLI `download` command now defaults `to_date` to yesterday (instead of today) when only `from_date` is provided. This prevents "Statement not available" errors for current-day reports which are typically not ready.

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
