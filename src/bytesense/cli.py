"""Command-line detection with machine-readable output and meaningful exit codes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from .api import from_fp, from_path
from .version import __version__


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bytesense", description="Detect encodings and validate the complete input."
    )
    parser.add_argument(
        "files", nargs="+", metavar="FILE", help="File(s) to analyse; - reads binary stdin"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Include the explanation")
    parser.add_argument("-m", "--minimal", action="store_true", help="Print encoding name only")
    parser.add_argument("--language", action="store_true", help="Include a language estimate")
    parser.add_argument(
        "--sample-size",
        type=int,
        default=4096,
        help="Linguistic sample budget (default: 4096 bytes)",
    )
    parser.add_argument(
        "--min-confidence", type=float, default=0.0, help="Abstain below this evidence score (0–1)"
    )
    parser.add_argument("--version", action="version", version=f"bytesense {__version__}")
    args = parser.parse_args(argv)
    if args.sample_size < 64 or not 0 <= args.min_confidence <= 1:
        parser.error("sample-size must be at least 64; min-confidence must be between 0 and 1")
    results = []
    exit_code = 0
    for filepath in args.files:
        options = dict(
            include_language=args.language,
            sample_size=args.sample_size,
            min_confidence=args.min_confidence,
        )
        try:
            result = (
                from_fp(sys.stdin.buffer, **options)
                if filepath == "-"
                else from_path(filepath, **options)
            )
        except OSError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            exit_code = 1
            continue
        if result.encoding is None:
            exit_code = 1
        if args.minimal:
            print(result.encoding or "unknown")
            continue
        d = result.to_dict()
        d["path"] = "-" if filepath == "-" else str(Path(filepath).resolve())
        if not args.verbose:
            d.pop("why", None)
        results.append(d)
    if not args.minimal:
        output = results[0] if len(results) == 1 else results
        print(json.dumps(output, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
