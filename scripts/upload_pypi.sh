#!/usr/bin/env bash
# Build sdist and upload to production PyPI (pypi.org). Activate venv; pip install -e ".[dev]"
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python scripts/build_fingerprints.py
rm -rf dist/*
maturin sdist -o dist/

# Optional: wheel for this machine only (Rust required)
# maturin build --release -o dist/ --manifest-path rust/Cargo.toml

twine check dist/*
echo "Uploading to https://pypi.org/ ..."
echo "Create an API token at https://pypi.org/manage/account/token/"
echo "export TWINE_USERNAME=__token__"
echo "export TWINE_PASSWORD='<pypi token starting with pypi->'"
twine upload dist/*
