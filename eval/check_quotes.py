"""Kiểm tra gold_quote của eval/golden.jsonl khớp văn bản pypdf ở gold_pages.

Chạy:  EVAL_PDF_DIR=<thư mục> python -m eval.check_quotes
Quote multi-hop gồm nhiều đoạn nối bằng " [...] ": mỗi đoạn phải khớp ở một trang
trong gold_pages, và mọi trang trong gold_pages phải được ít nhất một đoạn phủ.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from pypdf import PdfReader

GOLDEN = Path(__file__).with_name("golden.jsonl")
SEP = " [...] "


def norm(s: str) -> str:
    return " ".join(s.split())


def find_pdf(name: str) -> Path:
    base = Path(os.environ["EVAL_PDF_DIR"])
    for p in (base / name, base / "docs" / name):
        if p.exists():
            return p
    raise FileNotFoundError(f"{name} không có trong {base} (hoặc {base}/docs)")


def load_golden() -> list[dict]:
    return [json.loads(l) for l in GOLDEN.read_text(encoding="utf-8").splitlines() if l.strip()]


def check(rows: list[dict]) -> list[str]:
    """Trả về danh sách id không khớp."""
    cache: dict[str, list[str]] = {}
    bad = []
    for r in rows:
        if r["doc"] not in cache:
            cache[r["doc"]] = [norm(p.extract_text() or "") for p in PdfReader(find_pdf(r["doc"])).pages]
        pages = cache[r["doc"]]
        covered, ok = set(), True
        for seg in r["gold_quote"].split(SEP):
            where = [p for p in r["gold_pages"] if 1 <= p <= len(pages) and norm(seg) in pages[p - 1]]
            if not where:
                ok = False
            covered.update(where)
        if not ok or covered != set(r["gold_pages"]):
            bad.append(r["id"])
    return bad


if __name__ == "__main__":
    rows = load_golden()
    bad = check(rows)
    print(f"{len(rows) - len(bad)}/{len(rows)} gold_quote khớp")
    if bad:
        print("Không khớp:", ", ".join(bad))
    sys.exit(1 if bad else 0)
