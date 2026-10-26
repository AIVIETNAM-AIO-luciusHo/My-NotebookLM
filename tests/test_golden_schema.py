"""Hợp đồng dữ liệu eval/golden.jsonl (schema + phân bố). Quote so với PDF: python -m eval.check_quotes."""

import json
from collections import Counter
from pathlib import Path

ROWS = [json.loads(l) for l in (Path(__file__).resolve().parent.parent / "eval/golden.jsonl")
        .read_text(encoding="utf-8").splitlines() if l.strip()]
FIELDS = {"id", "doc", "question", "answer", "gold_pages", "gold_quote", "type", "reviewed"}
DOCS = {"bao-cao-bien-doi-gradient.pdf": 27, "probability-vs-statistics.pdf": 55, "kmeans-vs-knn.pdf": 53}


def test_thirty_rows_with_exact_fields():
    assert len(ROWS) == 30
    assert all(set(r) == FIELDS for r in ROWS)


def test_unique_ids():
    assert len({r["id"] for r in ROWS}) == 30


def test_type_distribution_10_10_10():
    assert Counter(r["type"] for r in ROWS) == {"fact": 10, "number": 10, "multi-hop": 10}


def test_each_doc_has_at_least_8():
    c = Counter(r["doc"] for r in ROWS)
    assert set(c) == set(DOCS) and min(c.values()) >= 8


def test_pages_valid_and_multihop_needs_two_pages():
    for r in ROWS:
        assert r["gold_pages"] and all(1 <= p <= DOCS[r["doc"]] for p in r["gold_pages"])
        assert (len(r["gold_pages"]) >= 2) == (r["type"] == "multi-hop"), r["id"]


def test_text_fields_nonempty_and_unreviewed():
    for r in ROWS:
        assert all(r[k].strip() for k in ("question", "answer", "gold_quote"))
        assert r["reviewed"] is False
