"""
RAGAS Evaluation Benchmark — Phase 4 of the Unified Personal Second Brain.

Evaluates the RAG pipeline using three metrics with 100% local models:
  - Faithfulness         : Is the answer grounded in the retrieved contexts?
  - Answer Relevancy     : Is the answer relevant to the question asked?
  - Context Precision    : Are the retrieved contexts relevant to the ground truth?

Critic LLM  : Ollama / llama3.2  (via langchain_ollama.ChatOllama)
Critic Embed : keepitreal/vietnamese-sbert  (via langchain_huggingface)

No OpenAI key is required.

# ── Installation ──────────────────────────────────────────────────────────────
# pip install ragas>=0.2.0
# pip install datasets>=2.19.0
# pip install pandas>=2.0.0
# pip install pytest>=8.0.0          (for running tests/test_evaluate_rag.py)
# ─────────────────────────────────────────────────────────────────────────────

Usage:
    python src/evaluate_rag.py          # runs with built-in mock QA pairs
    python -m pytest tests/             # runs the unit test suite
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Output path — report lands in the project root next to requirements.txt
# ---------------------------------------------------------------------------
_REPORT_PATH = Path(__file__).parent.parent / "ragas_evaluation_report.csv"

# ---------------------------------------------------------------------------
# Mock pipeline hooks — replace these with real ChromaDB + Ollama calls
# ---------------------------------------------------------------------------


def _mock_retrieve_contexts(question: str) -> list[str]:
    """
    Placeholder retriever: returns dummy contexts for a question.

    HOOK: Replace this body with a real ChromaDB similarity search, e.g.:
        docs = _vector_db.similarity_search(question, k=4)
        return [doc.page_content for doc in docs]
    """
    return [
        f"[MOCK CONTEXT A] A retrieved passage directly relevant to: '{question}'.",
        f"[MOCK CONTEXT B] A secondary passage providing supporting detail for: '{question}'.",
    ]


def _mock_generate_answer(question: str, contexts: list[str]) -> str:
    """
    Placeholder generator: returns a dummy answer given a question and contexts.

    HOOK: Replace this body with a real Ollama call, e.g.:
        llm = Ollama(model="llama3.2")
        prompt = _PROMPT.format(context="\\n".join(contexts), question=question)
        return _extract_answer(llm.invoke(prompt))
    """
    joined = " | ".join(c[:60] for c in contexts)
    return f"[MOCK ANSWER] Based on the retrieved context ({joined}), the answer is synthesized here."


# ---------------------------------------------------------------------------
# Local model initialisation — no OpenAI
# ---------------------------------------------------------------------------


def _build_critic_models() -> tuple[Any, Any]:
    """
    Initialise the critic LLM and embedding model using only local inference.

    Returns:
        (critic_llm, critic_embeddings) — RAGAS-compatible wrappers.

    Imports are lazy so the test suite can mock them without loading model weights.
    """
    from langchain_ollama import ChatOllama  # type: ignore[import]
    from langchain_huggingface import HuggingFaceEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper

    logger.info("Loading local critic LLM: llama3.2 via Ollama …")
    raw_llm = ChatOllama(model="llama3.2", temperature=0.0)

    logger.info("Loading local critic embeddings: keepitreal/vietnamese-sbert …")
    raw_emb = HuggingFaceEmbeddings(model_name="keepitreal/vietnamese-sbert")

    critic_llm = LangchainLLMWrapper(raw_llm)
    critic_emb = LangchainEmbeddingsWrapper(raw_emb)
    return critic_llm, critic_emb


# ---------------------------------------------------------------------------
# Core evaluation function
# ---------------------------------------------------------------------------


def run_evaluation(qa_pairs: list[dict[str, str]]) -> pd.DataFrame:
    """
    Run the RAGAS benchmark over a list of QA test pairs.

    Each element in *qa_pairs* must have at minimum:
        "question"     : str  — the user question
        "ground_truth" : str  — the reference (golden) answer

    The function wires in the mock pipeline hooks (_mock_retrieve_contexts and
    _mock_generate_answer) that you can replace with real RAG calls later.

    Args:
        qa_pairs: List of dicts with "question" and "ground_truth" keys.

    Returns:
        A pandas DataFrame with per-sample metric scores (faithfulness,
        answer_relevancy, context_precision).  The DataFrame is also written
        to *ragas_evaluation_report.csv* in the project root.
    """
    # ── Late imports to keep this module testable without loading weights ──
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import answer_relevancy, context_precision, faithfulness

    if not qa_pairs:
        raise ValueError("qa_pairs must contain at least one entry.")

    # ── 1. Build critic models (local, no OpenAI) ─────────────────────────
    critic_llm, critic_emb = _build_critic_models()

    # Belt-and-suspenders: set the llm/embeddings directly on each metric
    # in addition to passing them to evaluate() below.  This ensures
    # compatibility with both RAGAS 0.1.x and 0.2.x APIs.
    faithfulness.llm = critic_llm
    answer_relevancy.llm = critic_llm
    answer_relevancy.embeddings = critic_emb
    context_precision.llm = critic_llm

    # ── 2. Run the mock pipeline and build the HuggingFace Dataset ────────
    logger.info("Building evaluation dataset from %d QA pairs …", len(qa_pairs))
    rows: list[dict[str, Any]] = []
    for pair in qa_pairs:
        question: str = pair["question"]
        ground_truth: str = pair["ground_truth"]

        contexts: list[str] = _mock_retrieve_contexts(question)
        answer: str = _mock_generate_answer(question, contexts)

        rows.append(
            {
                "question": question,
                "answer": answer,
                "contexts": contexts,   # list[str] — RAGAS expects a list
                "ground_truth": ground_truth,
            }
        )

    dataset: Dataset = Dataset.from_list(rows)
    logger.info("Dataset schema: %s", dataset.features)

    # ── 3. Run RAGAS evaluate with local critic models ────────────────────
    logger.info("Running RAGAS evaluate …  (this may take a few minutes)")
    result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_precision],
        llm=critic_llm,
        embeddings=critic_emb,
        show_progress=True,
        raise_exceptions=False,     # return NaN for individual failures instead of crashing
    )

    # ── 4. Export to CSV ─────────────────────────────────────────────────
    df: pd.DataFrame = result.to_pandas()
    df.to_csv(_REPORT_PATH, index=False)
    logger.info("Report saved → %s", _REPORT_PATH)
    print(f"\n[RAGAS] Evaluation complete.  Report → {_REPORT_PATH}")
    print(df[["question", "faithfulness", "answer_relevancy", "context_precision"]].to_string())
    return df


# ---------------------------------------------------------------------------
# Sample QA pairs — Database Systems domain
# ---------------------------------------------------------------------------

SAMPLE_QA_PAIRS: list[dict[str, str]] = [
    {
        "question": "What is Boyce-Codd Normal Form (BCNF) and how does it differ from 3NF?",
        "ground_truth": (
            "BCNF (Boyce-Codd Normal Form) is a stricter version of 3NF. "
            "A relation is in BCNF if, for every non-trivial functional dependency X → Y, "
            "X is a superkey of the relation. Unlike 3NF, BCNF does not allow non-key "
            "attributes to determine other attributes even if the determinant is part of a "
            "candidate key, which can lead to loss of some functional dependencies during "
            "decomposition."
        ),
    },
    {
        "question": "Explain the SELECT and PROJECT operations in Relational Algebra.",
        "ground_truth": (
            "SELECT (σ) filters tuples from a relation that satisfy a given predicate, "
            "producing a horizontal subset (fewer rows). "
            "PROJECT (π) extracts specific columns from a relation, producing a vertical "
            "subset (fewer columns) and eliminating duplicate tuples from the result."
        ),
    },
    {
        "question": "What is a functional dependency and why is it important for normalization?",
        "ground_truth": (
            "A functional dependency X → Y means that the value of attribute set X uniquely "
            "determines the value of attribute set Y in a relation. It is the foundation of "
            "database normalization: each normal form (1NF through BCNF) eliminates a "
            "specific class of anomalous functional dependencies to reduce redundancy and "
            "prevent update, insertion, and deletion anomalies."
        ),
    },
    {
        "question": "What are the ACID properties of a database transaction?",
        "ground_truth": (
            "ACID stands for: Atomicity (a transaction is all-or-nothing), "
            "Consistency (a transaction brings the database from one valid state to another), "
            "Isolation (concurrent transactions execute as if they were serial), and "
            "Durability (committed changes survive system failures, typically via a write-ahead log)."
        ),
    },
]


# ---------------------------------------------------------------------------
# --live : retrieval-only evaluation (hit@k theo trang, MRR) — Pha 1 Vòng A
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent
_KS = (4, 6, 8)


def fact_pages(graph: Any, facts: list[str]) -> list[tuple[str, int]]:
    """(source, page) của các cạnh đồ thị đứng sau chuỗi fact "(Subj, rel, Obj)".

    Chỉ dùng cho --with-graph. Cạnh không có thuộc tính page (đồ thị cũ) bị bỏ qua.
    """
    out: list[tuple[str, int]] = []
    for f in facts:
        parts = [x.strip() for x in f.strip()[1:-1].split(",")]
        if len(parts) < 3:
            continue
        u, v = parts[0].lower(), parts[-1].lower()
        data = graph.get_edge_data(u, v) or graph.get_edge_data(v, u) or {}
        if "page" in data and "source" in data:
            out.append((str(data["source"]), int(data["page"])))
    return out


def _pctl(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, round(q * (len(xs) - 1)))]


def run_live(with_graph: bool = False, chunking: str = "char", out: str | None = None,
             retrieval: str | None = None, embedding: str | None = None,
             golden_path: str | None = None, bm25_tokens: str | None = None) -> dict:
    """Nạp 3 PDF vào Chroma/graph TẠM (eval/_work/), đo retrieval cho từng câu golden."""
    import json
    import os
    import shutil
    import subprocess
    import sys
    from datetime import date

    work = _ROOT / "eval" / "_work" / "live"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    # Phải đặt TRƯỚC khi import backend để không chạm chroma_db/ & knowledge_graph.graphml thật.
    os.environ["CHROMA_PATH"] = str(work / "chroma_db")
    os.environ["GRAPH_PATH"] = str(work / "knowledge_graph.graphml")
    for k_, v_ in (("RETRIEVAL", retrieval), ("EMBEDDING", embedding), ("BM25_TOKENS", bm25_tokens)):
        if v_:
            os.environ[k_] = v_
    sys.path[:0] = [str(_ROOT), str(_ROOT / "src")]

    import backend  # noqa: E402
    from pypdf import PdfReader  # noqa: E402

    from eval import metrics  # noqa: E402
    from eval.check_quotes import find_pdf  # noqa: E402

    assert Path(backend.CHROMA_PATH).resolve() == (work / "chroma_db").resolve()
    import resource
    import time

    gp = Path(golden_path) if golden_path else _ROOT / "eval" / "golden.jsonl"
    golden = [json.loads(l) for l in gp.read_text(encoding="utf-8").splitlines() if l.strip()]
    # Tất định: HNSW xây đa luồng cho kết quả xấp xỉ khác nhau giữa các lần chạy. Tạo trước
    # collection với 1 luồng + ef lớn hơn số chunk (~400) để tìm kiếm gần như vét cạn.
    client = backend.chromadb.PersistentClient(path=str(backend.CHROMA_PATH))
    cmeta = {"hnsw:space": "cosine", "hnsw:num_threads": 1,
             "hnsw:construction_ef": 1000, "hnsw:search_ef": 1000}
    if backend.EMBEDDING != "sbert":
        cmeta["embedding"] = backend.EMBEDDING
    client.get_or_create_collection(
        backend.retrieval.collection_name(backend.COLLECTION_NAME, backend.EMBEDDING), metadata=cmeta)
    del client
    col = backend._get_collection()
    t_index = time.perf_counter()
    for name in sorted({g["doc"] for g in golden}):
        pages = [p.extract_text() or "" for p in PdfReader(find_pdf(name)).pages]
        chunks, chunk_pages = backend._chunk_pages(pages, chunking)
        col.add(
            ids=[f"{name}:{i}" for i in range(len(chunks))],  # id tất định
            documents=chunks,
            embeddings=backend._embeddings.embed_documents(chunks),
            metadatas=[{"source": name, "page": p} for p in chunk_pages],
        )
        logger.info("%s: %d chunks", name, len(chunks))
    index_s = time.perf_counter() - t_index

    # Giai đoạn truy hồi (gồm nhúng truy vấn): lượt 1 = lạnh (câu đầu) + xếp hạng; lượt 2 = nóng.
    perf: dict = {}
    if backend.RETRIEVAL != "vector":
        t0 = time.perf_counter()
        backend._bm25_index(col)
        perf["bm25_build_s"] = round(time.perf_counter() - t0, 3)
    rows = []
    cold: list[float] = []
    for g in golden:
        if not cold:
            t0 = time.perf_counter()
            backend._query_workspace(col, g["question"], 8)
            cold.append((time.perf_counter() - t0) * 1000)
        ranked = {k: [(h[2], h[3]) for h in backend._query_workspace(col, g["question"], k)] for k in _KS}
        if with_graph:  # ponytail: chỉ cài đặt, chưa chạy thật (cần Ollama); facts không đổi thứ hạng chunk
            ranked = {k: r + fact_pages(backend._knowledge_graph, backend._get_graph_context(
                backend._knowledge_graph, g["question"])) for k, r in ranked.items()}
        rows.append({
            "id": g["id"], "type": g["type"],
            "hits": {k: metrics.hit_at_k(ranked[k], g["doc"], g["gold_pages"], k) for k in _KS},
            "cover": {k: metrics.full_cover_at_k(ranked[k], g["doc"], g["gold_pages"], k) for k in _KS},
            "rr": metrics.reciprocal_rank(ranked[8], g["doc"], g["gold_pages"], 8),
        })
    hot = []
    for g in golden:
        t0 = time.perf_counter()
        backend._query_workspace(col, g["question"], 8)
        hot.append((time.perf_counter() - t0) * 1000)
    try:
        gpu = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                      text=True).strip()
    except Exception:
        gpu = None
    perf.update({
        "index_s": round(index_s, 1), "chunks": col.count(),
        "index_bytes": sum(f.stat().st_size for f in Path(backend.CHROMA_PATH).rglob("*") if f.is_file()),
        "cold_first_query_ms": round(cold[0], 1),
        "hot_p50_ms": round(_pctl(hot, 0.5), 1), "hot_p95_ms": round(_pctl(hot, 0.95), 1),
        "rss_peak_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024),
        "gpu_used_mib_at_end_all_processes": gpu,
    })
    try:
        rev = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=_ROOT, text=True).strip()
    except Exception:
        rev = "unknown"
    report = {
        "meta": {
            "git_rev": rev, "date": date.today().isoformat(), "k": list(_KS), "n": len(golden),
            "mode": "vector+graph" if with_graph else "vector-only",
            "retrieval": backend.RETRIEVAL, "embedding": backend.EMBEDDING,
            "bm25_tokens": backend.BM25_TOKENS, "golden": gp.name,
            "reviewed": sum(1 for g in golden if g["reviewed"]),
            "mrr_cutoff": 8, "status": "tạm thời (chưa AC-9)",
        },
        "perf": perf,
        "metrics": metrics.aggregate(rows, _KS),
        "per_question": [{"id": r["id"], "type": r["type"], "rr": round(r["rr"], 4),
                          **{f"hit@{k}": r["hits"][k] for k in _KS}} for r in rows],
    }
    (Path(out) if out else _ROOT / "eval" / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="retrieval-only trên 3 PDF (cần EVAL_PDF_DIR)")
    ap.add_argument("--vector-only", action="store_true", help="mặc định")
    ap.add_argument("--with-graph", action="store_true", help="thêm trang từ facts đồ thị (cần Ollama)")
    ap.add_argument("--chunking", choices=["char", "token"], default="char", help="cách chia đoạn khi nạp")
    ap.add_argument("--out", default=None, help="đường dẫn report (mặc định eval/report.json)")
    ap.add_argument("--retrieval", choices=["vector", "hybrid", "hybrid_rerank"], default=None, help="mặc định vector")
    ap.add_argument("--embedding", choices=["sbert", "bge-m3"], default=None, help="mặc định sbert")
    ap.add_argument("--bm25-tokens", choices=["uni", "uni_bi"], default=None, help="mặc định uni")
    ap.add_argument("--golden", default=None, help="tệp golden (mặc định eval/golden.jsonl)")
    args = ap.parse_args()
    if args.live:
        logging.basicConfig(level=logging.INFO)
        rep = run_live(with_graph=args.with_graph, chunking=args.chunking, out=args.out, retrieval=args.retrieval,
                       embedding=args.embedding, golden_path=args.golden, bm25_tokens=args.bm25_tokens)
        print(json.dumps(rep["metrics"], ensure_ascii=False, indent=2))
        raise SystemExit(0)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )
    print("=" * 70)
    print("  Phase 4 — RAGAS Evaluation Benchmark (100% Local Models)")
    print("  Critic LLM  : llama3.2 via Ollama")
    print("  Critic Embed : keepitreal/vietnamese-sbert")
    print("=" * 70)

    report_df = run_evaluation(SAMPLE_QA_PAIRS)

    print("\n── Aggregate Scores ───────────────────────────────────────────────")
    numeric_cols = report_df.select_dtypes("number").columns
    print(report_df[numeric_cols].mean().round(4).to_string())
