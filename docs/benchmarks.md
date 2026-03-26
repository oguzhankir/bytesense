# Benchmarks

Accuracy and speed checks live under `benchmarks/`. For a **human-readable speed table** (bytesense vs chardet, representative µs means) and how to interpret workload-dependent cases (e.g. large UTF-8 buffers), see the **Speed (pytest-benchmark)** section in the [project README](../README.md#speed-pytest-benchmark).

Run accuracy gate (must pass):

```bash
pytest benchmarks/test_bench_detection.py -k accuracy -v
```

Run pytest-benchmark comparisons:

```bash
# Do not use -k bench_ — it matches the module name test_bench_detection.py and runs every test.
pytest benchmarks/test_bench_detection.py \
  -k "test_bench_bytesense_fast_path or test_bench_cn_fast_path or test_bench_bytesense_full or test_bench_cn_full or test_bench_chardet_full" \
  --benchmark-sort=mean -v \
  --benchmark-json=benchmarks/results/output.json
```

Results JSON is gitignored under `benchmarks/results/`.
