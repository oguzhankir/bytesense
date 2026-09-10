# bytesense

**Detect the encoding. Validate every byte. Keep your data intact.**

bytesense detects text encodings with zero runtime dependencies and optional Rust acceleration. Every returned encoding strictly decodes all supplied bytes. File and stream APIs keep memory bounded by spooling larger inputs to a temporary file.

```python
from bytesense import from_bytes

raw = "café 世界".encode()
result = from_bytes(raw)
assert result.encoding == "utf_8"
assert result.complete and result.bytes_validated == len(raw)
```

Start with the [quick start](quickstart.md), explore the [API](api.md), or review [measured accuracy and performance](benchmarks.md).

Encoding detection is inference. Full decode validation rules out an invalid codec; it cannot disambiguate every legacy encoding. Confidence is an evidence score, not a calibrated probability.
