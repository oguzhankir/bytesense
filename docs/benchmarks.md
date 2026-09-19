# Benchmarks and model provenance

## Held-out accuracy

This review uses [chardet/test-data](https://github.com/chardet/test-data/tree/b0c0d206913ba118ffea2f7d306883e7a4a76db7), pinned at `b0c0d206913ba118ffea2f7d306883e7a4a76db7`. There are 3,137 decodable/reference-binary cases; one invalid reference file is excluded and recorded in the output JSON.

Split by `int(SHA256(reference Unicode)[:8], 16) % 3`: zero is development (1,059 files); the rest is holdout (2,078). Identical decoded documents remain together even when re-encoded. The model uses **541 unique development documents** and no holdout documents. This groups exact duplicates, not near-duplicates. The source is chardet's own test corpus, so these results are not an independent estimate of performance on all real-world data.

**Correct** means decoding the complete input with the returned codec produces exactly the reference Unicode, including BOM behavior. A binary reference requires abstention. An encoding that merely decodes without an exception is not counted correct.

| Detector | Exact Unicode matches | Accuracy |
|---|---:|---:|
| bytesense 1.2.0 | 1907 / 2078 | 91.77% |
| bytesense 1.1.0 | 1907 / 2078 | 91.77% |
| bytesense 1.0.0 | 1906 / 2078 | 91.72% |
| bytesense 0.1.2 | 883 / 2078 | 42.49% |
| chardet 7.6.0 | 2060 / 2078 | 99.13% |
| charset-normalizer 3.5.1 | 1679 / 2078 | 80.80% |
| chardetng-py 0.3.5 | 776 / 2078 | 37.34% |

Bytesense exceeds charset-normalizer on this corpus. Chardet remains more accurate. Chardetng is designed around browser encodings; this broader corpus includes UTF-7/16/32, EBCDIC and DOS code pages outside that focus. Do not read the table as a ranking for every application.

The corpus-level elapsed times are diagnostic single passes, not latency benchmarks. Use the rotating-input measurements below for latency.

The v1.1 model weights are unchanged. Runtime changes were selected on development data and contract regressions, not by tuning on this holdout. Native and Python implementations selected identical encodings for all 2,078 files. The net gain here is **one file**, not evidence of a large general-accuracy improvement.

## New transfer check

The [UDHR in XML repository](https://github.com/unicode-org/udhr/tree/588b3f4b2d0467aff54842a4b926551b69d5a66a) is pinned at `588b3f4b2d0467aff54842a4b926551b69d5a66a`. The script fixes 28 language documents and generates 64-character, 512-character and full-document variants in UTF-8, BOM-less UTF-16 and a declared set of language-relevant legacy codecs.

Fixture preparation applies NFC, collapses whitespace, and maps six typographic quote/dash characters to ASCII. Encoding is strict: **432 cases** round-trip exactly; **27 unrepresentable combinations** are explicitly recorded as exclusions. The detector must reproduce the complete prepared reference Unicode. No source passages are included in reports or package artifacts.

| Detector | All cases | Legacy cases | Unicode cases |
|---|---:|---:|---:|
| bytesense 1.2.0 | 394 / 432 | 146 / 180 | 248 / 252 |
| bytesense 1.1.0 | 394 / 432 | 146 / 180 | 248 / 252 |
| bytesense 1.0.0 | 374 / 432 | 142 / 180 | 232 / 252 |
| chardet 7.6.0 | 422 / 432 | 170 / 180 | 252 / 252 |
| charset-normalizer 3.5.1 | 381 / 432 | 129 / 180 | 252 / 252 |
| chardetng-py 0.3.5 | 213 / 432 | 129 / 180 | 84 / 252 |

This set was not used for model training or runtime parameter selection. It is a **transfer check, not a representative benchmark of all applications**: the files are correlated re-encodings and length variants of translations of one document. Chardetng's Unicode count reflects its browser-encoding scope, not support for BOM-less UTF-16. The corpus is neither fully neutral nor a source of independent statistical trials.

V1.1 gains 20 exact recoveries over v1.0 on this check. Chardet remains more accurate; bytesense still has Unicode and legacy errors. Do not claim universal superiority from either table.

V1.2 changes validation cost, not the statistical model or ranking. Every native/Python prediction on the 2,078-file holdout remains identical to v1.1, and the 432-case transfer results are unchanged.

## Latency

Linux x86-64 (Intel Xeon Platinum 8370C), CPython 3.12.14, native bytesense. Competitor versions match the accuracy table. V1.1 and the v1.2 implementation run in separate persistent processes; 128 rounds use the same 32 rotating payloads, four warm-ups per workload, and seeded randomized engine order on each round. Timers exclude inter-process communication. These are warm measurements on one host, not cold-start or cross-platform guarantees. Every engine exactly decoded all 128 payloads in every workload/mode.

Default API median latency:

| Workload | bytesense 1.2 | bytesense 1.1 | chardet | charset-normalizer | chardetng-py |
|---|---:|---:|---:|---:|---:|
| ascii_1mib | 0.239 ms | 0.414 ms | 1.275 ms | 0.281 ms | 9.019 ms |
| utf8_8kib | 0.078 ms | 0.086 ms | 0.402 ms | 0.519 ms | 0.728 ms |
| utf8_64kib | 0.092 ms | 0.179 ms | 0.768 ms | 0.601 ms | 4.024 ms |
| utf8_1mib | 0.294 ms | 1.564 ms | 1.697 ms | 1.927 ms | 63.316 ms |
| utf8_8mib | 2.329 ms | 11.886 ms | 1.793 ms | 94.523 ms | 508.226 ms |
| turkish_cp1254_2100b | 2.731 ms | 2.891 ms | 1.972 ms | 3.259 ms | 0.360 ms |
| japanese_eucjp_4kib | 6.366 ms | 6.216 ms | 2.182 ms | 1.806 ms | 1.023 ms |

The measured 1 MiB and 8 MiB UTF-8 detection calls are **5.3× and 5.1× faster than v1.1**. Native `from_bytes(bytes)` validates UTF-8/UTF-8-SIG directly with pinned `simdutf8` 0.1.5: runtime AVX2/SSE4.2 dispatch on x86, target-supported NEON on ARM64, and scalar fallbacks. Its [compatibility validator](https://docs.rs/simdutf8/0.1.5/simdutf8/compat/fn.from_utf8.html) preserves strict rejection, early failure and first-error offsets. Other CPU architectures were not timed locally. Small-input gains are modest; legacy detection is essentially unchanged and competitors still win there.

Bytesense validates every byte. Chardet 7.6.0 defaults to a 200,000-byte examination cap, so its lower default latency on the 8 MiB workload does not represent equivalent validation work. Charset-normalizer fully decodes UTF-8; its scoring sample budget does not limit that decoding. Chardetng is called with `allow_utf8=True` and consumes the full input.

The `full_validation` mode adds one strict application decode to **every** detector, including bytesense. For the 1 MiB UTF-8 workload:

| Workflow | bytesense 1.2 | bytesense 1.1 | chardet | charset-normalizer | chardetng-py |
|---|---:|---:|---:|---:|---:|
| Detection + strict decode | 1.569 ms | 2.795 ms | 2.932 ms | 3.160 ms | 62.896 ms |

This application workflow improves by **1.8×**, rather than the 5.3× detector-only gain. Keep these modes separate.

On the 1 MiB UTF-8 detection call, peak traced Python allocations decrease from **6,291,602 to 5,988 bytes**. `tracemalloc` excludes native allocations and pre-existing input buffers; this is not RSS or total application memory. Decoding afterward allocates Unicode as usual, and `bytearray` inputs still incur the documented conversion to immutable bytes. The pure-Python UTF-8 path now uses 64 KiB decode blocks above 64 KiB; v1.1 already used blocks above 1 MiB. `from_path`, `from_fp` and stream finalization retain their existing incremental validation path.

The paired comparator records package versions, backend availability, source/extension hashes, payload hashes, exact-decode counts, median/p95 latency and traced Python allocations. The single-environment benchmark remains available for CI reports. Timing is never a correctness gate.

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
git clone https://github.com/unicode-org/udhr ../udhr
git -C ../udhr checkout 588b3f4b2d0467aff54842a4b926551b69d5a66a
python scripts/evaluate_udhr.py ../udhr --output transfer.json
```

Choose a pure or native build explicitly before comparing it. JSON records package versions, interpreter/platform, case hashes, reference encodings, predictions, decode validity and timing. Holdout evaluation does not update the model. Keep evaluation output outside the source package; do not silently reduce the corpus when files are missing.

For the paired comparison, install v1.1 and this checkout in separate environments with the same Python version and native backend. The v1.1 baseline is commit `5c6677096b4ce571509992980e28148b0a702fd3`; comparison dependencies belong in the candidate environment. Then run:

```bash
python scripts/benchmark_compare.py \
  --baseline-python /path/to/v1.1/bin/python \
  --candidate-python /path/to/v1.2/bin/python \
  --rounds 128 --output paired-latency.json
```

Check the recorded backend flags before comparing native and pure builds. The UTF-8 change also passed strict-decoder property tests, SIMD/block-boundary regressions, and an independent exhaustive/structured check of 1,272,596 byte inputs with identical validity and first-error offsets. That checks implementation equivalence, not language-detection accuracy.

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

The CI evaluation job also fetches both exact corpus commits, evaluates installed packages, enforces the v1.1 accuracy floors and checks every held-out native/Python prediction. Its `evaluation-results` artifact contains the raw accuracy and latency JSON; failures do not silently remove input cases. These published sets are regression checks for subsequent work; freeze a new validation set before choosing new ranking/model parameters.
