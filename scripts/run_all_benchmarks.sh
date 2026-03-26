#!/usr/bin/env bash
# Run all benchmark-related pytest targets and print everything to stdout
# (accuracy tables, hard scenarios, optional speed benches) — paste-friendly.
#
# Usage:
#   ./scripts/run_all_benchmarks.sh              # accuracy + hard + speed benches
#   ./scripts/run_all_benchmarks.sh --no-speed   # skip pytest-benchmark (faster)
#
# From repo root with dev deps installed:
#   pip install -e ".[dev]"
#   python scripts/fetch_cn_benchmark_samples.py   # for full CN accuracy
#   ./scripts/run_all_benchmarks.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=src

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="$(command -v python3 || true)"
fi
if [[ -z "$PY" || ! -x "$PY" ]]; then
  echo "error: no Python found (expected .venv/bin/python or python3)" >&2
  exit 1
fi

RUN_SPEED=1
if [[ "${1:-}" == "--no-speed" ]]; then
  RUN_SPEED=0
fi

banner() {
  printf '\n'
  printf '=%.0s' {1..72}
  printf '\n'
  printf ' %s\n' "$1"
  printf '=%.0s' {1..72}
  printf '\n\n'
}

banner "bytesense — full benchmark report ($(date '+%Y-%m-%d %H:%M:%S %Z'))"
echo "python: $($PY --version)"
echo "cwd: $ROOT"
echo "PYTHONPATH=$PYTHONPATH"
echo ""

banner "1/3 — Accuracy gates + three-way summary (test_bench_detection, -k accuracy)"
"$PY" -m pytest benchmarks/test_bench_detection.py -k accuracy -v -s

banner "2/3 — Hard stress corpus (test_hard_scenarios)"
"$PY" -m pytest benchmarks/test_hard_scenarios.py -v -s

banner "2.5/3 — Repair engine quick sanity"
"$PY" -m pytest tests/test_repair.py -v --tb=short

# Note: -k bench_ matches the *module* name test_bench_detection.py — do not use it.
BENCH_KW="test_bench_bytesense_fast_path or test_bench_cn_fast_path or test_bench_bytesense_full or test_bench_cn_full or test_bench_chardet_full"

if [[ "$RUN_SPEED" -eq 1 ]]; then
  banner "3/3 — Speed benchmarks (pytest-benchmark, timing-only tests)"
  "$PY" -m pytest benchmarks/test_bench_detection.py -k "$BENCH_KW" --benchmark-sort=mean -v
else
  banner "3/3 — Skipped (--no-speed)"
  echo "Re-run without --no-speed to include timing benchmarks."
fi

banner "done"
echo "Copy everything above this line to share results."
