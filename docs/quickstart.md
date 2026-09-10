# Quick start

```bash
pip install bytesense
```

Python 3.9+; no runtime dependencies. Native platform wheels include the accelerator. A portable wheel and compiler-free source installation are available. Set `BYTESENSE_BUILD_RUST=0` for a pure source build, `BYTESENSE_BUILD_RUST=1` to require Rust, or `BYTESENSE_PURE_PYTHON=1` to use Python scoring at runtime.

## Detect and decode

```python
from bytesense import from_bytes, from_path

raw = "Café à Paris".encode("cp1252")
result = from_bytes(raw, cp_isolation=["cp1252", "utf8"])
if result.encoding:
    text = raw.decode(result.encoding)

result = from_path("export.csv", include_language=True)
print(result.encoding, result.language, result.why)
```

`complete=True` means the supplied input ended. `bytes_validated` counts bytes strictly validated under the returned codec. `bytes_examined` reports the scoring/fast-path span. Unknown and binary results have `encoding=None`; alternatives are sample-level hypotheses and are not guaranteed to decode the entire input.

## Streams

```python
from bytesense import StreamDetector

with StreamDetector(memory_limit=1024 * 1024) as detector:
    with open("archive.txt", "rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            detector.feed(chunk)
    result = detector.finalize()
assert result.complete
```

Preview results have `complete=False`. Feed continues even if the guess becomes stable. Finalization is idempotent; feeding afterward raises. Use `reset()` for another input. Temporary disk use grows with the stream size beyond the memory limit.

## Repair and mixed documents

```python
from bytesense import repair, detect_multi

print(repair("cafÃ©").repaired)
segments = detect_multi("日本語🙂".encode(), segment_size=127)
assert segments.full_text == "日本語🙂"
```

Repair is opt-in and heuristic; inspect `RepairResult.improved` and keep the original. `repair_bytes()` and segment `.text` decode strictly. Mixed segmentation preserves all bytes, but finding a true encoding boundary without external structure remains heuristic. Prefer format-provided part boundaries when available.

## CLI

```bash
bytesense export.csv
bytesense --language --verbose export.csv
cat export.csv | bytesense --minimal -
```

Exit codes: 0 = all inputs detected, 1 = read/unknown/binary outcome, 2 = invalid arguments. `--sample-size` bounds linguistic scoring; complete decoding is still validated.
