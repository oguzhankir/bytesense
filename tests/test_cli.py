from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_cli_version() -> None:
    r = subprocess.run(
        [sys.executable, "-m", "bytesense.cli", "--version"],
        capture_output=True,
        text=True,
        check=False,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert r.returncode == 0
    assert "bytesense" in r.stdout


def test_cli_minimal_encoding() -> None:
    import tempfile

    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
        f.write(b"Hello world pure ascii test.")
        path = f.name
    try:
        r = subprocess.run(
            [sys.executable, "-m", "bytesense.cli", "-m", path],
            capture_output=True,
            text=True,
            check=False,
        )
        assert r.returncode == 0
        out = r.stdout.strip()
        assert out in ("ascii", "utf_8")
    finally:
        Path(path).unlink(missing_ok=True)


def test_cli_verbose_includes_why() -> None:
    import json
    import tempfile

    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
        f.write("Bonjour le monde".encode("utf-8"))
        path = f.name
    try:
        r = subprocess.run(
            [sys.executable, "-m", "bytesense.cli", "-v", path],
            capture_output=True,
            text=True,
            check=False,
        )
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert "why" in data
    finally:
        Path(path).unlink(missing_ok=True)


def test_cli_missing_file_prints_error() -> None:
    r = subprocess.run(
        [sys.executable, "-m", "bytesense.cli", "/nonexistent/bytesense-cli-404.txt"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0
    assert "Error" in r.stderr
