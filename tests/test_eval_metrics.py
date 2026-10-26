"""hit@k / MRR trên dữ liệu giả, đáp án tính tay."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eval import metrics as m  # noqa: E402
from eval.check_quotes import check  # noqa: E402

# hạng 1..4
R = [("a", 5), ("b", 1), ("a", 2), ("a", 9)]


def test_hit_at_k_boundaries():
    assert not m.hit_at_k(R, "a", [2], 2)  # trang 2 ở hạng 3
    assert m.hit_at_k(R, "a", [2], 3)


def test_hit_requires_same_doc():
    assert not m.hit_at_k(R, "b", [5], 4)  # trang 5 chỉ có ở doc a
    assert m.hit_at_k(R, "b", [1], 4)


def test_any_gold_page_counts():
    assert m.hit_at_k(R, "a", [7, 9], 4) and not m.hit_at_k(R, "a", [7, 9], 3)


def test_reciprocal_rank():
    assert m.reciprocal_rank(R, "a", [5], 4) == 1.0
    assert m.reciprocal_rank(R, "a", [2], 4) == 1 / 3
    assert m.reciprocal_rank(R, "a", [2], 2) == 0.0  # ngoài top-k
    assert m.reciprocal_rank(R, "a", [8], 4) == 0.0


def test_page_none_never_hits():
    assert not m.hit_at_k([("a", None)], "a", [1], 1)


def test_full_cover_for_multihop():
    assert m.full_cover_at_k(R, "a", [5, 2], 3) and not m.full_cover_at_k(R, "a", [5, 2], 2)


def test_aggregate_by_type():
    rows = [
        {"type": "fact", "hits": {4: True}, "cover": {4: True}, "rr": 1.0},
        {"type": "fact", "hits": {4: False}, "cover": {4: False}, "rr": 0.0},
        {"type": "number", "hits": {4: True}, "cover": {4: True}, "rr": 0.5},
    ]
    a = m.aggregate(rows, ks=(4,))
    assert a["all"]["n"] == 3 and a["all"]["hit@4"] == round(2 / 3, 4) and a["all"]["mrr"] == 0.5
    assert a["fact"]["hit@4"] == 0.5 and a["number"]["mrr"] == 0.5


def test_check_quotes_detects_mismatch(monkeypatch, tmp_path):
    from eval import check_quotes as cq
    monkeypatch.setattr(cq, "PdfReader", lambda p: type("R", (), {"pages": [
        type("P", (), {"extract_text": lambda s: "một  hai\nba"})(),
        type("P", (), {"extract_text": lambda s: "bốn năm"})()]})())
    monkeypatch.setattr(cq, "find_pdf", lambda n: tmp_path)
    ok = {"id": "ok", "doc": "d", "gold_pages": [1, 2], "gold_quote": "hai ba [...] bốn"}
    wrong_page = {"id": "wp", "doc": "d", "gold_pages": [2], "gold_quote": "hai ba"}
    uncovered = {"id": "uc", "doc": "d", "gold_pages": [1, 2], "gold_quote": "hai ba"}
    assert cq.check([ok, wrong_page, uncovered]) == ["wp", "uc"]


def test_fact_pages_reads_edge_page_attr():
    import networkx as nx
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    import evaluate_rag as ev
    g = nx.DiGraph()
    g.add_edge("a", "b", relation="r", source="d.pdf", page=4)
    g.add_edge("b", "c", relation="r", source="d.pdf")  # đồ thị cũ: không có page
    out = ev.fact_pages(g, ["(A, r, B)", "(B, r, C)", "(X, r, Y)", "rác"])
    assert out == [("d.pdf", 4)]
