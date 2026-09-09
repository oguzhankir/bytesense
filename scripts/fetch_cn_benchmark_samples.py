"""Fetch the pinned benchmark corpus and verify every file's SHA-256."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/cn_official_manifest.json"
OUT_DIR = ROOT / "benchmarks/data/cn_official"


def main() -> None:
    spec = json.loads(MANIFEST.read_text())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for entry in spec["files"]:
        dest = OUT_DIR / entry["file"]
        if dest.is_file() and hashlib.sha256(dest.read_bytes()).hexdigest() == entry["sha256"]:
            continue
        request = urllib.request.Request(
            spec["base_url"] + entry["file"], headers={"User-Agent": "bytesense-benchmark/1.0"}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise RuntimeError(f"Hash mismatch for {entry['file']}")
        dest.write_bytes(data)
    print(f"Verified all {len(spec['files'])} samples at {spec['source_commit']}")


if __name__ == "__main__":
    main()
