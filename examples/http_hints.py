#!/usr/bin/env python3
"""Extract charset hints from HTTP headers and from HTML/XML content."""
from __future__ import annotations

from bytesense import best_hint, hint_from_content, hint_from_http_headers


def main() -> None:
    headers = {
        "Content-Type": "text/html; charset=windows-1254",
    }
    h1 = hint_from_http_headers(headers)
    print("hint_from_http_headers:", h1)

    html = b"""<!doctype html><html><head>
<meta charset="utf-8">
<title>x</title></head><body></body></html>"""
    h2 = hint_from_content(html)
    print("hint_from_content:", h2)

    print("best_hint:", best_hint(html, headers=headers))


if __name__ == "__main__":
    main()
