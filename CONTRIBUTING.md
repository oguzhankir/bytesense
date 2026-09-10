# Contributing

Follow the [Code of Conduct](CODE_OF_CONDUCT.md). Use a focused `oguzhankir/<topic>` branch and sign commits with `git commit -s` under the project's DCO.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
BYTESENSE_BUILD_RUST=0 pip install -e '.[dev,docs]'
python scripts/fetch_cn_benchmark_samples.py
ruff check src tests benchmarks scripts setup.py
mypy src/bytesense
BYTESENSE_PURE_PYTHON=1 pytest tests --cov=bytesense --cov-branch
pytest benchmarks/test_bench_detection.py benchmarks/test_hard_scenarios.py --benchmark-disable
mkdocs build --strict
```

On Windows, set environment variables using your shell's syntax. Native development requires Rust 1.88+:

```bash
BYTESENSE_BUILD_RUST=1 pip install -e . --no-build-isolation
BYTESENSE_EXPECT_RUST=1 pytest tests
cargo test --manifest-path rust/Cargo.toml --locked
```

CI tests pure and native installations separately on Linux, macOS and Windows. Packaging jobs install and test actual wheels, check abi3 compatibility, and test the sdist without compiling Rust. The coverage floor remains 75%; timing measurements are reports, not noisy speed assertions.

## Model and benchmarks

The [benchmark documentation](docs/benchmarks.md) describes corpus pins, Unicode-based grouping and reproduction commands. Keep development and holdout documents separate. Do not tune the model on the holdout, silently omit missing inputs, compare differently sized payloads, or advertise sample-only latency as full-input validation latency.

`language.json.gz` contains aggregate character-pair statistics; no test documents are bundled. The core retains static model metadata, never document text in a global cache. Native and Python paths must agree within numerical tolerance and produce the same rounded detection scores.

## Release

Keep `pyproject.toml`, `rust/Cargo.toml`, and `src/bytesense/version.py` aligned; `python scripts/check_version.py` checks them. Update the existing changelog and API/migration documentation when behavior changes.

```bash
BYTESENSE_BUILD_RUST=0 python -m build
python scripts/check_dist.py dist
python -m twine check --strict dist/*
```

Publishing a GitHub Release triggers the release workflow. It checks the tag, builds and tests portable/native distributions, then uses the configured PyPI trusted publisher environment. A PR does not publish a release.

Keep documentation focused: README, quick start, API reference, benchmarks, and the shared changelog. Put rationale and validation detail in the PR instead of creating additional planning documents.
