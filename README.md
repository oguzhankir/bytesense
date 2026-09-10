<p align="center">
  <img src="https://raw.githubusercontent.com/oguzhankir/bytesense/main/assets/bytesense_logo.svg" alt="bytesense" width="480" />
</p>
<p align="center"><strong>Detect the encoding. Validate every byte. Keep your data intact.</strong></p>
<p align="center">
  <a href="https://pypi.org/project/bytesense/"><img src="https://img.shields.io/pypi/v/bytesense.svg" alt="PyPI" /></a>
  <a href="https://github.com/oguzhankir/bytesense/actions/workflows/ci.yml"><img src="https://github.com/oguzhankir/bytesense/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="https://github.com/oguzhankir/bytesense/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT license" /></a>
</p>

**bytesense** is a Python encoding detector for file imports, multilingual text pipelines and legacy data. It combines fast Unicode checks, compact character-pair statistics and optional Rust acceleration—with **zero runtime dependencies**.

Final detection results strictly validate the selected encoding against the complete supplied input. Linguistic scoring uses a bounded sample; stream inputs spill to a temporary file after a configurable memory limit. Results tell you what was examined, what was validated, and whether the input ended.

```python
from bytesense import from_bytes

data = "İstanbul'da çalışan mühendisler için doğru metin çözümleme. ".encode("cp1254")
result = from_bytes(data)
if result.encoding:
    text = data.decode(result.encoding)  # strict decoding; no replacement characters
    print(result.encoding, result.bytes_validated, result.complete)
```

## Install

```bash
pip install bytesense
```

Python **3.9+**. Platform wheels include Rust acceleration; the portable wheel works without a compiler. Source installations automatically use Rust when a toolchain is available. To explicitly choose a source build:

```bash
BYTESENSE_BUILD_RUST=0 pip install --no-binary=bytesense bytesense  # pure Python
BYTESENSE_BUILD_RUST=1 pip install --no-binary=bytesense bytesense  # require Rust
```

The old `[fast]` extra is a compatibility alias. It does not install an accelerator separately. `BYTESENSE_PURE_PYTHON=1` selects the Python implementation at runtime.

## Built for dependable imports

- **Complete validation:** a valid prefix cannot hide an undecodable suffix. Unknown and binary inputs have explicit outcomes.
- **Bounded streams:** feed small chunks or large ones; finalization accounts for every accepted byte. Preview stability never silently ends a stream.
- **Useful controls:** codec aliases, inclusion/exclusion filters, encoding hints, optional language estimates and a minimum evidence score.
- **Transparent results:** `why`, alternatives, sample/validation counts and completion status. Confidence is a heuristic score; no fabricated statistical intervals.
- **Portable acceleration:** native character-pair scoring and byte histograms, with matching Python behavior and typed public APIs.
- **Data repair tools:** opt-in mojibake repair and byte-preserving mixed-document segmentation, with strict decoding.

Decodability alone cannot prove the original encoding. Several legacy codecs can decode identical bytes into different, plausible text. Use a known encoding or an explicit hint when you have one, and evaluate representative data before switching detectors.

## Files, streams and existing integrations

```python
from bytesense import detect, detect_stream, from_path

result = from_path("export.csv", include_language=True)
print(result.to_dict())

with open("archive.txt", "rb") as source:
    result = detect_stream(iter(lambda: source.read(64 * 1024), b""))
assert result.complete

# Familiar dictionary interface for code that uses chardet.detect().
metadata = detect(b"hello world")
```

`detect_stream()` consumes to EOF by default. `max_bytes=...` or `early_stop=True` is an explicit sampling choice and returns `complete=False` when it stops early. Streaming uses temporary disk space beyond `memory_limit` (1 MiB by default); close an unfinished `StreamDetector` or use it as a context manager.

```bash
bytesense report.csv
bytesense --language --verbose report.csv
cat report.csv | bytesense --minimal -
```

The CLI exits **0** when every input has an encoding, **1** for read failures or unknown/binary inputs, and **2** for invalid arguments. JSON goes to stdout; errors go to stderr.

## Measured accuracy and performance

The v1 engine replaces the previous collection of special-case ranking rules with a small, reproducibly generated statistical model. The evaluation separates development documents from held-out documents, grouping identical decoded text across encodings. Accuracy means **exact Unicode equality**, not just a compatible codec name.

| Detector | Exact Unicode matches | Accuracy |
|---|---:|---:|
| **bytesense 1.1.0** | **1907 / 2078** | **91.77%** |
| bytesense 1.0.0 | 1906 / 2078 | 91.72% |
| bytesense 0.1.2 | 883 / 2078 | 42.49% |
| chardet 7.6.0 | 2060 / 2078 | 99.13% |
| charset-normalizer 3.5.1 | 1679 / 2078 | 80.80% |
| chardetng-py 0.3.5 | 776 / 2078 | 37.34% |

See [benchmarks and methodology](https://oguzhankir.github.io/bytesense/benchmarks/) for measured comparisons with chardet, charset-normalizer and chardetng, including the cases where another detector wins. Timing reports distinguish default behavior from an additional full-decode validation step.

**New in 1.1:** faster legacy scoring, canonical-Unicode evidence, and deeper full-input validation. On a new 432-case transfer check built from 28 UDHR translations, exact recovery increased from **374 to 394 cases**; charset-normalizer recovered 381 and chardet 422. These are correlated variants of one translated document, not a universal accuracy ranking. Chardet remains more accurate on both reported corpora.

The measured Turkish CP1254 and Japanese EUC-JP workloads run approximately **2.8× faster than bytesense 1.0** with the native backend. See the benchmark table for absolute timings and where competitors remain faster.

## Upgrading from 0.x

- Language reporting is opt-in: `include_language=True`.
- `confidence_interval` remains available and is `None`; scores are not calibrated probabilities.
- An empty `cp_isolation=[]` allows no codecs. Filters apply to every detection path.
- BOM-bearing UTF-16/32 selects `utf_16`/`utf_32`, which consume the signature when decoding.
- No unvalidated UTF-8 fallback; stream finalization and repair decoding reject silent data loss.
- `StreamDetector.feed()` after finalization raises. `reset()` starts a new stream.
- Python 3.8 is no longer supported. `steps` and `chunk_size` remain accepted compatibility arguments; use `sample_size` to control statistical work.

[Quick start](https://oguzhankir.github.io/bytesense/quickstart/) · [API](https://oguzhankir.github.io/bytesense/api/) · [Changes](https://github.com/oguzhankir/bytesense/blob/main/CHANGELOG.md) · [Contributing](https://github.com/oguzhankir/bytesense/blob/main/CONTRIBUTING.md)

Created by [Oğuzhan Kır](https://github.com/oguzhankir). MIT-licensed code. The aggregate model's data provenance and reproduction steps are documented with the benchmarks; upstream test documents remain copyrighted by their respective publishers.
