"""
Stress comparison: bytesense vs charset-normalizer vs chardet on **paragraph-sized**
ambiguous samples (see `hard_scenarios.py`).

Run (table + optional failure lists):

    PYTHONPATH=src pytest benchmarks/test_hard_scenarios.py -v -s

chardet is historically weak on very short inputs and UTF-16 without BOM; the
table is informational, not a release gate.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Tuple

import pytest

from benchmarks.hard_scenarios import HARD_SCENARIOS
from benchmarks.test_bench_detection import _encodings_match, _functional_text_match


def _libraries() -> Dict[str, Callable[[bytes], str | None]]:
    libs: Dict[str, Callable[[bytes], str | None]] = {}

    from bytesense import from_bytes as bs_fb

    def bs(data: bytes) -> str | None:
        return bs_fb(data).encoding

    libs["bytesense"] = bs

    try:
        from charset_normalizer import from_bytes as cn_fb

        def cn(data: bytes) -> str | None:
            r = cn_fb(data).best()
            return r.encoding if r else None

        libs["charset-normalizer"] = cn
    except ImportError:
        pass

    try:
        import chardet as cd

        def chd(data: bytes) -> str | None:
            return cd.detect(data).get("encoding")

        libs["chardet"] = chd
    except ImportError:
        pass

    return libs


def _score(
    fn: Callable[[bytes], str | None],
    mode: str,
) -> Tuple[int, int, List[str]]:
    bad: List[str] = []
    ok = 0
    for name, data, expected in HARD_SCENARIOS:
        det = fn(data)
        if mode == "strict":
            good = _encodings_match(det, expected)
        else:
            good = _functional_text_match(data, det, expected)
        if good:
            ok += 1
        else:
            bad.append(f"{name}: got {det!r}, want {expected!r}")
    n = len(HARD_SCENARIOS)
    return ok, n, bad


def test_hard_scenario_three_way_comparison() -> None:
    """Print strict + functional accuracy on the hard stress corpus."""
    libs = _libraries()
    if not libs:
        pytest.skip("bytesense unavailable")

    print("\n")
    print("=" * 72)
    print(
        "HARD SCENARIOS — paragraph-sized (~400 B+), ambiguous SBCS / CJK / UTF-16 / ISO-2022 "
        "(see hard_scenarios.py)"
    )
    print(f"Samples: {len(HARD_SCENARIOS)}")
    print("=" * 72)

    for mode, label in (
        ("strict", "Strict codec name match (aliases via codecs.lookup)"),
        ("functional", "Functional match (same Unicode as reference encoding)"),
    ):
        print(f"\n{label}")
        print(f"{'Library':<22} {'Correct':>8} {'Total':>8} {'Accuracy':>10}")
        print("-" * 72)
        for lib_name, fn in libs.items():
            ok, n, _ = _score(fn, mode)
            acc = ok / n if n else 0.0
            print(f"{lib_name:<22} {ok:>8} {n:>8} {acc:>9.1%}")
        print("-" * 72)

    print("\nPer-library functional misses (first 12 each):")
    for lib_name, fn in libs.items():
        _, _, bad = _score(fn, "functional")
        if not bad:
            print(f"  {lib_name}: (none)")
        else:
            print(f"  {lib_name}:")
            for line in bad[:12]:
                print(f"    {line}")
            if len(bad) > 12:
                print(f"    ... +{len(bad) - 12} more")
    print("=" * 72 + "\n")

    # Sanity: corpus must be non-empty and bytesense must load
    assert len(HARD_SCENARIOS) >= 12
