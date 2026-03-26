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

## Test PyPI (release dry-run)

Build fingerprints, create an sdist, check it, then upload (requires `pip install -e ".[dev]"` for `twine` and `maturin`):

```bash
# Create a token at https://test.pypi.org/manage/account/token/ then paste it below (keep the quotes).
export TWINE_USERNAME=__token__
export TWINE_PASSWORD='pypi-AgEIcHlwaS5vcmc...'
./scripts/upload_testpypi.sh
```

Do not put `#` comments on the same line as `export TWINE_PASSWORD=...`: an apostrophe inside the comment can break zsh parsing.

Install the uploaded package (use PyPI as an extra index so build backends like `maturin` resolve from production PyPI):

```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ bytesense
```

## PyPI (production)

Publishing runs from [`.github/workflows/release.yml`](.github/workflows/release.yml) when you **publish** a GitHub Release (draft releases do not run it). Bump `version` in `pyproject.toml` and `rust/Cargo.toml` to match the release tag first.

On PyPI, enable **trusted publishing** for this repository: [project → Settings → Publishing](https://pypi.org/manage/project/bytesense/settings/publishing/). The workflow uses OIDC (`id-token: write`); no `PYPI_API_TOKEN` secret is required.

## Style

Match existing formatting and keep changes focused on the issue at hand.

## Author

Maintained by **Oğuzhan Kır**.
