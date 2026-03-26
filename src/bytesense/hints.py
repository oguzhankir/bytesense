"""
Encoding hint extraction from HTTP headers and HTML/XML documents.

Used internally by StreamDetector, but also available as a public API
for callers who already have the raw content and headers.
"""
from __future__ import annotations

import re
from typing import Optional

_XML_DECL_RE = re.compile(rb'<\?xml[^>]*encoding=["\']([^"\']+)["\']', re.IGNORECASE)
_HTML_META_RE = re.compile(
    rb'<meta[^>]+charset\s*=\s*["\']?\s*([a-zA-Z0-9_\-]+)', re.IGNORECASE
)
_HTTP_EQUIV_RE = re.compile(
    rb'<meta[^>]+http-equiv\s*=\s*["\']?content-type["\']?[^>]*'
    rb'content\s*=\s*["\']?[^"\']*charset=([a-zA-Z0-9_\-]+)',
    re.IGNORECASE,
)
_HTTP_HEADER_RE = re.compile(
    r'charset\s*=\s*["\']?\s*([a-zA-Z0-9_\-]+)', re.IGNORECASE
)


def _normalise(enc_str: str) -> Optional[str]:
    import codecs

    try:
        return codecs.lookup(enc_str.strip()).name.replace("-", "_")
    except LookupError:
        return None


def hint_from_http_headers(headers: dict[str, str]) -> Optional[str]:
    """
    Extract encoding hint from HTTP response headers.

    Args:
        headers: Dict of header name → value (case-insensitive matching).

    Returns:
        Normalised IANA encoding name or None.

    Example::

        enc = hint_from_http_headers({"Content-Type": "text/html; charset=utf-8"})
        # → "utf_8"
    """
    ct = headers.get("Content-Type", headers.get("content-type", ""))
    m = _HTTP_HEADER_RE.search(ct)
    if m:
        return _normalise(m.group(1))
    return None


def hint_from_content(data: bytes, max_scan_bytes: int = 4096) -> Optional[str]:
    """
    Extract encoding hint from the first ``max_scan_bytes`` of an HTML or XML document.

    Looks for:
    - XML declaration: ``<?xml version="1.0" encoding="UTF-8"?>``
    - HTML meta charset: ``<meta charset="utf-8">``
    - HTML http-equiv: ``<meta http-equiv="Content-Type" content="text/html; charset=utf-8">``

    Args:
        data:           Raw bytes (need not be fully decoded).
        max_scan_bytes: How far into the document to scan.

    Returns:
        Normalised IANA encoding name or None.
    """
    probe = data[:max_scan_bytes]
    for pattern in (_XML_DECL_RE, _HTML_META_RE, _HTTP_EQUIV_RE):
        m = pattern.search(probe)
        if m:
            try:
                enc_str = m.group(1).decode("ascii", errors="ignore")
                result = _normalise(enc_str)
                if result:
                    return result
            except Exception:
                pass
    return None


def best_hint(
    data: bytes,
    headers: Optional[dict[str, str]] = None,
    max_scan_bytes: int = 4096,
) -> Optional[str]:
    """
    Return the best encoding hint from HTTP headers and/or document content.

    HTTP headers take priority (more reliable than meta tags).

    Args:
        data:    Raw document bytes.
        headers: HTTP response headers dict (optional).

    Returns:
        Normalised IANA encoding name or None.
    """
    if headers:
        h = hint_from_http_headers(headers)
        if h:
            return h
    return hint_from_content(data, max_scan_bytes)
