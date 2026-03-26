<h1 align="center">bytesense</h1>
<p align="center">
  <strong>Charset detection that stays fast, honest, and dependency-free.</strong><br>
  <sub>Byte fingerprints · pre-computed tables · optional Rust · zero ML · zero runtime dependencies</sub>
</p>

<p align="center">
  <a href="https://pypi.org/project/bytesense/">
    <img src="https://img.shields.io/pypi/v/bytesense.svg" alt="PyPI version" />
  </a>
  <a href="https://pypi.org/project/bytesense/">
    <img src="https://img.shields.io/pypi/pyversions/bytesense.svg" alt="Python versions" />
  </a>
  <a href="https://github.com/oguzhankir/bytesense/actions/workflows/ci.yml">
    <img src="https://github.com/oguzhankir/bytesense/actions/workflows/ci.yml/badge.svg" alt="CI" />
  </a>
  <a href="https://codecov.io/gh/oguzhankir/bytesense">
    <img src="https://codecov.io/gh/oguzhankir/bytesense/graph/badge.svg" alt="codecov" />
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
  </a>
</p>

<p align="center">
  <sub>Author: <strong>Oğuzhan Kır</strong> · <a href="https://github.com/oguzhankir/bytesense">GitHub</a> · <a href="docs/">Docs</a></sub>
</p>

---

**bytesense** reads raw bytes and tells you which encoding likely produced them—without shipping neural nets, without pulling in other Python packages at install time, and with an explainable `why` on every result. It is designed as a modern alternative to **chardet** and **charset-normalizer** for teams that want predictable performance and a small install footprint.

If you already use `chardet.detect()` or `charset_normalizer.detect()`, you can swap in `bytesense.detect()` with minimal code churn.

## At a glance

