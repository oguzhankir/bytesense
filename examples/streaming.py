#!/usr/bin/env python3
"""Incremental detection with StreamDetector (chunked input)."""
from __future__ import annotations

from bytesense import StreamDetector


def main() -> None:
    payload = "Streamed UTF-8: naïve café".encode("utf-8")
    det = StreamDetector()
    chunk_size = 5
    for i in range(0, len(payload), chunk_size):
        det.feed(payload[i : i + chunk_size])
    det.finalize()
    print(f"encoding={det.encoding!r}")
    print(f"confidence={det.confidence:.4f}")
    print(f"language={det.language!r}")
    print(f"stable={getattr(det, 'is_stable', 'n/a')}")


if __name__ == "__main__":
    main()
