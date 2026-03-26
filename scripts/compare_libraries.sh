#!/usr/bin/env bash
# bytesense vs charset-normalizer vs chardet — accuracy tables only (paste-friendly).
#
# Usage (repo root, dev deps installed):
#   pip install -e ".[dev]"
#   ./scripts/compare_libraries.sh
#
# Skip paragraph-sized hard stress (faster):
#   ./scripts/compare_libraries.sh --no-hard
#
# Skip downloading charset-normalizer official samples (synthetic corpus only):
#   ./scripts/compare_libraries.sh --no-fetch
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=src

RUN_HARD=1
FETCH=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-hard)  RUN_HARD=0 ;;
    --no-fetch) FETCH=0    ;;
    *)
      echo "usage: $0 [--no-hard] [--no-fetch]" >&2
      exit 1
      ;;
  esac
  shift
done

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="$(command -v python3 || true)"
fi
if [[ -z "$PY" || ! -x "$PY" ]]; then
  echo "error: need .venv/bin/python or python3" >&2
  exit 1
fi

banner() {
  printf '\n'
  printf '=%.0s' {1..72}
  printf '\n'
  printf ' %s\n' "$1"
  printf '=%.0s' {1..72}
  printf '\n\n'
}

banner "bytesense — library comparison ($(date '+%Y-%m-%d %H:%M:%S %Z'))"
echo "python: $($PY --version)"
echo "cwd: $ROOT"
echo ""

"$PY" scripts/build_fingerprints.py

if [[ "$FETCH" -eq 1 ]]; then
  banner "Fetch charset-normalizer official samples (benchmarks/data/cn_official/)"
  if ! "$PY" scripts/fetch_cn_benchmark_samples.py; then
    echo "warning: fetch failed — continuing with synthetic samples only." >&2
  fi
else
  echo "(skipped: --no-fetch)"
  echo ""
fi

banner "Accuracy: bytesense vs charset-normalizer vs chardet (pytest -k accuracy -s)"
"$PY" -m pytest benchmarks/test_bench_detection.py -k accuracy -v -s

if [[ "$RUN_HARD" -eq 1 ]]; then
  banner "Hard stress corpus (paragraph-sized, three-way table)"
  "$PY" -m pytest benchmarks/test_hard_scenarios.py -v -s
else
  echo "(skipped: --no-hard)"
fi

banner "done — copy the Strict / Functional tables above for README or release notes"
