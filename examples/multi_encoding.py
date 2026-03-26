#!/usr/bin/env python3
"""Mixed-encoding documents: segment-wise detection (detect_multi)."""
from __future__ import annotations

from bytesense import detect_multi


def main() -> None:
    english = ("Hello world. " * 80).encode("utf-8")
    russian = ("Привет, мир. " * 40).encode("cp1251")
    data = english + russian
    result = detect_multi(data, segment_size=2048, min_segment_bytes=64)
    print(f"uniform={result.is_uniform}  segments={len(result.segments)}")
    for seg in result.segments:
        snippet = seg.text[:48].replace("\n", " ")
        print(f"  [{seg.start}:{seg.end}] {seg.encoding!r}  {snippet!r}...")


if __name__ == "__main__":
    main()
