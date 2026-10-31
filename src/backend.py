import io
import json
import logging
import os
import re
import base64
import hashlib
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import chromadb
import networkx as nx
import numpy as np
from chromadb.api.models.Collection import Collection
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
from gtts import gTTS
from langchain_core.prompts import PromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter
# Aliased: `backend.Ollama` is the patch seam used throughout this module and its tests.
from langchain_ollama import OllamaLLM as Ollama
from langchain_huggingface import HuggingFaceEmbeddings
from pydantic import BaseModel
from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, PyPdfError
from ollama import ResponseError as OllamaResponseError

import jobs
import retrieval

# ---------------------------------------------------------------------------
# App & CORS
# ---------------------------------------------------------------------------

app = FastAPI(title="RAG API — Ollama + ChromaDB + HuggingFace Embeddings")


@app.on_event("startup")
def _mark_interrupted_jobs() -> None:
    n = jobs.mark_interrupted()
    if n:
        logger.warning("%d job(s) from a previous run marked 'interrupted'.", n)
    if RETRIEVAL == "hybrid_rerank":
        retrieval.prewarm_reranker(logger)


_PDF_ENCRYPTED = "PDF có mật khẩu, hãy gỡ mật khẩu rồi tải lại."
_CORS_ORIGINS = ["http://localhost:5173", "http://localhost:5174"]


def _exc_chain(exc: BaseException) -> list:
    chain, e = [], exc
    while e is not None and e not in chain:
        chain.append(e)
        e = e.__cause__ or e.__context__
    return chain


def _ollama_status(exc: BaseException, model: str):
    """(status, detail tiếng Việt) nếu lỗi do Ollama (mô hình chưa tải / không kết nối / quá lâu), ngược lại None."""
    chain = _exc_chain(exc)
    if any(isinstance(c, OllamaResponseError) and c.status_code == 404 for c in chain):
        return 503, f"Mô hình chưa được tải. Chạy `ollama pull {model}`."
    if any(isinstance(c, (httpx.ConnectError, httpx.ConnectTimeout, ConnectionError)) for c in chain):
        return 503, "Không kết nối được Ollama. Hãy chạy `ollama serve`."
    if any(isinstance(c, httpx.ReadTimeout) for c in chain):
        return 504, "Ollama phản hồi quá lâu."
    return None


@app.exception_handler(Exception)
async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    """Lỗi chưa bắt -> JSON. Handler này chạy ở ServerErrorMiddleware, NGOÀI CORSMiddleware,
    nên phải tự gắn header CORS, nếu không trình duyệt coi là lỗi mạng."""
    mapped = _ollama_status(exc, "llama3.2")
    if mapped:
        status, detail = mapped
    else:
        chain = _exc_chain(exc)
        if any(isinstance(c, FileNotDecryptedError) for c in chain):
            status, detail = 400, _PDF_ENCRYPTED
        elif any(isinstance(c, PyPdfError) for c in chain):
            status, detail = 400, "PDF không đọc được hoặc bị hỏng."
        else:
            logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
            status, detail = 500, "Lỗi máy chủ nội bộ."
    headers = {}
    origin = request.headers.get("origin")
    if origin in _CORS_ORIGINS:
        headers = {"access-control-allow-origin": origin, "access-control-allow-credentials": "true", "vary": "Origin"}
    return JSONResponse({"detail": detail}, status_code=status, headers=headers)


app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Singletons — loaded once at startup
# ---------------------------------------------------------------------------

logger = logging.getLogger("backend")

_DAY3_ROOT = Path(__file__).resolve().parent.parent

# Cờ E3/E4 (mặc định vector + sbert = hành vi cũ); giá trị lạ -> ValueError ngay khi import.
RETRIEVAL, EMBEDDING, BM25_TOKENS = retrieval.get_flags()

_embeddings = (HuggingFaceEmbeddings(model_name="keepitreal/vietnamese-sbert") if EMBEDDING == "sbert"
               else retrieval.OllamaEmbeddings("bge-m3"))

# ---------------------------------------------------------------------------
# Persistent vector store — cumulative multi-file workspace (NotebookLM-style)
# ---------------------------------------------------------------------------

# Anchored to the Day3 root so the store lands at Day3/chroma_db no matter
# which directory uvicorn is launched from.
CHROMA_PATH = Path(os.getenv("CHROMA_PATH") or _DAY3_ROOT / "chroma_db")
COLLECTION_NAME = "second_brain"

_chroma_client: chromadb.ClientAPI | None = None
_collection: Collection | None = None


def _get_collection() -> Collection:
    """Lazily open (or create) the persistent workspace collection."""
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        meta = {"hnsw:space": "cosine"}  # cosine → distance = 1 − cosine_similarity, inverted in /chat
        if EMBEDDING != "sbert":
            meta["embedding"] = EMBEDDING  # sbert giữ metadata cũ nguyên vẹn
        _collection = _chroma_client.get_or_create_collection(
            name=retrieval.collection_name(COLLECTION_NAME, EMBEDDING), metadata=meta)
        retrieval.check_collection_embedding(_collection.metadata, EMBEDDING)
    return _collection


def _list_sources(collection: Collection) -> list[str]:
    """Unique 'source' filenames currently loaded in the workspace, sorted."""
    if collection.count() == 0:
        return []
    records = collection.get(include=["metadatas"])
    sources: set[str] = {
        str(meta["source"])
        for meta in records.get("metadatas") or []
        if meta and meta.get("source")
    }
    return sorted(sources)


