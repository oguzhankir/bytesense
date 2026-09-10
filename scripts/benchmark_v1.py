"""Rotating-input latency, exact decode checks and allocation peaks. No timing gate."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import random
import statistics
import time
import tracemalloc
from pathlib import Path

from evaluate_corpus import engines


def samples() -> dict[str, list[bytes]]:
    templates = {
        "ascii_1mib": (b"The quick brown fox jumps over the lazy dog. ", 1_048_576, "ascii"),
        "utf8_1mib": ("Merhaba dünya! 日本語 Ελληνικά 🙂 ".encode(), 1_048_576, "utf_8"),
        "utf8_8kib": ("Café dünyası: 中文测试 🎉 ".encode(), 8192, "utf_8"),
        "turkish_cp1254_2100b": (
            ("İstanbul'da çalışan mühendisler için doğru metin çözümleme. " * 35).encode("cp1254"),
            2100,
            "cp1254",
        ),
        "japanese_eucjp_4kib": (
            "日本語の文字コードを正しく検出します。".encode("euc_jp"),
            4096,
            "euc_jp",
        ),
    }
    result = {}
    for name, (base, size, encoding) in templates.items():
        payloads = []
        for i in range(32):
            prefix = f"{i:06d} ".encode()
            body = (base * (size // len(base) + 1))[: size - len(prefix)]
            # Truncate only incomplete final code units, then restore exact byte length.
            body = body.decode(encoding, errors="ignore").encode(encoding)
            payloads.append(prefix + body + b" " * (size - len(prefix) - len(body)))
        assert all(len(d) == size for d in payloads)
        result[name] = payloads
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=64)
    parser.add_argument(
        "--engine",
        action="append",
        choices=["bytesense", "chardet", "charset-normalizer", "chardetng-py"],
    )
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error("--rounds must be positive")
    names = args.engine or ["bytesense", "chardet", "charset-normalizer", "chardetng-py"]
    detectors = engines(names)
    rows = []
    expected = {
        "ascii_1mib": "ascii",
        "utf8_1mib": "utf_8",
        "utf8_8kib": "utf_8",
        "turkish_cp1254_2100b": "cp1254",
        "japanese_eucjp_4kib": "euc_jp",
    }
    for case, payloads in samples().items():
        for mode in ["defaults", "full_validation"]:
            order = list(detectors)
            random.Random(42).shuffle(order)
            for name in order:
                fn = detectors[name]

                def call(
                    data: bytes, detect=fn, validate=(mode == "full_validation")
                ) -> str | None:
                    enc = detect(data)
                    if validate and enc:
                        data.decode(enc, errors="strict")
                    return enc

                for data in payloads[:2]:
                    call(data)
                times = []
                correct = 0
                for i in range(args.rounds):
                    data = payloads[i % len(payloads)]
                    start = time.perf_counter_ns()
                    enc = call(data)
                    times.append((time.perf_counter_ns() - start) / 1e6)
                    try:
                        correct += bool(enc and data.decode(enc) == data.decode(expected[case]))
                    except UnicodeError:
                        pass
                tracemalloc.start()
                try:
                    call(payloads[0])
                    _, peak = tracemalloc.get_traced_memory()
                finally:
                    tracemalloc.stop()
                rows.append(
                    {
                        "case": case,
                        "mode": mode,
                        "engine": name,
                        "bytes": len(payloads[0]),
                        "sha256": hashlib.sha256(b"".join(payloads)).hexdigest(),
                        "median_ms": statistics.median(times),
                        "p95_ms": sorted(times)[int(0.95 * (len(times) - 1))],
                        "python_peak_bytes": peak,
                        "correct": correct,
                        "rounds": args.rounds,
                    }
                )
                print(case, mode, name, round(statistics.median(times), 4), correct, flush=True)
    from bytesense._rust import is_rust_available

    result = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "bytesense_native": is_rust_available(),
        "versions": {name: importlib.metadata.version(name) for name in names},
        "notes": "32 rotating payloads; warm module/model; validation mode decodes every selected encoding, including bytesense (a conservative extra decode). tracemalloc excludes native allocations.",
        "results": rows,
    }
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
