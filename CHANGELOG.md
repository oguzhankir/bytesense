# Changelog

## [0.1.0] — 2025-03-26

First published release.

### Added

- `from_bytes()`, `from_path()`, `from_fp()`, `is_binary()` API
- `detect()` chardet / charset-normalizer drop-in compatibility
- `detect_stream()` for iterator-based streaming detection
- `StreamDetector` for incremental detection; `snapshot()`, `is_stable`, auto-stop when encoding is stable (configurable)
- In-band hints from HTML meta tags and XML declarations in `StreamDetector`
- Byte-distribution fingerprinting with pre-computed lookup table
- `repair()` and `repair_bytes()` for mojibake detection and repair; `is_mojibake()`; `RepairResult`
- `hint_from_http_headers()`, `hint_from_content()`, `best_hint()` for standalone hint extraction
- `detect_multi()` for multi-encoding documents; `MultiEncodingResult` and `DocumentSegment`
- Optional Rust core extension (`pip install "bytesense[fast]"`)
- CLI: `bytesense <file>`
- `py.typed` marker for PEP 561 compliance
- Full type annotations, mypy strict mode
- GitHub Actions CI across 3 OS × multiple Python versions

### Changed

- `LANGUAGE_ENCODINGS` aligned with languages in `CHAR_FREQUENCIES`
- Candidate shortlist tuned for speed while preserving accuracy targets

### Fixed

- Benchmark and packaging fixes (e.g. UTF-8 BOM test fixture, build backend configuration)
