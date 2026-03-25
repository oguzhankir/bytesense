# Quick start

Install:

```bash
pip install bytesense
```

Detect encoding from bytes:

```python
from bytesense import from_bytes

result = from_bytes(data)
print(result.encoding, result.confidence, result.language)
```

Use the CLI:

```bash
bytesense myfile.txt
bytesense -m myfile.txt
```

For streaming HTTP or file reads, use `StreamDetector` (see README examples).
