"""E3/E4: BM25, RRF, tách từ, cờ, tách chỉ mục theo mô hình nhúng. Offline, không cần mô hình thật."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.modules.setdefault("langchain_huggingface", MagicMock(name="langchain_huggingface"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import retrieval as r  # noqa: E402

DOCS = ["Mèo ăn cá ở nhà", "Chó chạy trong vườn", "Hồi quy tuyến tính dùng bình phương tối thiểu", "Cá voi sống ở biển"]


def test_tokenize_uni_and_bigram():
    assert r.tokenize("Hồi quy, tuyến_tính 2x!") == ["hồi", "quy", "tuyến", "tính", "2x"]
    assert r.tokenize("a b c", "uni_bi") == ["a", "b", "c", "a b", "b c"]


def test_tokenize_nfc_equivalence():
    import unicodedata
    s = "tuyến tính"
    assert r.tokenize(unicodedata.normalize("NFD", s)) == r.tokenize(s)


def test_bm25_ranks_matching_doc_first():
    bm = r.BM25(DOCS)
    assert bm.rank("bình phương tối thiểu")[0] == 2
    assert bm.rank("cá")[:2] == [0, 3] or set(bm.rank("cá")) == {0, 3}


def test_bm25_no_match_and_empty():
    assert r.BM25(DOCS).rank("zzz") == []
    assert r.BM25([]).rank("x") == []


def test_bm25_bigram_prefers_adjacent_phrase():
    docs = ["quy hồi tuyến", "hồi quy tuyến tính"]
    assert r.BM25(docs, "uni_bi").rank("hồi quy")[0] == 1


def test_rrf_scores_and_order():
    out = dict(r.rrf([["a", "b", "c"], ["b", "a"]], k=60))
    assert out["a"] == pytest.approx(1 / 61 + 1 / 62) and out["a"] == pytest.approx(out["b"])
    assert out["c"] == pytest.approx(1 / 63)
    assert [x for x, _ in r.rrf([["a", "b"], ["c", "b"]])][0] == "b"  # b có mặt ở cả hai nhánh


def test_flags_default_and_invalid():
    assert r.get_flags({}) == ("vector", "sbert", "uni")
    assert r.get_flags({"RETRIEVAL": "hybrid", "EMBEDDING": "bge-m3", "BM25_TOKENS": "uni_bi"}) == ("hybrid", "bge-m3", "uni_bi")
    for bad in ({"RETRIEVAL": "bm25"}, {"EMBEDDING": "openai"}, {"BM25_TOKENS": "x"}):
        with pytest.raises(ValueError, match="không hợp lệ"):
            r.get_flags(bad)


def test_collection_name_separates_models():
    assert r.collection_name("second_brain", "sbert") == "second_brain"
    assert r.collection_name("second_brain", "bge-m3") != "second_brain"


def test_refuse_wrong_embedding_index():
    r.check_collection_embedding({"hnsw:space": "cosine"}, "sbert")  # bộ cũ không khoá = sbert
    r.check_collection_embedding({"embedding": "bge-m3"}, "bge-m3")
    with pytest.raises(RuntimeError, match="EMBEDDING"):
        r.check_collection_embedding({"hnsw:space": "cosine"}, "bge-m3")
    with pytest.raises(RuntimeError, match="EMBEDDING"):
        r.check_collection_embedding({"embedding": "bge-m3"}, "sbert")


def test_backend_default_is_old_behaviour():
    import backend
    assert (backend.RETRIEVAL, backend.EMBEDDING) == ("vector", "sbert")
    assert r.collection_name(backend.COLLECTION_NAME, backend.EMBEDDING) == "second_brain"


def test_backend_hybrid_fuses_bm25_hit(monkeypatch, tmp_path):
    """Vector không thấy từ khoá hiếm, BM25 thấy -> đoạn đó lọt top-k khi RETRIEVAL=hybrid."""
    import backend
    from tests.test_multi_file import FakeEmbeddings
    monkeypatch.setattr(backend, "CHROMA_PATH", tmp_path / "c")
    monkeypatch.setattr(backend, "_chroma_client", None)
    monkeypatch.setattr(backend, "_collection", None)
    monkeypatch.setattr(backend, "_embeddings", FakeEmbeddings())
    monkeypatch.setattr(backend, "RETRIEVAL", "hybrid")
    col = backend._get_collection()
    texts = [f"đoạn số {i} nói về chuyện khác" for i in range(6)] + ["xyzzyquux là từ khoá hiếm"]
    col.add(ids=[str(i) for i in range(7)], documents=texts, embeddings=FakeEmbeddings().embed_documents(texts),
            metadatas=[{"source": "a.pdf", "page": 1}] * 7)
    hits = backend._query_workspace(col, "xyzzyquux", 3)
    assert any("xyzzyquux" in h[0] for h in hits) and len(hits) == 3


# ── P1.8 v3 ────────────────────────────────────────────────────────────────
import math  # noqa: E402
import threading  # noqa: E402


class _VecEmb:
    """Nhúng vector 2 chiều cố định theo bảng; chưa biết -> (0, 1)."""
    TABLE = {"truy vấn": [1.0, 0.0]}

    def embed_query(self, t):
        return self.TABLE.get(t, [0.0, 1.0])

    def embed_documents(self, ts):
        return [self.embed_query(t) for t in ts]


def _hybrid_col(monkeypatch, tmp_path):
    import backend
    monkeypatch.setattr(backend, "CHROMA_PATH", tmp_path / "c")
    monkeypatch.setattr(backend, "_chroma_client", None)
    monkeypatch.setattr(backend, "_collection", None)
    monkeypatch.setattr(backend, "_embeddings", _VecEmb())
    monkeypatch.setattr(backend, "RETRIEVAL", "hybrid")
    monkeypatch.setattr(backend, "_bm25_cache", {})
    monkeypatch.setattr(r, "POOL", 2)  # vector chỉ thấy 2 đoạn đầu -> đoạn BM25 nằm ngoài
    return backend, backend._get_collection()


def test_bm25_only_chunk_gets_real_cosine(monkeypatch, tmp_path):
    backend, col = _hybrid_col(monkeypatch, tmp_path)
    vecs = {"a": [1.0, 0.0], "b": [0.9, 0.1], "c": [3.0, 4.0]}  # c: cosine với (1,0) = 0.6
    col.add(ids=list(vecs), documents=["gần một", "gần hai", "xyzzy hiếm"], embeddings=list(vecs.values()),
            metadatas=[{"source": "s.pdf", "page": 1}] * 3)
    hits = backend._query_workspace(col, "truy vấn", 3)
    # truy vấn "truy vấn" không có từ khoá BM25 -> thêm từ hiếm vào truy vấn nhưng giữ vector (1,0)
    monkeypatch.setitem(_VecEmb.TABLE, "truy vấn xyzzy", [1.0, 0.0])
    hits = backend._query_workspace(col, "truy vấn xyzzy", 3)
    score = {h[0]: h[1] for h in hits}["xyzzy hiếm"]
    assert score == pytest.approx(0.6, abs=1e-4) and score != 0.0


def test_bm25_cache_survives_delete_then_add_same_count(monkeypatch, tmp_path):
    backend, col = _hybrid_col(monkeypatch, tmp_path)
    monkeypatch.setattr(r, "POOL", 30)
    add = lambda i, d: col.add(ids=[i], documents=[d], embeddings=[[1.0, 0.0]], metadatas=[{"source": "s", "page": 1}])
    for i, d in (("a", "mèo"), ("b", "chó"), ("c", "cá")):
        add(i, d)
    backend._query_workspace(col, "cá", 3)
    col.delete(ids=["c"])
    add("d", "chim cá")
    hits = backend._query_workspace(col, "chim", 3)  # trước sửa: KeyError 'c'
    assert hits[0][0] == "chim cá"


def test_reranker_built_once_under_threads(monkeypatch):
    built, n = [], 4
    barrier = threading.Barrier(n)
    gate = threading.Event()

    class Stub:
        def __init__(self, *a, **k):
            built.append(1)
            gate.wait(5)  # giữ luồng đầu trong lúc các luồng kia đã tới khoá

        def predict(self, pairs, batch_size=16):
            return [1.0] * len(pairs)

    monkeypatch.setitem(sys.modules, "sentence_transformers", MagicMock(CrossEncoder=Stub))
    monkeypatch.setitem(sys.modules, "torch", MagicMock(**{"cuda.is_available.return_value": False}))
    monkeypatch.setattr(r, "_reranker", None)

    def work():
        barrier.wait()
        r.rerank_scores("q", ["d"])

    ts = [threading.Thread(target=work) for _ in range(n)]
    [t.start() for t in ts]
    threading.Timer(0.5, gate.set).start()  # chỉ để nhả cổng; đúng/sai dựa vào số lần dựng
    [t.join(10) for t in ts]
    assert len(built) == 1


def test_prewarm_only_for_hybrid_rerank(monkeypatch):
    import backend
    calls = []
    monkeypatch.setattr(r, "prewarm_reranker", lambda log=None: calls.append(1))
    monkeypatch.setattr(backend, "RETRIEVAL", "hybrid")
    backend._mark_interrupted_jobs()
    assert calls == []
    monkeypatch.setattr(backend, "RETRIEVAL", "hybrid_rerank")
    backend._mark_interrupted_jobs()
    assert calls == [1]


def test_prewarm_failure_logged_not_raised(monkeypatch):
    monkeypatch.setattr(r, "_load_reranker", MagicMock(side_effect=RuntimeError("hết RAM")))
    log = MagicMock()
    r.prewarm_reranker(log).join(5)
    assert log.exception.called