| | [chardet](https://github.com/chardet/chardet) | [charset-normalizer](https://github.com/Ousret/charset_normalizer) | **bytesense** |
|---|:---:|:---:|:---:|
| **Runtime Python dependencies** | 0 | 0 | **0** |
| **ML / model weights** | No | No | **No** |
| **Native acceleration (optional)** | — | — | **Rust** (`pip install "bytesense[fast]"`)
| **Streaming-first API** | Limited | Via API patterns | **`StreamDetector`**
| **Explainable result (`why`)** | Partial | Rich metadata | **Yes** (always)
| **Wheel size (typical)** | ~hundreds of kB | ~150 kB | **Small** (pure Python + data tables)
| **IANA encodings (via stdlib codecs)** | Broad | Broad | **Broad** (same idea: decode candidates)

This table compares *design*; run the included benchmarks on your own hardware and datasets to compare latency and accuracy for your workload.

## Performance

Benchmarks use (1) **synthetic** samples and (2) **charset-normalizer’s published `data/` files** with the same expected encodings as their `tests/test_full_detection.py` (downloaded into `benchmarks/data/cn_official/`).

```bash
pip install -e ".[dev]"
python scripts/build_fingerprints.py
python scripts/fetch_cn_benchmark_samples.py   # official CN corpus (use the same venv — see below)
```

**One-shot report** (accuracy tables, hard scenarios, speed benches — paste the whole terminal output):

```bash
./scripts/run_all_benchmarks.sh              # full run
./scripts/run_all_benchmarks.sh --no-speed   # skip pytest-benchmark (faster)
```

Individual steps:

```bash
pytest benchmarks/test_bench_detection.py -k "accuracy" -v -s   # -s prints accuracy tables
pytest benchmarks/test_hard_scenarios.py -v -s   # optional: paragraph-sized stress corpus (three-way table)
pytest benchmarks/test_bench_detection.py \
  -k "test_bench_bytesense_fast_path or test_bench_cn_fast_path or test_bench_bytesense_full or test_bench_cn_full or test_bench_chardet_full" \
  --benchmark-sort=mean -v
```

**Why strict scores can look harsh:** charset-normalizer is trained and regression-tested on this exact `data/` set, so it will usually win on **strict** (same IANA label as the reference). That is expected, not a bug in your setup. **Functional** accuracy (same Unicode text after decode) is the fairer “did we recover the text?” metric when several labels are equivalent.

**Fingerprint script:** Lines like `utf_16` “skipped” are normal — those encodings are handled by BOM / null-byte logic, not the single-byte histogram table.

**Troubleshooting `fetch_cn_benchmark_samples.py` (SSL on macOS):** Always run scripts with the project interpreter, e.g. `.venv/bin/python scripts/fetch_cn_benchmark_samples.py`. Install CA bundles with `pip install certifi` (included in `[dev]`). If HTTPS still fails: run Apple’s *Install Certificates.command* for your Python, or `python scripts/fetch_cn_benchmark_samples.py --insecure` as a last resort.

The summary test prints **two** scores per library:

- **Strict**: detected codec name matches the reference (after `codecs.lookup` normalization).
- **Functional**: decoded **Unicode text** matches what the reference encoding would produce (so cp1253 vs iso8859_7 counts as correct when the bytes decode to the same string—same idea charset-normalizer uses when multiple labels fit).

| Library | Accuracy (dataset) | Notes |
|--------|-------------------|--------|
| bytesense (pure Python) | Run `pytest … -k accuracy` | Synthetic corpus: strict gate; CN files: functional floor in tests |
| bytesense + Rust | Same detection path; faster histogram / UTF-8 helpers | `maturin develop --release`
| charset-normalizer | Printed in `test_charset_normalizer_accuracy_for_comparison` | Should hit 100% functional on its own `data/` files |
| chardet | Optional in speed benches | Legacy baseline |

Fill the **mean / p95 / p99** table from your `pytest-benchmark` JSON and paste it here for your release notes.

## Installation

```bash
pip install bytesense                 # pure Python — always works
pip install "bytesense[fast]"       # same API; uses Rust wheel when available for your platform
```

## CLI

`bytesense` ships with a small CLI for files on disk.

```text
usage: bytesense [-h] [-v] [-m] [--version] FILE [FILE ...]

positional arguments:
  FILE              File(s) to analyse

optional arguments:
  -h, --help        show this help and exit
  -v, --verbose     Include the ``why`` field in JSON (``confidence_interval`` is always shown)
  -m, --minimal     Print only the detected encoding name
  --version         Show version and exit
```

```bash
bytesense ./README.md
bytesense -m ./README.md
python -m bytesense.cli --version
```

`stdout` is JSON (one object per file, or a list when multiple files and not `-m`):

```json
{
  "encoding": "utf_8",
  "confidence": 0.98,
  "confidence_interval": [0.93, 1.0],
  "language": "English",
  "alternatives": [],
  "bom_detected": false,
  "chaos": 0.02,
  "coherence": 0.41,
  "byte_count": 2048,
  "path": "/absolute/path/to/file"
}
```

Use ``-v`` to add the human-readable ``why`` string to each object.

## Python

**Full result object**

```python
from bytesense import from_bytes, from_path

result = from_path("notes.txt")
print(result.encoding, result.confidence, result.language)
print(result.why)
```

**Streaming**

```python
from bytesense import StreamDetector

det = StreamDetector()
for chunk in response.iter_content(1024):
    det.feed(chunk)
    if det.confidence >= 0.99:
        break
print(det.encoding, det.language)
```

**Drop-in `detect()`**

```python
from bytesense import detect

print(detect(b"hello"))  # {"encoding", "confidence", "language"}
```

More detail: [docs/api.md](docs/api.md) · [docs/quickstart.md](docs/quickstart.md)

## Why bytesense

- **Decode as late as possible.** Histograms, BOMs, and null-byte layout often rule out whole families of encodings before you spend CPU on full decodes.
- **Shortlist, then verify.** Cosine similarity against pre-generated fingerprints (see `scripts/build_fingerprints.py`) keeps the expensive “mess + coherence” phase on a handful of candidates.
- **No black boxes.** No training step, no weights to tune, no network calls—just tables and statistics you can inspect.
- **Rust is optional.** `pip install bytesense` never requires a compiler; Rust only accelerates hot paths when a wheel matches your platform.

## How it works (short)

1. **Fingerprint** the byte distribution and compare to pre-computed vectors.
2. **Decode** only the shortlisted encodings (strict), in a controlled order.
3. **Mess** — score how “garbled” the decoded text looks (printable ratio, bigrams, etc.).
4. **Coherence** — score language plausibility using character-frequency priors.
5. **Rank** and return the best hypothesis plus a human-readable **why**.

## Known limitations

- Very short inputs (dozens of bytes) are inherently ambiguous; any detector will guess.
- Mixed-language text can confuse language coherence.
- Like any heuristic detector, adversarial or random binary data may yield a best-effort encoding with low confidence.

## Contributing

Issues and PRs are welcome: [CONTRIBUTING.md](CONTRIBUTING.md) · [Issues](https://github.com/oguzhankir/bytesense/issues)

## License

MIT — see [LICENSE](LICENSE).

Copyright © Oğuzhan Kır.
