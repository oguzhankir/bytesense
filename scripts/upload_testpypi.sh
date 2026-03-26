#!/usr/bin/env bash
# Build sdist and upload to Test PyPI. Activate your venv first; install dev deps: pip install -e ".[dev]"
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python scripts/build_fingerprints.py
rm -rf dist/*
maturin sdist -o dist/

# Optional: add a wheel for the current platform (needs Rust toolchain)
# maturin build --release -o dist/ --manifest-path rust/Cargo.toml

twine check dist/*
echo "Uploading to Test PyPI..."
echo "Set TWINE_USERNAME=__token__ and TWINE_PASSWORD to your Test PyPI API token, or configure ~/.pypirc (gitignored)."
twine upload --repository testpypi dist/*
