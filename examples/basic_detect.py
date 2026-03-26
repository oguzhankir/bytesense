#!/usr/bin/env python3
"""Detect encoding from raw bytes and from a file (from_bytes, from_path)."""
from __future__ import annotations

from pathlib import Path

from bytesense import from_bytes, from_path


def main() -> None:
    text = "Café naïve — résumé"
    data = text.encode("utf-8")
    r = from_bytes(data)
    print("from_bytes:")
    print(f"  encoding={r.encoding!r}  confidence={r.confidence:.3f}  language={r.language!r}")
    print(f"  bytes={r.byte_count}  bom={r.bom_detected}")

    root = Path(__file__).resolve().parent.parent
    readme = root / "README.md"
    if readme.is_file():
        r2 = from_path(readme)
        print("\nfrom_path (README.md):")
        print(f"  encoding={r2.encoding!r}  confidence={r2.confidence:.3f}")
    else:
        print("\n(Skip from_path: README.md not found next to repo root.)")


if __name__ == "__main__":
    main()
