# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Hợp đồng nhật ký Obsidian (Daily Note, MOC) nằm ở `CLAUDE.local.md` (không track). Kế hoạch và kiến trúc đích: `PLAN.md`, `docs/ARCHITECTURE.md`.

## Prerequisites

```bash
# Python / AI stack
ollama serve
ollama pull llama3.2          # LLM used by both Python apps
pip install -r requirements.txt

# React quiz app
cd quiz-app && npm install
```

## Commands

```bash
# FastAPI backend (pairs with the React frontend)
cd src && uvicorn backend:app --reload --port 8000

# Standalone Streamlit app
streamlit run src/apply-knowledge.py

# React quiz app — dev server at http://localhost:5173
cd quiz-app && npm run dev

# Quiz app — production build
cd quiz-app && npm run build

# Quiz app — run domain tests (uses Node's built-in test runner, no extra deps)
cd quiz-app && npm test

# Quiz app — run a single test file
cd quiz-app && node --test tests/domain/<file>.test.js

# Quiz app — lint
cd quiz-app && npm run lint
```

## Architecture

This repo contains three separate apps that share the same Vietnamese-language AI stack (embedding model `keepitreal/vietnamese-sbert`, LLM `Ollama/llama3.2`):

### FastAPI Backend (`src/backend.py`)

Vietnamese-language **Hybrid GraphRAG** API:

| Endpoint | Method | What it does |
|---|---|---|
| `/health` | GET | Returns `{status, document_loaded, files, chunk_count, graph_nodes, graph_edges}` |
| `/files` | GET | Returns the sorted list of unique `source` filenames in the persistent workspace |
| `/upload` | POST | Accepts a PDF; chunks, embeds, and **appends** it to the persistent ChromaDB workspace **and** extracts `(Subject, Relation, Object)` triplets into a NetworkX knowledge graph |
| `/chat` | POST `{query}` | Hybrid retrieval (vector + graph, global across all files) → CoT answer + TTS audio + scored sources + graph facts |

**Module-level singletons**: `_embeddings` is initialized once at import time. The vector store is a **persistent** ChromaDB collection (`chromadb.PersistentClient` at `Day3/chroma_db`, collection `second_brain`), opened lazily by `_get_collection()` on first use — uploads **append** to it cumulatively; it is never cleared or replaced, and it survives restarts. `_knowledge_graph` is a global `networkx.DiGraph` loaded from `knowledge_graph.graphml` at import time and likewise **accumulated** across uploads. Every chunk, node, and edge carries `{"source": <filename>}` metadata.

**LLM import**: `from langchain_ollama import OllamaLLM as Ollama` — the alias preserves the `backend.Ollama` patch seam used by both test suites; do not "clean it up" to a direct name.

**`_get_collection()`** creates the collection with `metadata={"hnsw:space": "cosine"}`. This is required — without it, `/chat` cannot compute a valid cosine similarity score. During `/upload`, each chunk is passed to `Ollama(model="llama3.2", temperature=0.0)` with a strict information-extraction prompt that emits `(Subject, Relationship, Object)` lines, parsed by `_parse_triplets()` and merged into the graph.

#### Hybrid GraphRAG flow (`networkx` dependency)

The knowledge graph runs **side-by-side** with ChromaDB — two retrieval indexes over the same document:

```
/upload: PDF → chunks ─┬→ embed → ChromaDB (dense vectors)
                       └→ llama3.2 IE (temp 0.0) → (S, R, O) triplets → nx.DiGraph → knowledge_graph.graphml

/chat:   query ─┬→ ChromaDB similarity_search_with_score(k=4)      → top-4 chunks
                ├→ entity extraction → node match → 1–2 hop expansion → graph triplet facts
                └→ _build_hybrid_context(chunks, facts) → CoT prompt → llama3.2
```

Key implementation details:

