"""Reproduce the fixed corpus split, train aggregate pairs, or evaluate exact Unicode.

Corpus files remain external and retain their publishers' copyrights. Training
emits aggregate character/pair statistics only, never source passages.
"""

from __future__ import annotations

import argparse
import codecs
import gzip
import hashlib
import importlib.metadata
import json
import math
import platform
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path

SOURCE = "https://github.com/chardet/test-data"
COMMIT = "b0c0d206913ba118ffea2f7d306883e7a4a76db7"
ROOT = Path(__file__).resolve().parents[1]


def inventory(corpus: Path) -> tuple[list[dict], list[dict]]:
    actual = subprocess.check_output(
        ["git", "-C", str(corpus), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual != COMMIT:
        raise ValueError(f"Corpus must be checked out at {COMMIT}, got {actual}")
    rows, excluded = [], []
    for path in sorted(corpus.glob("*/*")):
        if not path.is_file() or "-" not in path.parent.name:
            continue
        encoding, language = path.parent.name.rsplit("-", 1)
        if encoding == "None":
            encoding = None
        else:
            try:
                codecs.lookup(encoding)
            except LookupError:
                continue
        data = path.read_bytes()
        try:
            text = data.decode(encoding) if encoding else ""
        except UnicodeError as exc:
            excluded.append({"file": str(path.relative_to(corpus)), "reason": str(exc)})
            continue
        group = hashlib.sha256(text.encode()).hexdigest()
        rows.append(
            {
                "file": str(path.relative_to(corpus)),
                "encoding": encoding,
                "language": language,
                "sha256": hashlib.sha256(data).hexdigest(),
                "group": group,
                "split": "development" if int(group[:8], 16) % 3 == 0 else "holdout",
                "size": len(data),
            }
        )
    if len(rows) != 3137:
        raise ValueError(
            f"Incomplete corpus: expected 3137 decodable/binary cases, got {len(rows)}"
        )
    return rows, excluded


def train(corpus: Path, rows: list[dict], output: Path) -> None:
    letters, pairs = defaultdict(Counter), defaultdict(Counter)
    groups = set()
    for item in rows:
        if item["split"] != "development" or not item["encoding"] or item["group"] in groups:
            continue
        groups.add(item["group"])
        decoded = (corpus / item["file"]).read_bytes().decode(item["encoding"])
        text = "".join(c if c.isalpha() else " " for c in decoded.lower())[:100000]
        letters[item["language"]].update(text)
        pairs[item["language"]].update(zip(text, text[1:]))
    unigrams, bigrams = {}, {}
    for language, counts in letters.items():
        total = sum(counts.values())
        for char, count in counts.items():
            if char != " ":
                unigrams[char] = max(unigrams.get(char, 0), count / total)
        for (a, b), count in pairs[language].items():
            if (a, b) != (" ", " ") and count >= 2:
                bigrams[a + b] = max(bigrams.get(a + b, 0), count / counts[a])
    payload = {
        "source": SOURCE,
        "commit": COMMIT,
        "split": "int(SHA256(decoded Unicode)[:8], 16) mod 3 == 0",
        "groups": len(groups),
        "letters": "".join(sorted(unigrams)),
        "pairs": {
            p: round(1 + 0.03 * max(-15, math.log(v)), 6) for p, v in sorted(bigrams.items())
        },
    }
    output.write_bytes(
        gzip.compress(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(), mtime=0
        )
    )
    print(
        f"Trained {len(groups)} unique documents; {len(unigrams)} letters, {len(bigrams)} pairs -> {output}"
    )


def engines(names: list[str]) -> dict:
    result = {}
    for name in names:
        if name == "bytesense":
            from bytesense import from_bytes

            result[name] = lambda d: from_bytes(d).encoding
        elif name == "chardet":
            import chardet

            result[name] = lambda d: chardet.detect(d)["encoding"]
        elif name == "charset-normalizer":
            import charset_normalizer

            def cn(data: bytes) -> str | None:
                match = charset_normalizer.from_bytes(data).best()
                return match.encoding if match else None

            result[name] = cn
        elif name == "chardetng-py":
            import chardetng_py

            result[name] = lambda d: chardetng_py.detect(d, allow_utf8=True)
        else:
            raise ValueError(name)
    return result


def evaluate(
    corpus: Path, rows: list[dict], split: str, names: list[str], output: Path, excluded: list[dict]
) -> None:
    detectors = engines(names)
    selected = [r for r in rows if r["split"] == split]
    records = []
    for i, item in enumerate(selected):
        data = (corpus / item["file"]).read_bytes()
        reference = data.decode(item["encoding"]) if item["encoding"] else None
        record = dict(item, results={})
        for name, detect in detectors.items():
            start = time.perf_counter()
            try:
                encoding = detect(data)
                elapsed = time.perf_counter() - start
                try:
                    correct = data.decode(encoding) == reference if encoding else reference is None
                    valid = encoding is not None
                except (UnicodeError, LookupError):
                    correct = valid = False
                record["results"][name] = {
                    "encoding": encoding,
                    "correct": correct,
                    "valid": valid,
                    "seconds": elapsed,
                }
            except Exception as exc:
                record["results"][name] = {
                    "error": repr(exc),
                    "correct": False,
                    "valid": False,
                    "seconds": time.perf_counter() - start,
                }
        records.append(record)
        if i % 200 == 0:
            print(f"{i}/{len(selected)}", flush=True)
    summary = {
        name: {
            "correct": sum(r["results"][name]["correct"] for r in records),
            "total": len(records),
            "seconds": sum(r["results"][name]["seconds"] for r in records),
        }
        for name in detectors
    }
    payload = {
        "source": SOURCE,
        "commit": COMMIT,
        "split": split,
        "excluded": excluded,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "versions": {name: importlib.metadata.version(name) for name in names},
        "summary": summary,
        "records": records,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["train", "evaluate"])
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--split", choices=["development", "holdout"], default="holdout")
    parser.add_argument(
        "--engine",
        action="append",
        choices=["bytesense", "chardet", "charset-normalizer", "chardetng-py"],
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows, excluded = inventory(args.corpus)
    if args.action == "train":
        train(args.corpus, rows, args.output)
    else:
        evaluate(
            args.corpus,
            rows,
            args.split,
            args.engine or ["bytesense", "chardet", "charset-normalizer", "chardetng-py"],
            args.output,
            excluded,
        )


if __name__ == "__main__":
    main()
