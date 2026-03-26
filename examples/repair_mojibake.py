#!/usr/bin/env python3
"""Mojibake repair after wrong decoding (repair, repair_bytes)."""
from __future__ import annotations

from bytesense import repair, repair_bytes


def main() -> None:
    # UTF-8 text wrongly interpreted as Latin-1 produces mojibake like "Ã©" for "é"
    garbled = "café".encode("utf-8").decode("latin_1")
    print("garbled string:", repr(garbled))
    out = repair(garbled)
    print("repair(str):", repr(out))

    raw = garbled.encode("latin_1")
    rb = repair_bytes(raw)
    print("repair_bytes improved:", rb.improved)
    print("repaired text:", repr(rb.repaired))


if __name__ == "__main__":
    main()
