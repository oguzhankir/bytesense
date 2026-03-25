# API reference

## `from_bytes(data, ...) -> DetectionResult`

Main entry point for raw `bytes` / `bytearray`. Returns a `DetectionResult` with `encoding`, `confidence`, `language`, `why`, and related fields.

## `from_path(path, ...) -> DetectionResult`

Reads a file and runs detection.

## `from_fp(fp, ...) -> DetectionResult`

Reads from a binary file object (does not close it).

## `is_binary(data, ...) -> bool`

Heuristic for whether input looks like binary (non-text) data.

## `detect(byte_str) -> dict`

Drop-in compatible with `chardet.detect` / `charset_normalizer.detect` style dicts (`encoding`, `confidence`, `language`).

## `StreamDetector`

Incremental detector: `feed(chunk)`, then read `encoding`, `confidence`, `language`, or call `finalize()`. Optional `hint_from_headers()` for HTTP charset hints.

## `DetectionResult`

- `encoding`: IANA-style name (e.g. `utf_8`, `cp1252`) or `None`
- `confidence`, `confidence_interval`, `chaos`, `coherence`
- `alternatives`: list of `EncodingAlternative`
- `bom_detected`, `byte_count`, `why`

Use `to_dict()` for JSON-serializable output.
