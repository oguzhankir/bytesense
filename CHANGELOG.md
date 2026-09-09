# Changelog


## 1.0.0

### Detection and correctness
- Replace the bespoke ranking pipeline with a reproducibly generated character-pair model and optional native scoring.
- Strictly validate every returned codec against the complete input, with explicit sample/validation counts and completion status.
- Normalize filters on all paths; an empty isolation list permits no codecs.
- Use BOM-consuming UTF-16/32 codecs, improve non-Latin Unicode lane detection, and recognize 7-bit shift syntax.
- Remove fabricated confidence intervals; scores are explicitly uncalibrated. Language reporting is opt-in.

### Streams and data handling
- Consume streams to EOF by default with bounded memory and temporary-file spooling.
- Preserve late informative samples across chunk boundaries; reject feeding after finalization.
- Retain every mixed-document byte, including short tails, and preserve Unicode boundaries.
- Use strict decoding for repair and segments; do not silently replace undecodable bytes.
- Add CLI stdin support, configuration flags and meaningful exit codes.

### Packaging and verification
- Python 3.9+, portable compiler-free wheel/sdist installs, typed package marker, and CPython abi3 native wheels.
- Distinct pure/native CI, installed-wheel tests, version checks, pinned/hash-verified corpus inputs and reproducible comparison tools.
- Consolidate documentation; retain historical details in this changelog.

See the README migration notes for intentional 0.x behavior changes.

## [0.1.2] — 2025-03-26

### Changed

- **BOM fast path:** UTF-8 with BOM now reports `encoding="utf_8_sig"` (aligned with `codecs` / `CandidateSelector`), not `utf_8`.
- **Streaming:** In-band HTML/XML hints are probed on every `feed()` until a hint is found (scan limited to the first 4KB inside `_probe_inband_hint`); shared regex patterns imported from `hints.py`; `codecs` imported at module level.
- **`detect_multi`:** Adjacent same-encoding merges no longer re-run `from_bytes` on the full merged span; `byte_count` on the shared `DetectionResult` is updated with `dataclasses.replace`.
- **`repair_bytes`:** Explicit `max_iterations` and `chains` parameters instead of `**kwargs: object`.
- **Coverage:** `fail_under` raised from 50 to **75** (current suite ~75%; 85% remains a stretch goal with more `api` / fingerprint tests).

### Fixed

- `DocumentSegment` / `MultiEncodingResult` now use `slots` on Python 3.10+ like other dataclasses in the package.

## [0.1.1] — 2025-03-26

### Added

- `examples/` scripts (basic detection, `detect()`, streaming, repair, HTTP hints, multi-encoding)
- MkDocs documentation site and GitHub Actions workflow **Docs Pages** → [GitHub Pages](https://oguzhankir.github.io/bytesense/)
- `[project.optional-dependencies]` group `docs` (`mkdocs`, `mkdocs-material`, `pymdown-extensions`)
- `project.urls.Documentation` in `pyproject.toml`

### Fixed

- README logo on PyPI: use `raw.githubusercontent.com` URL (sdist has no `assets/` for the image)
- Source distribution: include `LICENSE` in maturin `include` so PyPI accepts `License-File` metadata

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
