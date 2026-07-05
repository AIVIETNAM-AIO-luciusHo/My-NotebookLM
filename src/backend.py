import io
import json
import logging
import os
import re
import base64
import tempfile
from pathlib import Path
from uuid import uuid4

import chromadb
import networkx as nx
from chromadb.api.models.Collection import Collection
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from gtts import gTTS
from langchain_core.prompts import PromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter
# Aliased: `backend.Ollama` is the patch seam used throughout this module and its tests.
from langchain_ollama import OllamaLLM as Ollama
from langchain_huggingface import HuggingFaceEmbeddings
from pydantic import BaseModel
from pypdf import PdfReader

# ---------------------------------------------------------------------------
# App & CORS
# ---------------------------------------------------------------------------

app = FastAPI(title="RAG API — Ollama + ChromaDB + HuggingFace Embeddings")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Singletons — loaded once at startup
# ---------------------------------------------------------------------------

logger = logging.getLogger("backend")

_DAY3_ROOT = Path(__file__).resolve().parent.parent

_embeddings = HuggingFaceEmbeddings(model_name="keepitreal/vietnamese-sbert")

# ---------------------------------------------------------------------------
# Persistent vector store — cumulative multi-file workspace (NotebookLM-style)
# ---------------------------------------------------------------------------

# Anchored to the Day3 root so the store lands at Day3/chroma_db no matter
# which directory uvicorn is launched from.
CHROMA_PATH = _DAY3_ROOT / "chroma_db"
COLLECTION_NAME = "second_brain"

_chroma_client: chromadb.ClientAPI | None = None
_collection: Collection | None = None


def _get_collection() -> Collection:
    """Lazily open (or create) the persistent workspace collection."""
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            # hnsw:space=cosine → distance = 1 − cosine_similarity, inverted in /chat
            metadata={"hnsw:space": "cosine"},
        )
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


def _query_workspace(collection: Collection, query: str, k: int) -> list[tuple[str, float, str]]:
    """Global similarity search across ALL files. Returns (text, cosine_score, source)."""
    count = collection.count()
    if count == 0:
        return []
    result = collection.query(
        query_embeddings=[_embeddings.embed_query(query)],
        n_results=min(k, count),
        include=["documents", "distances", "metadatas"],
    )
    documents: list[str] = (result.get("documents") or [[]])[0]
    distances: list[float] = (result.get("distances") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    hits: list[tuple[str, float, str]] = []
    for i, text in enumerate(documents):
        distance = float(distances[i]) if i < len(distances) else 1.0
        meta = metadatas[i] if i < len(metadatas) else None
        source = str(meta.get("source", "unknown")) if meta else "unknown"
        hits.append((text, round(1.0 - distance, 4), source))
    return hits

# ---------------------------------------------------------------------------
# Knowledge Graph — NetworkX side-car to ChromaDB (Hybrid GraphRAG)
# ---------------------------------------------------------------------------

GRAPH_PATH = _DAY3_ROOT / "knowledge_graph.graphml"

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


def _extract_triplets_from_chunk(chunk: str) -> list[tuple[str, str, str]]:
    """LLM triplet extraction at temperature 0.0; never raises — a failed chunk yields []."""
    try:
        llm = Ollama(model="llama3.2", temperature=0.0)
        raw: str = llm.invoke(_TRIPLET_PROMPT.format(chunk=chunk))
        return _parse_triplets(raw)
    except Exception:
        logger.exception("Triplet extraction failed for a chunk; skipping it.")
        return []


def _ingest_chunks_into_graph(graph: nx.DiGraph, chunks: list[str], source: str) -> int:
    """Extract triplets from each chunk and merge them into *graph*. Returns edges added."""
    added = 0
    limit = _GRAPH_MAX_CHUNKS if _GRAPH_MAX_CHUNKS > 0 else len(chunks)
    for idx, chunk in enumerate(chunks[:limit]):
        for subj, rel, obj in _extract_triplets_from_chunk(chunk):
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
                graph.add_edge(s_key, o_key, relation=rel, source=source, chunk_index=idx)
                added += 1
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
    cosine_score: float
    source: str = "unknown"


class ChatResponse(BaseModel):
    answer: str
    audio_base64: str
    sources: list[SourceDoc]
    graph_facts: list[str] = []


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


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
    }


