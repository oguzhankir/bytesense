#!/usr/bin/env python3
"""Drop-in style dict like chardet / charset-normalizer (detect)."""
from __future__ import annotations

from bytesense import detect


def main() -> None:
    samples = [
        b"ASCII only",
        "Здравствуй, мир".encode("cp1251"),
        "こんにちは".encode("shift_jis"),
    ]
    for raw in samples:
        d = detect(raw)
        print(d)


if __name__ == "__main__":
    main()
