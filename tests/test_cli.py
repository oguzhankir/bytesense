from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from bytesense.cli import main


def test_main_version_system_exit() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0


def test_main_minimal_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
        f.write(b"Hello world pure ascii test.")
        path = f.name
    try:
        main(["-m", path])
    finally:
        Path(path).unlink(missing_ok=True)
    out = capsys.readouterr().out.strip()
    assert out in ("ascii", "utf_8")


def test_main_verbose_includes_why_in_process(capsys: pytest.CaptureFixture[str]) -> None:
    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
        f.write("Bonjour le monde".encode("utf-8"))
        path = f.name
    try:
        main(["-v", path])
    finally:
        Path(path).unlink(missing_ok=True)
    data = json.loads(capsys.readouterr().out)
    assert "why" in data


def test_main_default_json_omits_why(capsys: pytest.CaptureFixture[str]) -> None:
    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
        f.write(b"hello")
        path = f.name
    try:
        main([path])
    finally:
        Path(path).unlink(missing_ok=True)
    data = json.loads(capsys.readouterr().out)
    assert "path" in data
    assert "why" not in data


def test_main_two_files_outputs_list(capsys: pytest.CaptureFixture[str]) -> None:
    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix="a.txt") as fa:
        fa.write(b"x")
        pa = fa.name
    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix="b.txt") as fb:
        fb.write(b"y")
        pb = fb.name
    try:
        main([pa, pb])
    finally:
        Path(pa).unlink(missing_ok=True)
        Path(pb).unlink(missing_ok=True)
    data = json.loads(capsys.readouterr().out)
    assert isinstance(data, list) and len(data) == 2


def test_main_all_missing_files_empty_json(capsys: pytest.CaptureFixture[str]) -> None:
    main(["/nonexistent/bytesense-cli-404-a.txt", "/nonexistent/bytesense-cli-404-b.txt"])
    captured = capsys.readouterr()
    assert "Error" in captured.err
    assert json.loads(captured.out) == []


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
