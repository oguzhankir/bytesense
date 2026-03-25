# Changelog

## [0.1.0] — Unreleased

### Added

- Initial release
- `from_bytes()`, `from_path()`, `from_fp()`, `is_binary()` API
- `detect()` chardet/charset-normalizer drop-in compatibility
- `StreamDetector` for incremental detection
- Byte-distribution fingerprinting with pre-computed lookup table
- Optional Rust core extension (`pip install "bytesense[fast]"`)
- CLI: `bytesense <file>`
- Full type annotations, mypy strict mode
- GitHub Actions CI across 3 OS × 6 Python versions