@app.get("/files", response_model=list[str], summary="List all source files in the workspace")
def list_files() -> list[str]:
    try:
        return _list_sources(_get_collection())
    except Exception as exc:
        logger.exception("Failed to enumerate workspace sources.")
        raise HTTPException(status_code=500, detail="Could not read the workspace store.") from exc


@app.post("/upload", summary="Upload a PDF and append it to the persistent workspace")
async def upload_pdf(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    filename: str = file.filename or "unknown.pdf"

    content = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        reader = PdfReader(tmp_path)
        raw_text = "".join(page.extract_text() or "" for page in reader.pages)
    finally:
        os.remove(tmp_path)

    if not raw_text.strip():
        raise HTTPException(status_code=422, detail="No extractable text found in PDF.")

    chunks = RecursiveCharacterTextSplitter(
        chunk_size=600, chunk_overlap=75, separators=["\n\n", "\n", " ", ""]
    ).split_text(raw_text)

    # ── Cumulative vector indexing — append, never overwrite ────────────────
    try:
        collection = _get_collection()
        collection.add(
            ids=[uuid4().hex for _ in chunks],
            documents=chunks,
            embeddings=_embeddings.embed_documents(chunks),
            metadatas=[{"source": filename} for _ in chunks],
        )
    except Exception as exc:
        logger.exception("Vector indexing failed for '%s'.", filename)
        raise HTTPException(status_code=500, detail="Vector indexing failed.") from exc

    # ── Knowledge Graph extraction (Hybrid GraphRAG ingestion) ──────────────
    triplets_added = _ingest_chunks_into_graph(_knowledge_graph, chunks, source=filename)
    graph_persisted = _save_graph(_knowledge_graph)
    if triplets_added == 0:
        logger.warning("No knowledge-graph triplets extracted from '%s'.", filename)

    return {
        "message": "Document appended to workspace.",
        "source": filename,
        "chunk_count": len(chunks),
        "total_chunks": collection.count(),
        "files": _list_sources(collection),
        "graph_triplets_added": triplets_added,
        "graph_nodes": _knowledge_graph.number_of_nodes(),
        "graph_edges": _knowledge_graph.number_of_edges(),
        "graph_persisted": graph_persisted,
    }


@app.post("/chat", response_model=ChatResponse, summary="RAG chat with CoT, cosine scores and TTS")
async def chat(request: ChatRequest):
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
    chunk_texts = [text for text, _, _ in hits]
    sources = [
        SourceDoc(text=text, cosine_score=score, source=source)
        for text, score, source in hits
    ]

    # 2. Graph sub-pipeline — query entities → node match → 1–2 hop triplets
    try:
        graph_facts = _get_graph_context(_knowledge_graph, request.query)
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
    )


@app.post("/generate-quiz", summary="Generate a multiple-choice quiz from indexed document")
async def generate_quiz(request: GenerateQuizRequest):
    collection = _get_collection()
    if collection.count() == 0:
        raise HTTPException(status_code=400, detail="Workspace is empty. POST to /upload first.")

    hits = _query_workspace(collection, request.topic, k=8)
    context = "\n\n".join(text for text, _, _ in hits)

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
async def generate_mindmap(request: MindmapRequest):
    collection = _get_collection()
    if collection.count() == 0:
        raise HTTPException(status_code=400, detail="Workspace is empty. POST to /upload first.")

    hits = _query_workspace(collection, request.topic, k=6)
    context = "\n\n".join(text for text, _, _ in hits)

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
