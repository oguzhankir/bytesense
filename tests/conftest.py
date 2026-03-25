from __future__ import annotations

from pathlib import Path
from typing import Dict

import pytest

DATA_DIR = Path(__file__).parent / "data"

# ---------------------------------------------------------------------------
# Inline fixtures (no external files needed for basic tests)
# ---------------------------------------------------------------------------

FIXTURES: Dict[str, bytes] = {
    "ascii": b"Hello World! This is pure ASCII text with no high bytes.",
    "utf8_english": "Hello world! Unicode: \u00e9 \u00e0 \u00fc \u00f1".encode(),
    "utf8_french": "Bonjour le monde! J\u2019aime les \u00e9toiles.".encode(),
    "utf8_russian": "\u041f\u0440\u0438\u0432\u0435\u0442 \u043c\u0438\u0440!".encode(),
    "utf8_chinese": "\u4e2d\u6587\u6d4b\u8bd5\u6587\u672c\uff0c\u7528\u4e8e\u7f16\u7801\u68c0\u6d4b\u3002".encode(),
    "latin1_french": "Bonjour, je suis \xe0 la recherche d\x27une aide sur les \xe9toiles.".encode("latin-1"),
    "cp1252_german": "Sch\xf6ne Gr\xfc\xdfe aus Deutschland! \x80\x82".encode("latin-1"),
    "cp1251_russian": "\xcf\xf0\xe8\xe2\xe5\xf2 \xec\xe8\xf0! \xdd\xf2\xee \xf2\xe5\xea\xf1\xf2.".encode("latin-1"),
    "cp1253_greek": "\xc5\xeb\xeb\xe7\xed\xe9\xea\xfc \xea\xe5\xdf\xec\xe5\xed\xef.".encode("latin-1"),
    "utf16_le_bom": "Hello UTF-16 LE".encode("utf-16"),  # includes BOM
    "utf16_be_bom": "Hello UTF-16 BE".encode("utf-16-be"),  # no BOM — add manually
    "utf8_bom": b"\xef\xbb\xbf" + b"Hello with BOM!",
    "empty": b"",
    "single_byte": b"x",
}


@pytest.fixture(params=list(FIXTURES.keys()))
def sample_name(request: pytest.FixtureRequest) -> str:
    return str(request.param)


@pytest.fixture
def samples() -> Dict[str, bytes]:
    return FIXTURES


def load_data_file(name: str) -> bytes:
    return (DATA_DIR / name).read_bytes()
