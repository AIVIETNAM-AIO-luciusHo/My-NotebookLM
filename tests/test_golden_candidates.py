"""Hợp đồng dữ liệu eval/golden_candidates.jsonl (cấu trúc, không cần PDF). Quote so với PDF: python -m eval.p18_check_candidates."""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROWS = [json.loads(l) for l in (ROOT / "eval/golden_candidates.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
GOLD_IDS = {json.loads(l)["id"] for l in (ROOT / "eval/golden.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
FIELDS = {"id", "doc", "question", "answer", "gold_pages", "gold_quote", "type", "reviewed", "kind", "proposed_by"}
DOCS = {"math-linear-regression.pdf": 51, "module3-trees-xai-timeseries.pdf": 60, "module4-deeplearning-optimization.pdf": 90}
OLD_DOCS = {"bao-cao-bien-doi-gradient.pdf", "probability-vs-statistics.pdf", "kmeans-vs-knn.pdf"}


def test_schema_and_unique_ids():
    assert len(ROWS) >= 30 and all(set(r) == FIELDS for r in ROWS)
    ids = [r["id"] for r in ROWS]
    assert len(set(ids)) == len(ids) and not set(ids) & GOLD_IDS


def test_enums_and_unreviewed():
    for r in ROWS:
        assert r["type"] in {"fact", "number", "multi-hop"} and r["kind"] in {"prose", "table", "formula"}
        assert r["reviewed"] is False and r["proposed_by"] == "model"


def test_pages_valid_and_multihop_needs_two_pages():
    for r in ROWS:
        assert r["doc"] in DOCS and r["doc"] not in OLD_DOCS
        assert r["gold_pages"] and all(1 <= p <= DOCS[r["doc"]] for p in r["gold_pages"]), r["id"]
        assert (len(r["gold_pages"]) >= 2) == (r["type"] == "multi-hop"), r["id"]
        assert len(r["gold_quote"].split(" [...] ")) == len(r["gold_pages"]), r["id"]
        assert all(r[k].strip() for k in ("question", "answer", "gold_quote"))


def test_balance():
    assert min(Counter(r["type"] for r in ROWS).values()) >= 8
    assert sum(r["kind"] in {"table", "formula"} for r in ROWS) >= 10
    c = Counter(r["doc"] for r in ROWS)
    assert set(c) == set(DOCS) and min(c.values()) >= 8


def test_no_duplicate_questions():
    qs = [" ".join(r["question"].lower().split()) for r in ROWS]
    assert len(set(qs)) == len(qs)
