"""Tests for encoding hint extraction."""
from __future__ import annotations

import codecs

from bytesense import best_hint, hint_from_content, hint_from_http_headers


def test_http_header_utf8() -> None:
    enc = hint_from_http_headers({"Content-Type": "text/html; charset=utf-8"})
    assert enc == "utf_8"


def test_http_header_cp1252() -> None:
    enc = hint_from_http_headers({"Content-Type": "text/html; charset=windows-1252"})
    assert enc == "cp1252"
    assert codecs.lookup(enc).name == "cp1252"


def test_http_header_missing() -> None:
    enc = hint_from_http_headers({"Content-Type": "text/html"})
    assert enc is None


def test_http_header_case_insensitive() -> None:
    enc = hint_from_http_headers({"content-type": "text/html; charset=UTF-8"})
    assert enc == "utf_8"


def test_html_meta_charset() -> None:
    html = b'<html><head><meta charset="cp1252"></head><body>Test</body></html>'
    enc = hint_from_content(html)
    assert enc is not None
    assert codecs.lookup(enc).name == "cp1252"


def test_xml_declaration() -> None:
    xml = b'<?xml version="1.0" encoding="ISO-8859-1"?><root>x</root>'
    enc = hint_from_content(xml)
    assert enc is not None
    assert codecs.lookup(enc).name == "iso8859-1"


def test_no_hint_in_binary() -> None:
    enc = hint_from_content(bytes(range(256)))
    assert enc is None


def test_best_hint_prefers_header() -> None:
    html = b'<meta charset="iso-8859-1">'
    headers = {"Content-Type": "text/html; charset=utf-8"}
    enc = best_hint(html, headers=headers)
    assert enc == "utf_8"


def test_best_hint_falls_back_to_content() -> None:
    html = b'<meta charset="iso-8859-1">'
    enc = best_hint(html)
    assert enc is not None
    assert codecs.lookup(enc).name == "iso8859-1"
