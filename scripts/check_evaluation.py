"""Enforce frozen accuracy floors and native/Python parity; never gate timing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from evaluate_corpus import COMMIT as CORPUS_COMMIT
from evaluate_udhr import COMMIT as TRANSFER_COMMIT

root = Path(sys.argv[1])
native = json.loads((root / "holdout-native.json").read_text(encoding="utf-8"))
pure = json.loads((root / "holdout-pure.json").read_text(encoding="utf-8"))
transfer = json.loads((root / "transfer.json").read_text(encoding="utf-8"))

assert native["commit"] == pure["commit"] == CORPUS_COMMIT
assert native["split"] == pure["split"] == "holdout"
assert native["versions"]["bytesense"] == pure["versions"]["bytesense"]
for report in (native, pure):
    summary = report["summary"]["bytesense"]
    assert summary["total"] == 2078
    assert summary["correct"] >= 1907, summary
    assert not any("error" in r["results"]["bytesense"] for r in report["records"])

assert len(native["records"]) == len(pure["records"]) == 2078
for a, b in zip(native["records"], pure["records"]):
    assert (a["file"], a["sha256"]) == (b["file"], b["sha256"])
    assert a["results"]["bytesense"]["encoding"] == b["results"]["bytesense"]["encoding"], a["file"]
    assert a["results"]["bytesense"]["correct"] == b["results"]["bytesense"]["correct"]

assert transfer["commit"] == TRANSFER_COMMIT
assert transfer["documents"] == 28
assert len(transfer["records"]) == 432
assert len(transfer["excluded"]) == 27
for family, total, minimum in (("all", 432, 394), ("legacy", 180, 146), ("unicode", 252, 248)):
    summary = transfer["summary"]["bytesense"][family]
    assert summary["total"] == total
    assert summary["correct"] >= minimum, (family, summary)
assert not any("error" in r["results"]["bytesense"] for r in transfer["records"])
print("Accuracy floors and all 2,078 native/Python predictions verified.")
