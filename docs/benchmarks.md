# Benchmarks and model provenance

## Held-out accuracy

This review uses [chardet/test-data](https://github.com/chardet/test-data/tree/b0c0d206913ba118ffea2f7d306883e7a4a76db7), pinned at `b0c0d206913ba118ffea2f7d306883e7a4a76db7`. There are 3,137 decodable/reference-binary cases; one invalid reference file is excluded and recorded in the output JSON.

Split by `int(SHA256(reference Unicode)[:8], 16) % 3`: zero is development (1,059 files); the rest is holdout (2,078). Identical decoded documents remain together even when re-encoded. The model uses **541 unique development documents** and no holdout documents. This groups exact duplicates, not near-duplicates. The source is chardet's own test corpus, so these results are not an independent estimate of performance on all real-world data.

**Correct** means decoding the complete input with the returned codec produces exactly the reference Unicode, including BOM behavior. A binary reference requires abstention. An encoding that merely decodes without an exception is not counted correct.

| Detector | Exact Unicode matches | Accuracy |
|---|---:|---:|
| bytesense 1.0.0 | 1906 / 2078 | 91.72% |
| bytesense 0.1.2 | 883 / 2078 | 42.49% |
| chardet 7.6.0 | 2060 / 2078 | 99.13% |
| charset-normalizer 3.5.1 | 1679 / 2078 | 80.80% |
| chardetng-py 0.3.5 | 776 / 2078 | 37.34% |

Bytesense exceeds charset-normalizer on this corpus. Chardet remains more accurate. Chardetng is designed around browser encodings; this broader corpus includes UTF-7/16/32, EBCDIC and DOS code pages outside that focus. Do not read the table as a ranking for every application.

The corpus-level elapsed times are diagnostic single passes, not latency benchmarks. Use the rotating-input measurements below for latency.

## Latency

Linux x86-64, CPython 3.12.14, bytesense native scoring. Package versions match the accuracy table. Each workload has 32 rotating payloads, two warm-up calls and 64 timed calls. Models/modules are warm; these are **not cold-start measurements**. Every detector correctly decoded all 64 payloads in each reported workload.

Default API median latency:

| Workload | bytesense | chardet | charset-normalizer | chardetng-py |
|---|---:|---:|---:|---:|
| ascii_1mib | 0.159 ms | 0.688 ms | 0.118 ms | 6.764 ms |
| utf8_1mib | 1.234 ms | 0.804 ms | 1.497 ms | 35.680 ms |
| utf8_8kib | 0.034 ms | 0.182 ms | 0.225 ms | 0.400 ms |
| turkish_cp1254_2100b | 4.479 ms | 0.832 ms | 1.670 ms | 0.187 ms |
| japanese_eucjp_4kib | 10.474 ms | 0.970 ms | 0.861 ms | 0.565 ms |

Bytesense's default API validates the complete input. Competitors' defaults can use different sample budgets (chardet 7.6.0 caps examination by default). The script also reports **detector + one strict application decode** for every library, including bytesense, under `full_validation`. That intentionally includes an additional decode for bytesense; keep the two modes separate.

Legacy statistical scoring is still slower than these competitors on the Turkish and Japanese workloads. The new native scorer fuses Unicode classification and pair statistics, but considering many legacy candidates remains the main latency bottleneck. UTF-8 fast paths bypass the statistical model entirely. ASCII performance depends on size and detector; there is no universal speedup claim.

Allocation peaks use `tracemalloc` and exclude native allocations. Stream spooling is verified separately with an 8 MB single-chunk regression: feeding a large chunk must not first duplicate that chunk in the in-memory spool.

## Reproduce

Use Python 3.12 for the exact training reproduction. Install comparison packages only in the benchmark environment:

```bash
pip install -e '.[dev]' chardet==7.6.0 charset-normalizer==3.5.1 chardetng-py==0.3.5
git clone https://github.com/chardet/test-data ../test-data
git -C ../test-data checkout b0c0d206913ba118ffea2f7d306883e7a4a76db7
python scripts/evaluate_corpus.py evaluate ../test-data --split holdout --output holdout.json
python scripts/benchmark_v1.py --output latency.json
BYTESENSE_PURE_PYTHON=1 python scripts/evaluate_corpus.py evaluate ../test-data \
  --split holdout --engine bytesense --output pure-holdout.json
```

Choose a pure or native build explicitly before comparing it. JSON records package versions, interpreter/platform, case hashes, reference encodings, predictions, decode validity and timing. Holdout evaluation does not update the model. Keep evaluation output outside the source package; do not silently reduce the corpus when files are missing.

## Model generation

```bash
python scripts/evaluate_corpus.py train ../test-data --output regenerated-language.json.gz
```

The generator selects development groups only, counts at most 100,000 normalized characters per document, aggregates per-language letter/pair frequencies, requires two observations for a pair, and merges conditional pair support across languages. Runtime scoring combines letter coverage and pair support, emphasizes non-ASCII evidence, and penalizes control/symbol noise. The resulting score is not a calibrated probability.

The compressed artifact contains individual characters, character pairs and numeric weights—no source passages. Upstream documents retain their respective publishers' copyrights; see the upstream [catalog](https://github.com/chardet/test-data/blob/b0c0d206913ba118ffea2f7d306883e7a4a76db7/CATALOG.md) for provenance. Dataset text is not redistributed with the package. Development-source statistics are distinct from chardet's implementation and model code.

Model SHA-256: `2211f5c6c167afe9ce060e28a2fc08670ff9b7839f3a7af4d2085d3a0ebc420a`.

## Regression suites and release gates

```bash
python scripts/fetch_cn_benchmark_samples.py
pytest tests benchmarks/test_bench_detection.py benchmarks/test_hard_scenarios.py --benchmark-disable
```

The 18 charset-normalizer reference files are pinned to commit `b130b7dae36658c7ba67381fe06a62c7c7c03894`, with per-file SHA-256 and size in `benchmarks/cn_official_manifest.json`. Missing or changed files fail collection. The 1 MiB fixture is actually 1,048,576 bytes and benchmark IDs follow the dataset order.

The existing synthetic/curated suites are regression gates, not independent accuracy evidence. CI separately exercises installed pure and native artifacts, strict full-input validation, chunk boundaries, overflow-safe histograms, Unicode parity, thread determinism and CLI outcomes. Timings are reports; a noisy speed assertion cannot hide a failed correctness gate.
