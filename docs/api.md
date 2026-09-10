# API reference

## Detection

`from_bytes(data, steps=5, chunk_size=512, threshold=0.2, cp_isolation=None, cp_exclusion=None, language_threshold=0.1, enable_fallback=True, *, sample_size=4096, include_language=False, min_confidence=0.0, encoding_hint=None, use_hints=True)`

| Parameter | Behavior |
|---|---|
| `data` | `bytes` or `bytearray`; other types raise `TypeError`. |
| `sample_size` | Integer ≥64. Bounds statistical scoring, not full validation. An informative window avoids spending the budget entirely on an ASCII header. |
| `cp_isolation` | Allowed codec names; aliases normalized. `None` uses built-in candidates; `[]` permits none. |
| `cp_exclusion` | Excluded normalized codec names; exclusion wins conflicts. This is exact-codec filtering, not family filtering. |
| `threshold` | Maximum control-character fraction in a statistical candidate, 0–1. |
| `encoding_hint` | Preferred codec when BOM/Unicode checks do not already resolve the input; must validate completely. |
| `use_hints` | Consult HTML/XML declarations for legacy candidates. Disable with `False`; explicit caller hints still apply. |
| `include_language` | Opt-in language estimate. Language and encoding are separate inferences. |
| `language_threshold` | Minimum support for reporting a language, 0–1. |
| `min_confidence` | Abstain below this heuristic score, 0–1; not a target accuracy percentage. |
| `enable_fallback` | Allow an explicitly included codec as a low-confidence fallback only after full validation. |
| `steps`, `chunk_size` | Positive compatibility arguments retained from 0.x; statistical work is controlled by `sample_size`. |

Custom codecs must be explicitly included or hinted and provide a bytes-to-text incremental decoder through Python's codec registry. Binary transforms such as base64 and hex are rejected. Unknown codec names raise `LookupError`.

`from_path(path, **kwargs)` opens a binary file. `from_fp(fp, **kwargs)` reads from the current position in bounded chunks and leaves the caller's file open. Both consume to EOF and accept detection options plus the stream's `memory_limit`.

`is_binary(data, **kwargs)` reports positive binary evidence (known signatures or excessive control bytes), not merely an unknown encoding. It is a heuristic classifier.

`detect(data)` returns the familiar `encoding`, `confidence`, `language` dictionary. Field layout compatibility does not imply identical decisions to another library.

## Results

| `DetectionResult` field | Meaning |
|---|---|
| `encoding` | Python codec name or `None`. The chosen codec strictly decodes every validated byte. |
| `confidence` | Evidence score in [0,1]. Strong structural evidence can score 1; this is not a probability. |
| `confidence_interval` | `None`. Retained for migration compatibility. |
| `language` | Language estimate or empty string. |
| `alternatives` | Ranked sample-level hypotheses (`encoding`, `confidence`, `language`). Not full-input validation promises. |
| `bom_detected` | A recognized signature resolved the input. UTF-16/32 use BOM-consuming codecs by default. |
| `chaos`, `coherence` | Sample control fraction and statistical support; fast Unicode paths may omit language support. |
| `why` | Explanation of the decision, including hints or validation fallback. |
| `byte_count` | Bytes accepted by the call/stream. |
| `bytes_examined` | Scoring span or direct fast-path inspection count. Separate validation passes can read more bytes. |
| `bytes_validated` | Bytes strictly validated under the returned codec; zero when unknown. |
| `complete` | Input ended, rather than a preview or early/budget-limited result. |
| `status` | `matched`, `ambiguous`, `unknown`, `binary`, or `invalid`. |

`bool(result)` means an encoding exists. `to_dict()` is JSON-serializable. `complete=True` does not prove a guessed legacy encoding is the original encoding.

## Streaming

`StreamDetector(threshold=0.2, language_threshold=0.1, auto_stop_confidence=0.97, *, memory_limit=1048576, **detection_options)`

- `feed(chunk)` accepts bytes/bytearray. It never silently stops on stability.
- `result`, `encoding`, `confidence`, `language` expose a provisional guess.
- `bytes_fed`, `snapshot()`, `is_stable` expose progress. Stability is not end-of-input.
- `hint_from_headers(headers)` extracts a case-insensitive Content-Type charset.
- `finalize()` validates the full accepted stream and closes its spool. Repeated finalization returns the same result.
- `close()` releases an unfinished spool. A context manager closes it automatically.
- `reset()` closes the previous spool and starts a fresh input with the same options.

`detect_stream(chunks, *, stop_confidence=0.97, max_bytes=None, early_stop=False, **kwargs)` consumes to EOF by default. Explicit stopping returns `complete=False`. Oversized chunks are sliced before acceptance when `max_bytes` is set; the unused part has already been yielded by the source and cannot be restored. The accepted prefix may be fully validated while the source itself is incomplete.

Memory is bounded by the configured spool limit plus sample/decoder buffers and static model tables. Temporary disk usage grows with accepted input size. Very small chunks may create more Python call overhead.

## Repair and segmentation

`repair(text, max_iterations=2, chains=None)` returns original/repaired text, improvement, transformation chain, chaos scores and iteration count. `max_iterations` is 1 or 2. `repair_bytes(data, encoding=None, *, max_iterations=2, chains=None)` first decodes strictly; unknown encodings raise instead of replacing bytes. `is_mojibake(text, threshold=0.15)` is a repair-oriented heuristic.

`detect_multi(data, segment_size=4096, min_segment_bytes=128, merge_threshold=0.85)` returns contiguous, exhaustive `DocumentSegment` objects. Small tails are retained. A fully validated Unicode/stateful input is preserved as a single segment to avoid splitting code units/shift state. Mixed-encoding boundaries remain heuristic.

A segment exposes `start`, `end`, original `data`, `detection`, `encoding`, strict `.text` and `to_dict()`. `MultiEncodingResult` exposes `segments`, `is_uniform`, `dominant`, `.full_text` and `to_dict()`. Unknown segment text raises `UnicodeError`.

`best_hint(data, headers=None, max_scan_bytes=4096)`, `hint_from_content(...)` and `hint_from_http_headers(...)` are also public; declarations are hints, not proof.