def _query_workspace(
    collection: Collection, query: str, k: int
) -> list[tuple[str, float, str, int | None]]:
    """Global similarity search across ALL files. Returns (text, cosine_score, source, page).

    page is 1-based, or None for chunks indexed before page metadata existed."""
    count = collection.count()
    if count == 0:
        return []
    if RETRIEVAL != "vector":
        return _query_hybrid(collection, query, k, count)
    result = collection.query(
        query_embeddings=[_embeddings.embed_query(query)],
        n_results=min(k, count),
        include=["documents", "distances", "metadatas"],
    )
    documents: list[str] = (result.get("documents") or [[]])[0]
    distances: list[float] = (result.get("distances") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    hits: list[tuple[str, float, str, int | None]] = []
    for i, text in enumerate(documents):
        distance = float(distances[i]) if i < len(distances) else 1.0
        meta = metadatas[i] if i < len(metadatas) else None
        source = str(meta.get("source", "unknown")) if meta else "unknown"
        page = meta.get("page") if meta else None
        hits.append((text, round(1.0 - distance, 4), source, int(page) if page else None))
    return hits

_bm25_cache: dict = {}


def _bm25_index(collection: Collection):
    """(ids, docs, BM25). Khoá theo băm (id, văn bản) của mọi đoạn: thay/xoá/thêm đều làm mất cache.
    ponytail: đọc lại mọi đoạn mỗi truy vấn để băm và dựng lại trong RAM, trần ~10^5 đoạn; cần sổ phiên bản nếu lớn hơn."""
    r = collection.get(include=["documents"])
    key = hashlib.sha1("\0".join(f"{i}\0{d}" for i, d in zip(r["ids"], r["documents"])).encode()).hexdigest()
    c = _bm25_cache.get(id(collection))
    if c is None or c[0] != key:
        c = (key, r["ids"], r["documents"], retrieval.BM25(r["documents"], BM25_TOKENS))
        _bm25_cache[id(collection)] = c
    return c[1:]


def _query_hybrid(collection: Collection, query: str, k: int, count: int):
    """vector top-30 + BM25 top-30 -> RRF (-> cross-encoder nếu hybrid_rerank) -> top-k.

    cosine_score = cosine thật; đoạn ngoài top-30 vector được tính từ embedding đã lưu (None nếu không lấy được)."""
    qemb = _embeddings.embed_query(query)
    res = collection.query(query_embeddings=[qemb],
                           n_results=min(retrieval.POOL, count), include=["documents", "distances", "metadatas"])
    vids = res["ids"][0]
    info = {i: (d, round(1.0 - float(x), 4), m) for i, d, x, m in
            zip(vids, res["documents"][0], res["distances"][0], res["metadatas"][0])}
    ids, docs, bm = _bm25_index(collection)
    bids = [ids[i] for i in bm.rank(query, retrieval.POOL)]
    fused = [i for i, _ in retrieval.rrf([vids, bids])][:retrieval.POOL]
    missing = [i for i in fused if i not in info]
    if missing:
        r = collection.get(ids=missing, include=["documents", "metadatas", "embeddings"])
        embs = r.get("embeddings")
        qv = np.asarray(qemb, dtype=float)
        for n, (i, d, m) in enumerate(zip(r["ids"], r["documents"], r["metadatas"])):
            cos = None
            try:
                v = np.asarray(embs[n], dtype=float)
                cos = round(float(v @ qv / (np.linalg.norm(v) * np.linalg.norm(qv))), 4)
            except Exception:  # không lấy được embedding -> None, không bịa 0.0
                pass
            info[i] = (d, cos, m)
    if RETRIEVAL == "hybrid_rerank":
        sc = retrieval.rerank_scores(query, [info[i][0] for i in fused])
        fused = [i for _, i in sorted(zip(sc, fused), key=lambda t: -t[0])]
    hits = []
    for i in fused[:k]:
        text, cos, meta = info[i]
        page = meta.get("page") if meta else None
        hits.append((text, cos, str(meta.get("source", "unknown")) if meta else "unknown", int(page) if page else None))
    return hits


# ---------------------------------------------------------------------------
# Knowledge Graph — NetworkX side-car to ChromaDB (Hybrid GraphRAG)
# ---------------------------------------------------------------------------

GRAPH_PATH = Path(os.getenv("GRAPH_PATH") or _DAY3_ROOT / "knowledge_graph.graphml")

# 0 (default) = extract triplets from every chunk; N > 0 caps the per-upload
# LLM extraction calls for very large PDFs.
_GRAPH_MAX_CHUNKS = int(os.getenv("GRAPH_MAX_CHUNKS", "0"))

_TRIPLET_PROMPT = """You are a deterministic information-extraction engine. Read the TEXT and extract factual relationships between named entities and concepts.

OUTPUT RULES — follow them EXACTLY:
1. Output one triplet per line, in this exact format: (Subject, Relationship, Object)
2. Subject and Object are short noun phrases (1-5 words). Relationship is a short verb phrase (1-4 words), e.g. "is a", "works at", "causes", "part of".
3. NEVER use commas or parentheses inside Subject, Relationship, or Object.
4. Extract ONLY facts stated explicitly in the TEXT. Never infer or invent.
5. Extract at most 10 of the most important triplets.
6. If the TEXT contains no extractable relationships, output exactly: NONE
7. Output nothing else — no commentary, no numbering, no markdown.

EXAMPLE TEXT:
Marie Curie discovered polonium and radium. She was a professor at the University of Paris.

EXAMPLE OUTPUT:
(Marie Curie, discovered, polonium)
(Marie Curie, discovered, radium)
(Marie Curie, professor at, University of Paris)

TEXT:
{chunk}

OUTPUT:"""

_TRIPLET_RE = re.compile(r"\(\s*([^,()\n]+?)\s*,\s*([^,()\n]+?)\s*,\s*([^,()\n]+?)\s*\)")


def _parse_triplets(raw: str) -> list[tuple[str, str, str]]:
    """Parse '(Subject, Relationship, Object)' lines; skip anything malformed."""
    if not raw or raw.strip().upper() == "NONE":
        return []
    triplets: list[tuple[str, str, str]] = []
    for match in _TRIPLET_RE.finditer(raw):
        subj, rel, obj = (" ".join(part.split()) for part in match.groups())
        if subj and rel and obj:
            triplets.append((subj, rel, obj))
    return triplets


_extract_state = threading.local()  # .failed = ngoại lệ của lần trích gần nhất trên luồng này (None nếu ổn)


def _is_connection_error(exc: BaseException) -> bool:
    return isinstance(exc, ConnectionError) or "connect" in f"{type(exc).__name__} {exc}".lower()


def _extract_triplets_from_chunk(chunk: str) -> list[tuple[str, str, str]]:
    """LLM triplet extraction at temperature 0.0; never raises — a failed chunk yields []."""
    _extract_state.failed = None
    try:
        llm = Ollama(model="llama3.2", temperature=0.0)
        raw: str = llm.invoke(_TRIPLET_PROMPT.format(chunk=chunk))
        return _parse_triplets(raw)
    except Exception as exc:
        _extract_state.failed = exc
        logger.error("Triplet extraction failed for a chunk; skipping it: %s: %s", type(exc).__name__, exc)
        return []


def _merge_triplets(
    graph: nx.DiGraph, triplets: list[tuple[str, str, str]], source: str, idx: int, page: int | None = None
) -> int:
    """Merge one chunk's triplets into *graph* (idempotent per chunk). Returns edges added."""
    added = 0
    for subj, rel, obj in triplets:
        # Node id = lowercase key so "Marie Curie" and "marie curie" merge;
        # original casing kept as the display label.
        s_key, o_key = subj.lower(), obj.lower()
        if s_key == o_key:
            continue
        if not graph.has_node(s_key):
            graph.add_node(s_key, label=subj, source=source)
        if not graph.has_node(o_key):
            graph.add_node(o_key, label=obj, source=source)
        if graph.has_edge(s_key, o_key):
            existing = graph[s_key][o_key].get("relation", "")
            if rel.lower() not in existing.lower():
                graph[s_key][o_key]["relation"] = f"{existing}; {rel}" if existing else rel
        else:
            attrs = {"page": page} if page is not None else {}
            graph.add_edge(s_key, o_key, relation=rel, source=source, chunk_index=idx, **attrs)
            added += 1
    return added


def _ingest_chunks_into_graph(
    graph: nx.DiGraph, chunks: list[str], source: str, pages: list[int] | None = None
) -> int:
    """Extract triplets from each chunk and merge them into *graph*. Returns edges added."""
    added = 0
    limit = _GRAPH_MAX_CHUNKS if _GRAPH_MAX_CHUNKS > 0 else len(chunks)
    for idx, chunk in enumerate(chunks[:limit]):
        page = pages[idx] if pages and idx < len(pages) else None
        added += _merge_triplets(graph, _extract_triplets_from_chunk(chunk), source, idx, page)
    return added


def _save_graph(graph: nx.DiGraph, path: Path | None = None) -> bool:
    """Persist the graph as GraphML; returns False (never raises) on failure."""
    target = path or GRAPH_PATH
    try:
        nx.write_graphml(graph, target)
        return True
    except Exception:
        logger.exception("Failed to persist knowledge graph to %s", target)
        return False


def _load_graph(path: Path | None = None) -> nx.DiGraph:
    """Load the persisted GraphML if present; otherwise start with an empty graph."""
    target = path or GRAPH_PATH
    if not target.exists():
        return nx.DiGraph()
    try:
        return nx.DiGraph(nx.read_graphml(target))
    except Exception:
        logger.warning("Could not read %s — starting with an empty knowledge graph.", target)
        return nx.DiGraph()


_knowledge_graph: nx.DiGraph = _load_graph()

# ---------------------------------------------------------------------------
# Two-phase ingestion: slow phase (triplet extraction) runs in one background worker
# ---------------------------------------------------------------------------

_graph_lock = threading.RLock()  # bảo vệ _knowledge_graph; KHÔNG giữ khoá khi gọi LLM
_chat_cv = threading.Condition()
_chat_active = 0  # số /chat đang xử lý
_YIELD_MAX_WAIT = 60.0  # giây tối đa worker nhường /chat trước mỗi lần gọi LLM (tránh đói)
_YIELD_COOLDOWN = float(os.getenv("GRAPH_YIELD_COOLDOWN_SECONDS", "3"))  # nguội sau /chat cuối
_clock = time.monotonic  # test thay bằng đồng hồ giả
_chat_last_end = float("-inf")
_SAVE_EVERY = 10  # lưu graphml mỗi N đoạn


@contextmanager
def _chat_gate():
    global _chat_active, _chat_last_end
    with _chat_cv:
        _chat_active += 1
    try:
        yield
    finally:
        with _chat_cv:
            _chat_active -= 1
            _chat_last_end = _clock()
            _chat_cv.notify_all()


def _idle_wait(timeout: float) -> None:
    """Chờ tín hiệu /chat (gọi khi đang giữ _chat_cv); test thay bằng bước đồng hồ giả."""
    _chat_cv.wait(timeout)


def _wait_chat_idle() -> None:
    """Không bắt đầu lời gọi LLM khi /chat đang chạy hoặc mới xong < _YIELD_COOLDOWN giây; trần _YIELD_MAX_WAIT."""
    deadline = _clock() + _YIELD_MAX_WAIT
    logged = False
    with _chat_cv:
        while True:
            now = _clock()
            quiet = _YIELD_COOLDOWN - (now - _chat_last_end)
            if _chat_active == 0 and quiet <= 0:
                return
            if now >= deadline:
                return
            if not logged:
                logger.info("Graph worker yields to /chat (active=%d).", _chat_active)
                logged = True
            _idle_wait(min(deadline - now, quiet) if _chat_active == 0 else deadline - now)


_FAIL_MIN_TRIED = 5  # tỉ lệ lỗi >= 50% trên >= số đoạn này thì job failed
_FAIL_RATIO = 0.5


def _run_graph_job(job_id: str, ctx: dict) -> None:
    """Pha chậm: đọc đoạn từ Chroma theo chunk_ids, trích triplet, ghi đồ thị. ctx chụp lúc xếp hàng."""
    graph, path, collection = ctx["graph"], ctx["path"], ctx["collection"]
    try:
        job = jobs.get(job_id, full=True)
        ids, total, start = job["chunk_ids"], job["chunks_total"], job["chunks_done"]
        jobs.update(job_id, status="graph_running")
        recs = collection.get(ids=ids[start:total], include=["documents", "metadatas"])
        by_id = dict(zip(recs["ids"], zip(recs["documents"], recs["metadatas"])))
        added = job["triplets_added"]
        tried = failed = conn_failed = 0
        save_failed = False
        for idx in range(start, total):
            doc, meta = by_id[ids[idx]]
            _wait_chat_idle()
            _extract_state.failed = None
            triplets = _extract_triplets_from_chunk(doc)  # LLM: ngoài khoá
            err = getattr(_extract_state, "failed", None)
            tried += 1
            if err is not None:
                failed += 1
                conn_failed += _is_connection_error(err)
                if tried >= _FAIL_MIN_TRIED and failed / tried >= _FAIL_RATIO:
                    break
            with _graph_lock:
                added += _merge_triplets(graph, triplets, job["source"], idx, (meta or {}).get("page"))
            if (idx + 1) % _SAVE_EVERY == 0 or idx + 1 == total:
                # chunks_done chỉ ghi SAU khi graphml đã lưu thành công: kill -9 hay lỗi ghi đĩa
                # không làm resume bỏ sót đoạn
                with _graph_lock:
                    saved = _save_graph(graph, path)
                if saved:
                    jobs.update(job_id, chunks_done=idx + 1, triplets_added=added)
                    save_failed = False
                else:
                    save_failed = True
                    jobs.update(job_id, error="Không lưu được đồ thị (graphml); tiến độ không tăng.")
        if tried and (conn_failed == tried or (tried >= _FAIL_MIN_TRIED and failed / tried >= _FAIL_RATIO)):
            why = ("Không kết nối được Ollama" if conn_failed == tried else "Quá nhiều đoạn lỗi khi trích triplet")
            jobs.update(job_id, status="failed",
                        error=f"{why}: {failed}/{tried} đoạn lỗi. Kiểm tra `ollama serve` rồi POST /jobs/{job_id}/resume.")
        elif save_failed:
            jobs.update(job_id, status="failed", error="Không lưu được đồ thị (graphml) ở lần lưu cuối; hãy resume.")
        else:
            warn = f"Cảnh báo: {failed}/{tried} đoạn trích triplet lỗi (đã bỏ qua)." if failed else None
            jobs.update(job_id, status="done", error=warn)
    except Exception as exc:
        logger.exception("Graph job %s failed.", job_id)
        try:
            jobs.update(job_id, status="failed", error=f"{type(exc).__name__}: {exc}")
        except Exception:
            logger.exception("Could not record failure of job %s.", job_id)


_graph_worker = jobs.Worker(_run_graph_job)


def wait_for_jobs(timeout: float | None = 120.0) -> bool:
    """Chờ pha chậm xong (dùng cho test/script). True nếu hết việc trước hạn."""
    return _graph_worker.join(timeout)


def _current_ctx() -> dict:
    return {"graph": _knowledge_graph, "path": GRAPH_PATH, "collection": _get_collection()}


def _graph_ready() -> bool:
    try:
        return not jobs.graph_pending()
    except Exception:
        logger.exception("Could not read job store; assuming graph_ready.")
        return True

_ENTITY_PROMPT = """You are a strict entity extractor. Extract up to 5 key entities (people, places, organizations, concepts, technical terms) from the QUERY.

OUTPUT RULES:
1. Output ONLY the entities, comma-separated, on a single line.
2. No explanations, no numbering, no markdown.
3. If there are no meaningful entities, output exactly: NONE

QUERY:
{query}

ENTITIES:"""


def _extract_query_entities(query: str) -> list[str]:
    """LLM entity extraction with a deterministic keyword fallback."""
    try:
        llm = Ollama(model="llama3.2", temperature=0.0)
        raw = llm.invoke(_ENTITY_PROMPT.format(query=query)).strip()
        if raw and raw.upper() != "NONE":
            entities = [e.strip() for e in raw.splitlines()[0].split(",") if e.strip()]
            if entities:
                return entities[:5]
    except Exception:
        logger.warning("Entity extraction LLM call failed; falling back to query keywords.")
    tokens = re.findall(r"\w+", query.lower(), re.UNICODE)
    return [t for t in tokens if len(t) > 2][:10]


def _match_graph_nodes(graph: nx.DiGraph, entities: list[str]) -> list[str]:
    """Case-insensitive exact + substring matching of entities against graph nodes."""
    matches: list[str] = []
    for entity in entities:
        e = entity.strip().lower()
        if not e:
            continue
        if graph.has_node(e):
            matches.append(e)
            continue
        matches.extend(node for node in graph.nodes if e in node or node in e)
    return list(dict.fromkeys(matches))


def _get_graph_context(graph: nx.DiGraph, query: str, max_facts: int = 15) -> list[str]:
    """Graph sub-pipeline: query entities → matching nodes → 1–2 hop triplet facts."""
    if graph.number_of_nodes() == 0:
        return []
    seeds = _match_graph_nodes(graph, _extract_query_entities(query))
    if not seeds:
        return []

    def fmt(u: str, v: str, data: dict) -> str:
        u_label = graph.nodes[u].get("label", u)
        v_label = graph.nodes[v].get("label", v)
        return f"({u_label}, {data.get('relation', 'related to')}, {v_label})"

    facts: list[str] = []
    seen_edges: set[tuple[str, str]] = set()
    visited: set[str] = set()
    frontier = seeds
    for _hop in range(2):
        next_frontier: list[str] = []
        for node in frontier:
            if node in visited:
                continue
            visited.add(node)
            edges = list(graph.out_edges(node, data=True)) + list(graph.in_edges(node, data=True))
            for u, v, data in edges:
                if (u, v) in seen_edges:
                    continue
                seen_edges.add((u, v))
                facts.append(fmt(u, v, data))
                if len(facts) >= max_facts:
                    return facts
                next_frontier.append(v if u == node else u)
        frontier = next_frontier
    return facts


def _build_hybrid_context(chunks: list[str], graph_facts: list[str]) -> str:
    """Context Fusion: raw vector-search chunks + knowledge-graph triplets."""
    parts: list[str] = []
    if chunks:
        parts.append(
            "### NGỮ CẢNH VĂN BẢN (Vector Search):\n" + "\n\n".join(chunks)
        )
    if graph_facts:
        parts.append(
            "### TRI THỨC ĐỒ THỊ — các quan hệ (Subject, Relation, Object) trích từ tài liệu (Knowledge Graph):\n"
            + "\n".join(f"- {fact}" for fact in graph_facts)
        )
    return "\n\n".join(parts)

# ---------------------------------------------------------------------------
# Chain-of-Thought RAG Prompt
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATE = """ROLE: Bạn là trợ lý AI nghiêm túc, chỉ trả lời dựa trên TÀI LIỆU ĐƯỢC CUNG CẤP.

QUY TẮC TUYỆT ĐỐI:
1. Chỉ dùng thông tin trong phần Ngữ cảnh bên dưới.
2. Nếu không tìm thấy câu trả lời, phải nói trong thẻ <answer>: "Tôi không biết thông tin này vì không có trong tài liệu."
3. Không bịa, không đoán mò, không mở rộng ngoài phạm vi văn bản.

Ngữ cảnh:
{context}

Câu hỏi: {question}

Hãy suy nghĩ từng bước bên trong thẻ <thinking>:
- Xác định đoạn nào trong ngữ cảnh liên quan trực tiếp đến câu hỏi.
- Tổng hợp thông tin từ nhiều đoạn nếu cần, chú ý mâu thuẫn.
- Phác thảo câu trả lời dựa trên bằng chứng cụ thể.

Sau đó viết câu trả lời cuối cùng trong thẻ <answer>.

<thinking>
</thinking>
<answer>
</answer>"""

_PROMPT = PromptTemplate(template=_PROMPT_TEMPLATE, input_variables=["context", "question"])


def _extract_answer(raw: str) -> str:
    """Return the <answer> block content, falling back gracefully."""
    match = re.search(r"<answer>(.*?)</answer>", raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"<answer>(.*?)$", raw, re.DOTALL)
    if match:
        text = match.group(1).strip()
        if text:
            return text
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", raw, flags=re.DOTALL)
    return cleaned.strip() or raw.strip()


def _clean_mermaid(raw: str) -> str:
    """Strip markdown code fences the LLM sometimes wraps around Mermaid output."""
    cleaned = re.sub(r"```(?:mermaid)?\s*\n?", "", raw)
    return cleaned.replace("```", "").strip()


_GENERAL_TOPIC_KEYWORDS = frozenset({
    "tổng quan", "overview", "toàn bộ", "tất cả", "all topics",
    "summary", "tóm tắt", "comprehensive", "main topics", "toàn diện",
    "chủ đề chính", "nội dung chính", "document overview", "general",
    "full document", "entire document", "whole document",
})


def _is_general_topic(topic: str) -> bool:
    t = topic.lower().strip()
    return any(kw in t for kw in _GENERAL_TOPIC_KEYWORDS)


# ---------------------------------------------------------------------------
# Adaptive temperature routing
# ---------------------------------------------------------------------------

_CLASSIFY_PROMPT = """You are a strict query classifier. Given a DOCUMENT CONTEXT and a USER QUERY, classify the query into exactly one category. Output ONLY the integer 1, 2, or 3 — no explanation, no punctuation, no markdown.

Category 1: The query asks for direct facts, definitions, or strict content lookup that can be fully answered from the document context alone.
Category 2: The query is partially related to the document but expands or extends to external real-world knowledge or applications beyond the document.
Category 3: The query is completely unrelated to the document context.

DOCUMENT CONTEXT:
{context}

USER QUERY:
{query}

OUTPUT (1, 2, or 3):"""

_TEMPERATURE_MAP: dict[int, float] = {1: 0.0, 2: 0.3, 3: 0.5}


def _classify_query(context: str, query: str) -> float:
    classifier = Ollama(model="llama3.2", temperature=0.0)
    raw = classifier.invoke(_CLASSIFY_PROMPT.format(context=context, query=query)).strip()
    match = re.search(r"[123]", raw)
    category = int(match.group()) if match else 1
    return _TEMPERATURE_MAP.get(category, 0.0)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    query: str


class GenerateQuizRequest(BaseModel):
    topic: str
    num_questions: int = 5
    difficulty: str = "Normal"


class MindmapRequest(BaseModel):
    topic: str


class SourceDoc(BaseModel):
    text: str
    cosine_score: float | None = None
    source: str = "unknown"
    page: int | None = None


class ChatResponse(BaseModel):
    answer: str
    audio_base64: str
    sources: list[SourceDoc]
    graph_facts: list[str] = []
    graph_ready: bool = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


# Chế độ chia đoạn qua env CHUNKING (đọc mỗi lần gọi): "char" (600 ký tự, chồng 75; mặc định, hành vi cũ) hoặc "token".
# "token": sbert cắt ở 256 token (gồm 2 token đặc biệt). 230 chừa dư cho token đặc biệt và sai số
# khi bộ chia ghép lại đoạn (bộ chia cộng độ dài từng mảnh nên đếm lại cả đoạn có thể lệch; đo trên
# 3 PDF: 230 -> 3 đoạn vượt 256, 220 -> max 255, 210 -> max 243). Chồng 20 token ~ 75 ký tự.
TOKEN_CHUNK_SIZE = 210
TOKEN_CHUNK_OVERLAP = 20
_SBERT_MODEL = "keepitreal/vietnamese-sbert"
_tokenizer = None


def _load_tokenizer():
    """Tải lười tokenizer của sbert từ cache cục bộ (không tải mạng). Thiếu thì raise, không quay về char."""
    global _tokenizer
    if _tokenizer is None:
        try:
            from transformers import AutoTokenizer

            _tokenizer = AutoTokenizer.from_pretrained(_SBERT_MODEL, local_files_only=True)
        except Exception as exc:
            raise RuntimeError(
                "CHUNKING=token cần thư viện `transformers` và tokenizer của "
                f"{_SBERT_MODEL} có sẵn trong cache HuggingFace (không tải mạng): {exc}"
            ) from exc
    return _tokenizer


def _chunk_pages(page_texts: list[str], chunking: str | None = None) -> tuple[list[str], list[int]]:
    """Chunk page by page; chunks never cross a page. Returns (chunks, 1-based pages).

    chunking None -> env CHUNKING; "char" = 600/75 ký tự, "token" = TOKEN_CHUNK_SIZE/TOKEN_CHUNK_OVERLAP token sbert.
    """
    mode = chunking or os.getenv("CHUNKING", "char")
    if mode == "char":
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=600, chunk_overlap=75, separators=["\n\n", "\n", " ", ""]
        )
    elif mode == "token":
        tok = _load_tokenizer()
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=TOKEN_CHUNK_SIZE, chunk_overlap=TOKEN_CHUNK_OVERLAP,
            separators=["\n\n", "\n", " ", ""],
            length_function=lambda t: len(tok.encode(t, add_special_tokens=False)),
        )
    else:
        raise ValueError(f"CHUNKING không hợp lệ: {mode!r} (chỉ 'char' hoặc 'token').")
    chunks: list[str] = []
    pages: list[int] = []
    for page_no, text in enumerate(page_texts, start=1):
        for piece in splitter.split_text(text) if text.strip() else []:
            chunks.append(piece)
            pages.append(page_no)
    return chunks, pages


