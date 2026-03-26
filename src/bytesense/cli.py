from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from .api import from_path
from .version import __version__


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="bytesense",
        description="Fast charset/encoding detection. Zero dependencies.",
    )
    parser.add_argument("files", nargs="+", metavar="FILE", help="File(s) to analyse")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-m", "--minimal", action="store_true", help="Print encoding name only")
    parser.add_argument("--version", action="version", version=f"bytesense {__version__}")

    args = parser.parse_args(argv)

    results = []
    for filepath in args.files:
        try:
            result = from_path(filepath)
        except OSError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            continue

        if args.minimal:
            print(result.encoding or "unknown")
            continue

        d = result.to_dict()
        d["path"] = str(Path(filepath).resolve())
        if not args.verbose:
            d.pop("why", None)
            # confidence_interval kept for default JSON (matches README / API transparency)
        results.append(d)

    if not args.minimal:
        output = results[0] if len(results) == 1 else results
        print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