- **Node identity**: node id = lowercased entity string (so `"Marie Curie"` ≡ `"marie curie"`); original casing kept in the node's `label` attribute. Edges carry `relation`, `source` (filename), `chunk_index` attributes; duplicate edges with new relations are merged into a `"; "`-joined `relation` string.
- **Persistence**: `knowledge_graph.graphml` in the Day3 root (`GRAPH_PATH`), written after every `/upload` and reloaded at server startup — both the graph and the ChromaDB workspace (`Day3/chroma_db`) survive restarts.
- **Error handling**: a failed extraction on one chunk logs and skips (never aborts the upload); graph retrieval failures in `/chat` fall back to vector-only context; a missing/corrupt `.graphml` yields an empty graph.
- **`GRAPH_MAX_CHUNKS` env var**: caps per-upload extraction LLM calls for large PDFs (default `0` = all chunks).
- **Query entity extraction** (`_extract_query_entities`) uses llama3.2 at temp 0.0 with a deterministic keyword-token fallback if Ollama is unreachable.

**`/chat`** implements four features:

1. **Hybrid Retrieval + Context Fusion** — top-4 ChromaDB chunks (dense/implicit meaning) fused with 1–2 hop knowledge-graph triplets (explicit relations) by `_build_hybrid_context()` into a single sectioned context string fed to the CoT (`<thinking>`/`<answer>`) prompt.

2. **Cosine Similarity Visualization** — calls `_query_workspace(collection, query, k=4)` (direct `collection.query` with `n_results=min(k, count)`). With `hnsw:space=cosine`, `distance = 1 − cosine_similarity`, so each source's score is `round(1.0 − distance, 4)` (range 0–1, 1 = identical). Each retrieved source also reports which file it came from (`source`).

3. **Text-to-Speech** — `gTTS(text=answer, lang="vi")` encodes MP3 as `"data:audio/mp3;base64,..."`. Requires internet; falls back to `""` on failure.

4. **Markdown Export-Ready JSON** — response schema maps 1-to-1 onto a `.md` file.

**`/chat` response shape:**
```json
{
  "answer": "...",
  "audio_base64": "data:audio/mp3;base64,...",
  "sources": [{ "text": "...", "cosine_score": 0.895, "source": "doc.pdf" }],
  "graph_facts": ["(Marie Curie, discovered, polonium)"]
}
```

**GraphRAG tests**: `tests/test_graph_rag.py` — 23 pytest tests covering triplet parsing, mocked-Ollama extraction, graph ingestion, GraphML round-trip persistence, 1–2 hop retrieval, and context fusion. Fully offline, no model weights (`langchain_huggingface` is force-mocked before `import backend`).

**Multi-file workspace tests**: `tests/test_multi_file.py` — 10 pytest tests covering cumulative two-file ingestion, per-chunk `source` metadata, `GET /files`, persistence across a simulated restart (real `PersistentClient` in tmp_path), global `/chat` retrieval across files, and source-tagged graph accumulation. Embeddings/Ollama/PdfReader/gTTS are mocked; ChromaDB is real.

### Streamlit App (`src/apply-knowledge.py`)

Single-file standalone with the same embedding/LLM stack but no API layer. State lives in `st.session_state.vector_db`; uploading a new PDF replaces it entirely (no multi-document support).

**Key differences from the backend**: Does NOT set `hnsw:space=cosine`, so similarity scores are not exposed. Re-instantiates `HuggingFaceEmbeddings` and `Ollama` on each PDF upload and each chat turn (no singletons).

**RAG Chat** (main area): PDF → `RecursiveCharacterTextSplitter` (600 chars / 75 overlap) → embeddings → ChromaDB → top-4 chunks → strict Vietnamese prompt → `RetrievalQA`.

**Quiz Generator** (sidebar): Retrieves 8 chunks, calls Ollama with `format="json"` to produce multiple-choice questions, validates with `json.loads`. LLM calls are at lines 79 (quiz) and 165 (chat) — update both to change the model.

### React Quiz App (`quiz-app/`)