@app.get("/health")
def health() -> dict[str, object]:
    try:
        collection = _get_collection()
        chunk_count = collection.count()
        files = _list_sources(collection)
    except Exception:
        logger.exception("Persistent vector store unavailable in /health.")
        chunk_count, files = 0, []
    return {
        "status": "ok",
        "document_loaded": chunk_count > 0,
        "files": files,
        "chunk_count": chunk_count,
        "model": "llama3.2",
        "graph_nodes": _knowledge_graph.number_of_nodes(),
        "graph_edges": _knowledge_graph.number_of_edges(),
        "graph_ready": _graph_ready(),
    }


@app.get("/files", response_model=list[str], summary="List all source files in the workspace")
def list_files() -> list[str]:
    try:
        return _list_sources(_get_collection())
    except Exception as exc:
        logger.exception("Failed to enumerate workspace sources.")
        raise HTTPException(status_code=500, detail="Could not read the workspace store.") from exc


def _fast_phase(filename: str, content: bytes) -> dict:
    """Pha nhanh (chạy trong threadpool): trích văn bản, chia đoạn, embedding, ghi Chroma."""
    job_id = jobs.create(filename)
    try:
        jobs.update(job_id, status="fast_running")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            try:
                reader = PdfReader(tmp_path)
                page_texts = [page.extract_text() or "" for page in reader.pages]
            except PyPdfError as exc:
                msg = _PDF_ENCRYPTED if isinstance(exc, FileNotDecryptedError) else "PDF không đọc được hoặc bị hỏng."
                raise HTTPException(status_code=400, detail=msg) from exc
            raw_text = "".join(page_texts)
        finally:
            os.remove(tmp_path)

        if not raw_text.strip():
            raise HTTPException(status_code=422, detail="No extractable text found in PDF.")

        chunks, chunk_pages = _chunk_pages(page_texts)

        # ── Cumulative vector indexing — append, never overwrite ────────────
        ids = [uuid4().hex for _ in chunks]
        limit = _GRAPH_MAX_CHUNKS if _GRAPH_MAX_CHUNKS > 0 else len(chunks)
        jobs.update(job_id, chunk_ids=ids, chunks_total=min(limit, len(chunks)))
        try:
            collection = _get_collection()
            collection.add(
                ids=ids,
                documents=chunks,
                embeddings=_embeddings.embed_documents(chunks),
                metadatas=[{"source": filename, "page": p} for p in chunk_pages],
            )
        except Exception as exc:
            logger.exception("Vector indexing failed for '%s'.", filename)
            mapped = _ollama_status(exc, getattr(_embeddings, "model", "bge-m3")) if EMBEDDING != "sbert" else None
            if mapped:
                raise HTTPException(status_code=mapped[0], detail=mapped[1]) from exc
            raise HTTPException(status_code=500, detail="Vector indexing failed.") from exc

        jobs.update(job_id, status="fast_done")
        ctx = _current_ctx()
        _graph_worker.submit(job_id, ctx)
    except Exception as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else f"{type(exc).__name__}: {exc}"
        jobs.update(job_id, status="failed", error=str(detail))
        raise

    with _graph_lock:
        nodes, edges = _knowledge_graph.number_of_nodes(), _knowledge_graph.number_of_edges()
    return {
        "message": "Document appended to workspace.",
        "source": filename,
        "chunk_count": len(chunks),
        "total_chunks": collection.count(),
        "files": _list_sources(collection),
        "graph_triplets_added": 0,  # pha chậm chạy nền; xem GET /jobs/{job_id}
        "graph_nodes": nodes,
        "graph_edges": edges,
        "graph_persisted": False,
        "job_id": job_id,
        "graph_status": "pending",
    }


