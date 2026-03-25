"""
Pre-compute byte-frequency fingerprints for all supported encodings.

Algorithm per encoding:
  1. For each byte value 0x00–0xFF, attempt to decode it with the encoding.
  2. Record which bytes decode to printable, non-control characters.
  3. Build a 256-element vector and L2-normalise it.

The resulting vectors are used for cosine-similarity shortlisting at runtime.

Run this once after cloning:
    python scripts/build_fingerprints.py
"""
from __future__ import annotations

import codecs
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from bytesense.constant import ALL_ENCODINGS  # noqa: E402

# Histogram fingerprints are single-byte tables; UTF-16/32 are not meaningful here
# (detection uses BOM / null-byte layout in candidate.py instead).
_SKIP_EXPLAIN_MULTIBYTE_UNIT = frozenset(
    {"utf_16", "utf_16_be", "utf_16_le", "utf_32", "utf_32_be", "utf_32_le"},
)


def build_fingerprint(encoding: str) -> list[float] | None:
    try:
        codecs.lookup(encoding)
    except LookupError:
        return None

    vector = [0.0] * 256
    for i in range(256):
        try:
            char = bytes([i]).decode(encoding, errors="ignore")
            if char and char.isprintable():
                vector[i] = 1.0
        except Exception:
            pass

    magnitude = math.sqrt(sum(x * x for x in vector))
    if magnitude == 0.0:
        return None
    return [x / magnitude for x in vector]


def main() -> None:
    out_dir = ROOT / "src" / "bytesense" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "__init__.py").touch()

    fingerprints: dict[str, list[float]] = {}
    skipped: list[str] = []

    for encoding in ALL_ENCODINGS:
        fp = build_fingerprint(encoding)
        if fp is not None:
            fingerprints[encoding] = fp
            print(f"  ✓  {encoding}")
        else:
            skipped.append(encoding)
            if encoding in _SKIP_EXPLAIN_MULTIBYTE_UNIT:
                print(
                    f"  ·  {encoding}  (not used — multibyte UTF-16/32; "
                    "shortlist uses BOM/null-byte rules, not this table)"
                )
            else:
                print(f"  ✗  {encoding}  (skipped — no valid single-byte decodings)")

    lines = [
        '"""',
        "Auto-generated encoding fingerprint table.",
        "Do not edit manually — regenerate with:  python scripts/build_fingerprints.py",
        '"""',
        "from __future__ import annotations",
        "",
        "ENCODING_FINGERPRINTS: dict[str, list[float]] = {",
    ]
    for enc, fp in sorted(fingerprints.items()):
        fp_str = ", ".join(f"{x:.6f}" for x in fp)
        lines.append(f"    {enc!r}: [{fp_str}],")
    lines.append("}")
    lines.append("")

    out_file = out_dir / "fingerprints.py"
    out_file.write_text("\n".join(lines), encoding="utf-8")

    print(f"\n✓ Wrote {len(fingerprints)} fingerprints to {out_file}")
    mb = [x for x in skipped if x in _SKIP_EXPLAIN_MULTIBYTE_UNIT]
    other = [x for x in skipped if x not in _SKIP_EXPLAIN_MULTIBYTE_UNIT]
    if mb:
        print(f"  Note: {len(mb)} UTF-16/32 entries omitted by design (see above).")
    if other:
        print(f"  Skipped (no printable single-byte decodings): {', '.join(other)}")


if __name__ == "__main__":
    main()
