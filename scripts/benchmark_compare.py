"""Compare installed baseline/candidate packages in paired, isolated processes."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

from benchmark_v1 import samples
from evaluate_corpus import engines

EXPECTED = {
    "ascii_1mib": "ascii",
    "utf8_1mib": "utf_8",
    "utf8_8kib": "utf_8",
    "utf8_64kib": "utf_8",
    "utf8_8mib": "utf_8",
    "turkish_cp1254_2100b": "cp1254",
    "japanese_eucjp_4kib": "euc_jp",
}
COMPETITORS = ["chardet", "charset-normalizer", "chardetng-py"]


def worker(variant: str, competitors: list[str]) -> None:
    import bytesense.api
    from bytesense._rust import is_rust_available

    names = ["bytesense"] + (competitors if variant == "candidate" else [])
    detectors = engines(names)
    payloads = samples()
    for inputs in payloads.values():
        for data in inputs[:4]:
            for detector in detectors.values():
                detector(data)
    metadata = {
        "ready": True,
        "native": is_rust_available(),
        "python": platform.python_version(),
        "versions": {name: importlib.metadata.version(name) for name in names},
        "api_sha256": hashlib.sha256(Path(bytesense.api.__file__).read_bytes()).hexdigest(),
    }
    if is_rust_available():
        import bytesense._rust_core

        metadata["native_extension_sha256"] = hashlib.sha256(
            Path(bytesense._rust_core.__file__).read_bytes()
        ).hexdigest()
    print(json.dumps(metadata), flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        case, engine = request["case"], request["engine"]
        data = payloads[case][request["index"]]

        def call(
            payload: bytes = data,
            detect=detectors[engine],
            validate: bool = request["mode"] == "full_validation",
        ) -> str | None:
            encoding = detect(payload)
            if validate and encoding:
                payload.decode(encoding, errors="strict")
            return encoding

        if request.get("allocation"):
            tracemalloc.start()
            try:
                call()
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            result = {"peak_bytes": peak}
        else:
            start = time.perf_counter_ns()
            encoding = call()
            elapsed = (time.perf_counter_ns() - start) / 1e6
            try:
                correct = bool(encoding and data.decode(encoding) == data.decode(EXPECTED[case]))
            except UnicodeError:
                correct = False
            result = {"ms": elapsed, "correct": correct}
        print(json.dumps(result), flush=True)


class Worker:
    def __init__(self, python: Path, variant: str, competitors: list[str]):
        self.variant = variant
        environment = dict(os.environ)
        # Each supplied interpreter must resolve its own installed package.
        environment.pop("PYTHONPATH", None)
        # Keep virtualenv interpreter symlinks intact: resolving one loses its
        # environment and can import a different installed package.
        arguments = [str(python.absolute()), "-u", str(Path(__file__).resolve()), "--worker", variant]
        for competitor in competitors:
            arguments.extend(["--engine", competitor])
        self.process = subprocess.Popen(
            arguments,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            env=environment,
        )

    def read(self) -> dict[str, Any]:
        assert self.process.stdout is not None
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(
                f"{self.variant} worker closed its output; inspect its stderr above "
                f"(exit status: {self.process.poll()})."
            )
        return json.loads(line)

    def request(self, **payload: Any) -> dict[str, Any]:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()
        return self.read()

    def close(self) -> None:
        if self.process.stdin is not None:
            with contextlib.suppress(BrokenPipeError):
                self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if self.process.stdout is not None:
            self.process.stdout.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-python", type=Path)
    parser.add_argument("--candidate-python", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--rounds", type=int, default=128)
    parser.add_argument("--engine", action="append", choices=COMPETITORS)
    parser.add_argument("--worker", choices=["baseline", "candidate"], help=argparse.SUPPRESS)
    args = parser.parse_args()
    competitors = list(dict.fromkeys(args.engine or COMPETITORS))
    if args.worker:
        worker(args.worker, competitors)
        return
    if not args.baseline_python or not args.candidate_python or not args.output:
        parser.error("--baseline-python, --candidate-python and --output are required")
    if args.rounds < 1:
        parser.error("--rounds must be positive")
    processes: dict[str, Worker] = {}
    metadata = {}
    try:
        for variant, python in [
            ("baseline", args.baseline_python), ("candidate", args.candidate_python)
        ]:
            processes[variant] = Worker(python, variant, competitors)
            metadata[variant] = processes[variant].read()
            if not metadata[variant].get("ready"):
                raise RuntimeError(f"{variant} worker did not initialize")
        print(json.dumps(metadata), flush=True)
        detectors = [("baseline", "bytesense"), ("candidate", "bytesense")]
        detectors += [("candidate", name) for name in competitors]
        rng = random.Random(20260919)
        results = []
        for case, payloads in samples().items():
            for mode in ["defaults", "full_validation"]:
                times: dict[tuple[str, str], list[float]] = {key: [] for key in detectors}
                correct = dict.fromkeys(detectors, 0)
                for i in range(args.rounds):
                    order = list(detectors)
                    rng.shuffle(order)
                    for variant, engine in order:
                        result = processes[variant].request(
                            case=case, engine=engine, index=i % len(payloads), mode=mode
                        )
                        times[(variant, engine)].append(result["ms"])
                        correct[(variant, engine)] += result["correct"]
                for variant, engine in detectors:
                    durations = times[(variant, engine)]
                    allocation = processes[variant].request(
                        case=case, engine=engine, index=0, mode=mode, allocation=True
                    )
                    result = {
                        "case": case,
                        "mode": mode,
                        "variant": variant,
                        "engine": engine,
                        "bytes": len(payloads[0]),
                        "sha256": hashlib.sha256(b"".join(payloads)).hexdigest(),
                        "median_ms": statistics.median(durations),
                        "p95_ms": sorted(durations)[int(0.95 * (args.rounds - 1))],
                        "peak_bytes": allocation["peak_bytes"],
                        "correct": correct[(variant, engine)],
                        "rounds": args.rounds,
                    }
                    results.append(result)
                    print(json.dumps(result), flush=True)
                args.output.write_text(
                    json.dumps(
                        {
                            "python": platform.python_version(),
                            "platform": platform.platform(),
                            "metadata": metadata,
                            "notes": "32 rotating payloads; four warmups per case; persistent isolated "
                            "baseline/candidate processes; seed 20260919 randomized engine order each "
                            "round; IPC excluded; tracemalloc excludes native allocations.",
                            "results": results,
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
    finally:
        for process in processes.values():
            process.close()


if __name__ == "__main__":
    main()
