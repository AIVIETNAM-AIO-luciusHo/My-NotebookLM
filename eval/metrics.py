"""Retrieval metrics (no LLM): hit@k theo trang, MRR. Thuần Python, tất định.

Một "ranked" là danh sách (doc, page) theo thứ tự xếp hạng (hạng 1 đầu tiên).
Một hit = chunk thuộc đúng tài liệu `doc` VÀ trang nằm trong `gold_pages`.
"""

from __future__ import annotations

from collections import defaultdict


def _is_hit(item: tuple[str, int | None], doc: str, gold_pages: list[int]) -> bool:
    return item[0] == doc and item[1] in gold_pages


def hit_at_k(ranked, doc: str, gold_pages: list[int], k: int) -> bool:
    return any(_is_hit(it, doc, gold_pages) for it in ranked[:k])


def reciprocal_rank(ranked, doc: str, gold_pages: list[int], k: int) -> float:
    """1/hạng của chunk trúng đầu tiên trong top-k; 0.0 nếu không có."""
    for i, it in enumerate(ranked[:k], start=1):
        if _is_hit(it, doc, gold_pages):
            return 1.0 / i
    return 0.0


def full_cover_at_k(ranked, doc: str, gold_pages: list[int], k: int) -> bool:
    """Mọi trang vàng đều xuất hiện trong top-k (quan trọng với multi-hop)."""
    got = {p for d, p in ranked[:k] if d == doc}
    return set(gold_pages) <= got


def aggregate(rows: list[dict], ks=(4, 6, 8)) -> dict:
    """rows: [{type, hits:{k:bool}, cover:{k:bool}, rr:float}] -> số đo tổng và theo type."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups["all"].append(r)
        groups[r["type"]].append(r)
    out = {}
    for name, rs in groups.items():
        n = len(rs)
        out[name] = {
            "n": n,
            **{f"hit@{k}": round(sum(r["hits"][k] for r in rs) / n, 4) for k in ks},
            **{f"cover@{k}": round(sum(r["cover"][k] for r in rs) / n, 4) for k in ks},
            "mrr": round(sum(r["rr"] for r in rs) / n, 4),
        }
    return out
