"""
Download charset-normalizer's official data/ samples for apples-to-apples benchmarks.

Upstream: https://github.com/jawah/charset_normalizer (data/ + tests/test_full_detection.py)

Run (use the same venv as the project — avoids macOS Python SSL issues):

    .venv/bin/python scripts/fetch_cn_benchmark_samples.py

If HTTPS still fails, install certs:  pip install certifi
Or (last resort):  python scripts/fetch_cn_benchmark_samples.py --insecure
"""
from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "benchmarks" / "cn_official_manifest.json"
OUT_DIR = ROOT / "benchmarks" / "data" / "cn_official"

USER_AGENT = "bytesense-benchmark-fetch/1.0 (+https://github.com/oguzhankir/bytesense)"


def _ssl_context(insecure: bool) -> ssl.SSLContext:
    if insecure:
        print("WARNING: using unverified HTTPS (not for production).", file=sys.stderr)
        return ssl._create_unverified_context()
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch charset-normalizer data/ samples for benchmarks.")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification (only if certifi / system CA fails).",
    )
    args = parser.parse_args()

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    base = data["base_url"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ctx = _ssl_context(args.insecure)

    for entry in data["files"]:
        name = entry["file"]
        url = base + name
        dest = OUT_DIR / name
        print(f"  fetching {name} ...")
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                dest.write_bytes(resp.read())
        except urllib.error.URLError as e:
            print(
                "\nHTTPS fetch failed. Try one of:\n"
                "  • Use project venv:  .venv/bin/python scripts/fetch_cn_benchmark_samples.py\n"
                "  • Install CA bundle: pip install certifi\n"
                "  • macOS Python.org: run /Applications/Python\\ 3.*/Install\\ Certificates.command\n"
                "  • Last resort:       python scripts/fetch_cn_benchmark_samples.py --insecure\n",
                file=sys.stderr,
            )
            raise SystemExit(1) from e

    (OUT_DIR / "MANIFEST.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"\nOK: {len(data['files'])} files -> {OUT_DIR}")


if __name__ == "__main__":
    main()
