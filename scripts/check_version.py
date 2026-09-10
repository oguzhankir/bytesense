"""Reject a release whose tag, Python metadata and Cargo version disagree."""

import os
import runpy
from pathlib import Path

import tomllib

root = Path(__file__).resolve().parents[1]
module = runpy.run_path(str(root / "src/bytesense/version.py"))
version = module["__version__"]
assert module["VERSION"] == tuple(map(int, version.split(".")))
assert tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"] == version
assert tomllib.loads((root / "rust/Cargo.toml").read_text())["package"]["version"] == version
lock = tomllib.loads((root / "rust/Cargo.lock").read_text())
assert next(p["version"] for p in lock["package"] if p["name"] == "bytesense-core") == version
assert os.environ.get("RELEASE_TAG", f"v{version}") == f"v{version}"
print(f"Versions agree: {version}")