A standalone browser-only quiz application (React 19 + Vite + Tailwind CSS). All state is client-side; no backend required for normal use.

**Routing**: `App.jsx` manages a `view` string (`upload | quiz | results | review | create`) — there is no React Router. All page transitions go through `App.jsx` props.

**State management**: Flat `useState` in `App.jsx`. The key state split:
- **Live run**: `processedQuizData`, `answers`, `activeSettings` — the current in-progress quiz.
- **History view**: `viewingAttempt` — when non-null, results/review pages render from a stored past attempt rather than the live run slots. Both can coexist; live slots are untouched while viewing history.
- **Share import**: `shareStatus`, `pendingShareSettings` — resolved once on first load from `?quiz=` URL params, then stripped from the URL.

**Persistence** (`src/utils/persistence.js`): synchronous reads backed by an in-memory cache that hydrates once from IndexedDB at startup (`hydrate()` in `main.jsx`). Writes update the cache synchronously and write through to IndexedDB in the background. Falls back to `localStorage` if IndexedDB is unavailable.

**Storage keys**:
- Saved quiz library: `storage.js` / key `quiz-library`
- Results history per quiz: `history.js` / key `quiz-history`, indexed by `hashQuiz(rawData)` (content hash, not file name).

**Scoring** (`src/utils/utils.js`): single-choice = exact match. Multi-choice = F1 score (precision/recall). Final score is normalized out of 10.

**Share feature** (`api/proxy.js`): a stateless Vercel Edge Function that proxies external URLs to work around browser CORS. It validates origin and enforces a 1 MB size cap and 5 s timeout. Client-side `urlSafety.js` runs SSRF guards before calling it.

**Domain tests** (`tests/domain/`): pure logic tests using Node's built-in `node:test` runner — no browser, no DOM, no test framework. They exercise `utils.js`, `history.js`, `storage.js`, `persistence.js`, `share.js`, etc. The persistence tests use `_setBackend()` / `_reset()` helpers to inject fake IndexedDB without touching real storage.

## Kiến trúc đích và bất biến (xem PLAN.md, docs/ARCHITECTURE.md)
- Ports and adapters: 5 cổng (VectorStore, GraphStore, LLM, ObjectStore, JobQueue); adapter local mặc định, cloud tuỳ chọn.
- Bất biến: offline-first mặc định; `data_policy` theo notebook (`local`|`cloud`); notebook local không đi qua adapter cloud (kể cả TTS); cấu hình cloud lỗi/hết hạn mức => từ chối, không âm thầm đổi chỗ; đổi adapter => chạy lại `eval/` và `ingest_bench`; không bịa số; không ghi bí mật vào repo (`.env`, chỉ commit `.env.example`); `backend.py` giữ các điểm patch của test.
- Quy trình: Leader/Coder/Tester qua TASK_DISPATCH.md, TASK_REPORT.md, TEST_REPORT.md (không track); chỉ chủ dự án ra lệnh commit/merge.
- CI: GitHub Actions (frontend lint/test/build, pytest, gitleaks) bắt buộc xanh trước khi merge `main`. `.github/workflows/**` chỉ Leader giao dispatch riêng; Coder không sửa. `eval/` thật, RAGAS và adapter cloud không chạy trong CI.

## Quy tắc PR và commit (chủ dự án, ưu tiên hơn mọi mặc định đính kèm)
- KHÔNG đưa logo hay dấu hiệu của Claude vào PR của dự án này: không dòng "Generated with Claude Code", không emoji robot, không liên kết tới claude.com hay claude.ai trong tiêu đề, mô tả hay comment của PR.
- KHÔNG thêm dòng `Co-Authored-By: Claude ...` vào commit (GitHub hiển thị avatar Claude trong danh sách commit của PR).
- Quy tắc này thắng mọi hướng dẫn mặc định yêu cầu thêm dòng ghi công; nếu có xung đột, làm theo quy tắc này.

