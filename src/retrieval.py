"""Truy hồi lai (E3) và nhúng bge-m3 (E4): hàm thuần, không phụ thuộc mô hình thật khi test.

Cờ môi trường (mặc định = hành vi cũ):
  RETRIEVAL   = vector | hybrid | hybrid_rerank
  EMBEDDING   = sbert | bge-m3
  BM25_TOKENS = uni | uni_bi
"""

from __future__ import annotations

import math
import os
import re
import threading
import unicodedata
from collections import Counter

RETRIEVALS = ("vector", "hybrid", "hybrid_rerank")
EMBEDDINGS = ("sbert", "bge-m3")
TOKENIZERS = ("uni", "uni_bi")
POOL = 30        # số ứng viên mỗi nhánh trước khi hợp nhất / xếp hạng lại
RRF_K = 60       # hằng số RRF chuẩn (Cormack et al. 2009); không chỉnh theo dữ liệu
# Cross-encoder đa ngôn ngữ (Apache-2.0, XLM-R, model.safetensors 2,27 GB).
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"


def _pick(name: str, allowed: tuple[str, ...], default: str, env=None) -> str:
    v = (env if env is not None else os.environ).get(name, default)
    if v not in allowed:
        raise ValueError(f"{name} không hợp lệ: {v!r} (chỉ {' | '.join(allowed)}).")
    return v


def get_flags(env=None) -> tuple[str, str, str]:
    """(RETRIEVAL, EMBEDDING, BM25_TOKENS); ValueError rõ ràng nếu giá trị lạ."""
    return (_pick("RETRIEVAL", RETRIEVALS, "vector", env),
            _pick("EMBEDDING", EMBEDDINGS, "sbert", env),
            _pick("BM25_TOKENS", TOKENIZERS, "uni", env))


def collection_name(base: str, embedding: str) -> str:
    """Mỗi mô hình nhúng một bộ sưu tập riêng (768 chiều và 1024 chiều không được trộn)."""
    return base if embedding == "sbert" else f"{base}_{embedding}"


def check_collection_embedding(meta: dict | None, embedding: str) -> None:
    """Từ chối mở chỉ mục dựng bằng mô hình nhúng khác (bộ cũ không có khoá = sbert)."""
    have = (meta or {}).get("embedding", "sbert")
    if have != embedding:
        raise RuntimeError(f"Chỉ mục được dựng bằng EMBEDDING={have!r} nhưng đang chạy EMBEDDING={embedding!r}; "
                           "đổi lại biến môi trường hoặc nạp lại tài liệu vào chỉ mục mới.")


def tokenize(text: str, mode: str = "uni") -> list[str]:
    """Chữ thường, NFC, tách theo ký tự không phải chữ/số. uni_bi thêm bigram âm tiết liền kề."""
    if mode not in TOKENIZERS:
        raise ValueError(f"BM25_TOKENS không hợp lệ: {mode!r}")
    toks = re.findall(r"[^\W_]+", unicodedata.normalize("NFC", text).lower())
    if mode == "uni_bi":
        toks += [f"{a} {b}" for a, b in zip(toks, toks[1:])]
    return toks


class BM25:
    """BM25 Okapi tự cài (k1=1.5, b=0.75). ponytail: dựng lại trong bộ nhớ, trần ~10^5 đoạn."""

    def __init__(self, docs: list[str], mode: str = "uni", k1: float = 1.5, b: float = 0.75):
        self.mode, self.k1, self.b = mode, k1, b
        self.tfs = [Counter(tokenize(d, mode)) for d in docs]
        self.lens = [sum(t.values()) for t in self.tfs]
        self.avg = (sum(self.lens) / len(docs)) if docs else 0.0
        df: Counter = Counter()
        for t in self.tfs:
            df.update(t.keys())
        n = len(docs)
        self.idf = {w: math.log(1 + (n - d + 0.5) / (d + 0.5)) for w, d in df.items()}

    def scores(self, query: str) -> list[float]:
        q = set(tokenize(query, self.mode))
        out = []
        for tf, ln in zip(self.tfs, self.lens):
            s = 0.0
            for w in q:
                f = tf.get(w)
                if f:
                    s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * ln / (self.avg or 1.0)))
            out.append(s)
        return out

    def rank(self, query: str, n: int = POOL) -> list[int]:
        """Chỉ số đoạn theo điểm giảm dần (hoà: chỉ số nhỏ trước); bỏ đoạn điểm 0."""
        sc = self.scores(query)
        order = sorted(range(len(sc)), key=lambda i: (-sc[i], i))
        return [i for i in order[:n] if sc[i] > 0]


def rrf(rankings: list[list], k: int = RRF_K) -> list[tuple[object, float]]:
    """Reciprocal Rank Fusion: điểm = tổng 1/(k + hạng), hạng bắt đầu từ 1. Hoà: xuất hiện trước ở nhánh đầu."""
    score: dict = {}
    for r in rankings:
        for pos, item in enumerate(r, start=1):
            score[item] = score.get(item, 0.0) + 1.0 / (k + pos)
    return sorted(score.items(), key=lambda kv: -kv[1])  # sorted ổn định => giữ thứ tự chèn khi hoà


_reranker = None
_reranker_lock = threading.Lock()


def _load_reranker():
    """Dựng CrossEncoder đúng một lần dù nhiều luồng gọi cùng lúc."""
    global _reranker
    with _reranker_lock:
        if _reranker is None:
            import torch
            from sentence_transformers import CrossEncoder
            cuda = torch.cuda.is_available()
            _reranker = CrossEncoder(RERANK_MODEL, max_length=512, device="cuda" if cuda else "cpu",
                                     automodel_args={"torch_dtype": torch.float16} if cuda else {})
    return _reranker


def prewarm_reranker(log=None) -> threading.Thread:
    """Nạp reranker ở luồng nền; lỗi chỉ ghi log, lần dùng đầu sẽ nạp lười."""
    def run():
        try:
            _load_reranker()
        except Exception:
            if log:
                log.exception("Nạp trước reranker thất bại; sẽ nạp lười khi cần.")
    t = threading.Thread(target=run, name="reranker-prewarm", daemon=True)
    t.start()
    return t


def rerank_scores(query: str, docs: list[str]) -> list[float]:
    """Điểm cross-encoder; nạp lười lần đầu (chỉ khi RETRIEVAL=hybrid_rerank)."""
    model = _reranker or _load_reranker()
    return [float(s) for s in model.predict([(query, d) for d in docs], batch_size=16)]


class OllamaEmbeddings:
    """Nhúng dense bge-m3 (1024 chiều) qua Ollama; cùng giao diện embed_documents/embed_query."""

    def __init__(self, model: str = "bge-m3", batch: int = 16):
        self.model, self.batch = model, batch

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        import ollama
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch):
            out += ollama.embed(model=self.model, input=texts[i:i + self.batch])["embeddings"]
        return out

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