@app.post("/upload", summary="Upload a PDF and append it to the persistent workspace")
async def upload_pdf(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Chỉ nhận tệp PDF.")
    content = await file.read()
    return await run_in_threadpool(_fast_phase, file.filename or "unknown.pdf", content)


@app.get("/jobs", summary="List ingestion jobs, newest first")
def list_jobs() -> list[dict]:
    return jobs.list_jobs()


@app.get("/jobs/{job_id}", summary="Status of one ingestion job")
def get_job(job_id: str) -> dict:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@app.delete("/jobs/{job_id}", summary="Delete a finished job record (done|failed|interrupted)")
def delete_job(job_id: str) -> dict:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    # chỉ xoá bản ghi job; KHÔNG đụng Chroma/đồ thị. CAS nguyên tử: job vừa chuyển sang chạy thì không xoá.
    if not jobs.delete_finished(job_id):
        raise HTTPException(status_code=409, detail="Tác vụ đang chạy, chưa xoá được.")
    return {"deleted": job_id}


@app.post("/jobs/{job_id}/resume", summary="Resume the graph phase of an interrupted/failed job")
def resume_job(job_id: str) -> dict:
    job = jobs.get(job_id, full=True)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    ids = job["chunk_ids"][: job["chunks_total"]]
    try:
        present = len(_get_collection().get(ids=ids, include=[])["ids"]) if ids else 0
    except Exception:
        present = 0
    if not ids or present != len(ids):
        raise HTTPException(status_code=409, detail="Pha nhanh chưa hoàn tất; hãy upload lại tệp.")
    # compare-and-set: hai resume đồng thời chỉ một cái thắng
    if not jobs.claim(job_id, ("interrupted", "failed"), status="queued", error=None):
        now = jobs.get(job_id)["status"]
        raise HTTPException(status_code=409, detail=f"Job is '{now}', not resumable.")
    _graph_worker.submit(job_id, _current_ctx())
    return jobs.get(job_id)


@app.post("/chat", response_model=ChatResponse, summary="RAG chat with CoT, cosine scores and TTS")
def chat(request: ChatRequest):
    with _chat_gate():
        return _chat_impl(request)


def _chat_impl(request: ChatRequest):
    try:
        collection = _get_collection()
        workspace_empty = collection.count() == 0
    except Exception as exc:
        logger.exception("Persistent vector store unavailable in /chat.")
        raise HTTPException(status_code=500, detail="Could not read the workspace store.") from exc
    if workspace_empty:
        raise HTTPException(status_code=400, detail="Workspace is empty. POST to /upload first.")

    # ── Hybrid Retrieval ─────────────────────────────────────────────────────
    # 1. Vector sub-pipeline — top-4 chunks by cosine similarity across ALL files
    hits = _query_workspace(collection, request.query, k=4)
    chunk_texts = [h[0] for h in hits]
    sources = [
        SourceDoc(text=text, cosine_score=score, source=source, page=page)
        for text, score, source, page in hits
    ]

    # 2. Graph sub-pipeline — query entities → node match → 1–2 hop triplets
    try:
        with _graph_lock:  # ảnh chụp; truy vấn (có gọi LLM) chạy ngoài khoá
            graph_snapshot = _knowledge_graph.copy()
        graph_facts = _get_graph_context(graph_snapshot, request.query)
    except Exception:
        logger.exception("Graph retrieval failed; falling back to vector-only context.")
        graph_facts = []

    # 3. Context Fusion — dense chunks + explicit graph relations
    context = _build_hybrid_context(chunk_texts, graph_facts)

    # ── Intent classification → adaptive temperature ───────────────────────
    temperature = _classify_query(context, request.query)
    llm = Ollama(model="llama3.2", temperature=temperature)
    raw: str = llm.invoke(_PROMPT.format(context=context, question=request.query))
    answer = _extract_answer(raw)

    # ── TTS → Base64 ─────────────────────────────────────────────────────────
    try:
        tts = gTTS(text=answer, lang="vi", slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        audio_base64 = "data:audio/mp3;base64," + base64.b64encode(buf.read()).decode()
    except Exception:
        audio_base64 = ""

    return ChatResponse(
        answer=answer,
        audio_base64=audio_base64,
        sources=sources,
        graph_facts=graph_facts,
        graph_ready=_graph_ready(),
    )


@app.post("/generate-quiz", summary="Generate a multiple-choice quiz from indexed document")
def generate_quiz(request: GenerateQuizRequest):
    collection = _get_collection()
    if collection.count() == 0:
        raise HTTPException(status_code=400, detail="Workspace is empty. POST to /upload first.")

    hits = _query_workspace(collection, request.topic, k=8)
    context = "\n\n".join(text for text, *_ in hits)

    difficulty_instruction = (
        f'DIFFICULTY / FOCUS DIRECTIVE: "{request.difficulty}". '
        "Strictly tailor every question to this direction. "
        "For 'Easy': use simple vocabulary, test recall of key definitions. "
        "For 'Hard': require multi-step reasoning, compare/contrast, or apply concepts. "
        "For any other value: treat it as a subject-focus filter and only ask about that aspect."
    )

    prompt = f"""You are a JSON-only quiz generator. Read the CONTEXT and produce exactly {request.num_questions} multiple-choice questions about "{request.topic}".

{difficulty_instruction}

STRICT RULES:
1. Output ONLY valid JSON. No commentary, no markdown fences, no text outside the JSON.
2. "correctAnswer" must be a 0-based integer index into that question's "options" array.
3. Every "explanation" must cite a fact stated directly in the CONTEXT — never invent.
4. Produce exactly {request.num_questions} questions inside the "questions" array.

--- EXAMPLE ---

CONTEXT:
Quang hợp là quá trình thực vật sử dụng ánh sáng mặt trời, nước và khí CO2 để tổng hợp glucose và giải phóng oxy. Quá trình này diễn ra bên trong lục lạp, nơi chứa chất diệp lục có khả năng hấp thụ ánh sáng.

TOPIC: Quang hợp
DIFFICULTY: Easy
NUM_QUESTIONS: 1

OUTPUT:
{{
  "title": "Quiz: Quang hợp",
  "questions": [
    {{
      "question": "Quang hợp diễn ra ở bào quan nào trong tế bào thực vật?",
      "options": ["Ti thể", "Lục lạp", "Nhân tế bào", "Không bào"],
      "correctAnswer": 1,
      "explanation": "Theo tài liệu, quang hợp diễn ra bên trong lục lạp — nơi chứa chất diệp lục hấp thụ ánh sáng mặt trời."
    }}
  ]
}}

--- YOUR TURN ---

CONTEXT:
{context}

TOPIC: {request.topic}
DIFFICULTY: {request.difficulty}
NUM_QUESTIONS: {request.num_questions}

OUTPUT:"""

    llm = Ollama(model="llama3.2", temperature=0.1, format="json")
    raw: str = llm.invoke(prompt)

    try:
        quiz_data = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="LLM produced invalid JSON. Please try again.")

    questions = quiz_data.get("questions")
    if not isinstance(questions, list) or len(questions) == 0:
        raise HTTPException(status_code=422, detail="LLM response missing valid 'questions' array.")

    for i, q in enumerate(questions):
        if not isinstance(q.get("question"), str) or not q["question"].strip():
            raise HTTPException(status_code=422, detail=f"Question {i} is missing a 'question' string.")
        if not isinstance(q.get("options"), list) or len(q["options"]) < 2:
            raise HTTPException(status_code=422, detail=f"Question {i} must have at least 2 options.")
        if not isinstance(q.get("correctAnswer"), int):
            raise HTTPException(status_code=422, detail=f"Question {i} 'correctAnswer' must be an integer.")
        if q["correctAnswer"] < 0 or q["correctAnswer"] >= len(q["options"]):
            raise HTTPException(status_code=422, detail=f"Question {i} 'correctAnswer' index is out of range.")

    return quiz_data


@app.post("/generate-mindmap", summary="Generate a Mermaid.js mindmap from indexed document")
def generate_mindmap(request: MindmapRequest):
    collection = _get_collection()
    if collection.count() == 0:
        raise HTTPException(status_code=400, detail="Workspace is empty. POST to /upload first.")

    hits = _query_workspace(collection, request.topic, k=6)
    context = "\n\n".join(text for text, *_ in hits)

    if _is_general_topic(request.topic):
        prompt = f"""You are a Mermaid.js diagram generator. Your output must be ONLY valid Mermaid graph syntax.

CRITICAL RULES:
1. Output ONLY the raw Mermaid code. Absolutely no markdown backticks, no explanations, no prose.
2. Start the output directly with: graph TD
3. Keep node labels short (3-6 words). Wrap all labels in double quotes.
4. Use maximum 18 nodes. Prefer a clear 2-level hierarchy: root → pillars → key concepts.
5. Every edge must use the --> arrow.

TASK — DOCUMENT OVERVIEW MINDMAP:
The user wants a comprehensive top-level mindmap of the ENTIRE document.
Read the CONTEXT carefully and:
  1. Identify the 3-5 foundational pillars, chapters, or major themes present in the context.
  2. Under each pillar, list 2-3 of its most important sub-concepts or facts.
  3. Use a single root node labelled with the document's apparent subject.

--- EXAMPLE INPUT ---
CONTEXT: Chapter 1 covers Newton's three laws of motion. Chapter 2 discusses energy: kinetic, potential, and conservation. Chapter 3 explores waves: frequency, amplitude, and the electromagnetic spectrum. Forces such as friction, gravity, and tension are covered throughout.

--- EXAMPLE OUTPUT ---
graph TD
    ROOT["Physics Fundamentals"] --> P1["Newton's Laws of Motion"]
    ROOT --> P2["Energy"]
    ROOT --> P3["Waves & EM Spectrum"]
    ROOT --> P4["Forces"]
    P1 --> C1["Law 1: Inertia"]
    P1 --> C2["Law 2: F = ma"]
    P1 --> C3["Law 3: Action-Reaction"]
    P2 --> C4["Kinetic Energy"]
    P2 --> C5["Potential Energy"]
    P2 --> C6["Conservation of Energy"]
    P3 --> C7["Frequency & Amplitude"]
    P3 --> C8["Electromagnetic Spectrum"]
    P4 --> C9["Gravity & Friction"]
    P4 --> C10["Tension"]

--- YOUR TURN ---
CONTEXT:
{context}

OUTPUT:"""
    else:
        prompt = f"""You are a Mermaid.js diagram generator. Your output must be ONLY valid Mermaid graph syntax.

CRITICAL RULES:
1. Output ONLY the raw Mermaid code. Absolutely no markdown backticks, no explanations, no prose.
2. Start the output directly with: graph TD
3. Keep node labels short (3-5 words). Wrap labels containing special chars in double quotes.
4. Use maximum 15 nodes. Prefer a clear tree/hierarchy over a flat list.
5. Every edge must use the --> arrow.

--- EXAMPLE INPUT ---
TOPIC: Photosynthesis
CONTEXT: Photosynthesis occurs in chloroplasts using sunlight, CO2, and water to produce glucose and oxygen. It has two main stages: the light-dependent reactions and the Calvin cycle. Chlorophyll absorbs light energy.

--- EXAMPLE OUTPUT ---
graph TD
    A["Photosynthesis"] --> B["Location: Chloroplasts"]
    A --> C["Inputs"]
    A --> D["Outputs"]
    A --> E["Two Stages"]
    C --> F["Sunlight"]
    C --> G["CO2"]
    C --> H["Water"]
    D --> I["Glucose"]
    D --> J["Oxygen"]
    E --> K["Light Reactions"]
    E --> L["Calvin Cycle"]
    B --> M["Contains Chlorophyll"]

--- YOUR TURN ---
TOPIC: {request.topic}
CONTEXT:
{context}

OUTPUT:"""

    llm = Ollama(model="llama3.2", temperature=0.0)
    raw: str = llm.invoke(prompt)

    mermaid_code = _clean_mermaid(raw)

    if not mermaid_code.strip().startswith("graph"):
        lines = mermaid_code.splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith("graph"):
                mermaid_code = "\n".join(lines[i:])
                break
        else:
            raise HTTPException(
                status_code=422,
                detail="LLM did not produce valid Mermaid syntax. Please try again."
            )

    return {"mermaid_code": mermaid_code}
