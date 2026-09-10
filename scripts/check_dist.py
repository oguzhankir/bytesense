"""Verify distribution payloads, including typing and reproducible model data."""

import sys
import tarfile
import zipfile
from pathlib import Path

for path in sorted(Path(sys.argv[1]).iterdir()):
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if "none-any" in path.name:
                assert not any(n.endswith((".so", ".pyd", ".dll")) for n in names)
            assert "bytesense/py.typed" in names
            assert "bytesense/data/language.json.gz" in names
            assert not any("/target/" in n for n in names)
    elif path.name.endswith(".tar.gz"):
        with tarfile.open(path) as archive:
            names = archive.getnames()
            for required in (
                "setup.py",
                "scripts/evaluate_corpus.py",
                "benchmarks/cn_official_manifest.json",
                "rust/Cargo.toml",
                "rust/Cargo.lock",
                "rust/src/language.rs",
                "src/bytesense/py.typed",
                "src/bytesense/data/language.json.gz",
            ):
                assert any(n.endswith("/" + required) for n in names), required
            assert not any("/target/" in n for n in names)
    else:
        continue
    print(f"Payload verified: {path.name}")
