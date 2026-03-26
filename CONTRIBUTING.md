# Contributing

Thanks for your interest in **bytesense**.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/build_fingerprints.py
```

## Checks before a PR

- `ruff check src/ tests/ benchmarks/`
- `mypy src/bytesense`
- `pytest tests/ -v --cov=bytesense` (must satisfy `fail_under` in `pyproject.toml`)
- `python scripts/fetch_cn_benchmark_samples.py` (for full benchmark parity with charset-normalizer’s `data/`)
- `pytest benchmarks/test_bench_detection.py -k accuracy -v`

Optional (with Rust installed):

```bash
maturin develop --release --manifest-path rust/Cargo.toml
pytest tests/test_rust.py -v
```

## Style

Match existing formatting and keep changes focused on the issue at hand.

## Author

Maintained by **Oğuzhan Kır**.
