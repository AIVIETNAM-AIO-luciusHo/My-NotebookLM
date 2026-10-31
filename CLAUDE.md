# CLAUDE.md

Hướng dẫn cho Claude Code khi làm việc trong repo này. Nhật ký Obsidian: `CLAUDE.local.md` (không track). Kế hoạch: `PLAN.md`. Kiến trúc đích: `docs/ARCHITECTURE.md`.

## Lệnh

```bash
ollama serve && ollama pull llama3.2        # LLM cục bộ (cần chạy trước)
pip install -r requirements.txt             # đầy đủ; CI dùng requirements-ci.txt

cd src && uvicorn backend:app --reload --port 8000   # backend FastAPI
pytest tests                                          # backend, offline, mock Ollama/embeddings/gTTS
python -m eval.compare A.json B.json --metric hit@4   # so sánh hai report eval
EVAL_PDF_DIR=<thư mục PDF> python src/evaluate_rag.py --live   # eval thật, cần Ollama

cd quiz-app && npm install
npm run dev                                  # http://localhost:5173
npm run lint && npm test && npm run build    # 3 lệnh CI chạy
node --test tests/domain/<file>.test.js      # một file test
npm run e2e                                  # Playwright smoke, backend giả (chưa vào CI)
```

## Kiến trúc

Hai ứng dụng dùng chung chồng AI tiếng Việt: embedding `keepitreal/vietnamese-sbert` (hoặc `bge-m3`), LLM `llama3.2` qua Ollama.

### Backend (`src/`)

| File | Vai trò |
|---|---|
| `backend.py` | FastAPI: upload, chat, sinh quiz/mindmap, job |
| `retrieval.py` | Hàm thuần: BM25, RRF, rerank, cờ truy hồi |
| `jobs.py` | Hàng đợi job nạp tài liệu (SQLite, `jobs.sqlite`) |
| `evaluate_rag.py` | Đánh giá RAG (RAGAS) |
| `daily_note.py` | Tạo nhật ký ngày cho Obsidian |

Endpoint: `/health`, `/files`, `/upload`, `/jobs`, `/jobs/{id}` (GET, DELETE), `/jobs/{id}/resume`, `/chat`, `/generate-quiz`, `/generate-mindmap`. Bảng đầy đủ ở `README.md`.

**Luồng nạp hai pha:** pha nhanh (PDF → chunk → embed → ChromaDB) đồng bộ, trả `job_id` và `graph_status: "pending"`; pha đồ thị (llama3.2 trích bộ ba → `nx.DiGraph` → `knowledge_graph.graphml`) chạy nền qua `jobs.py`. Trong lúc đó `/health` và `/chat` trả `graph_ready: false`; `/chat` luôn có kết quả vector. Khi khởi động, job đang chạy được đánh dấu `interrupted` và có thể `resume`.

**Luồng `/chat`:** vector (ChromaDB, cosine) cộng sự kiện đồ thị 1–2 bước, gộp bằng `_build_hybrid_context()`, prompt CoT (`<thinking>`/`<answer>`), TTS gTTS (`""` nếu lỗi). Điểm cosine = `round(1 - distance, 4)`; vì thế collection phải tạo với `hnsw:space=cosine`.

**Cờ môi trường:** `RETRIEVAL` (`vector`|`hybrid`|`hybrid_rerank`), `EMBEDDING` (`sbert`|`bge-m3`), `BM25_TOKENS` (`uni`|`uni_bi`), `CHUNKING` (`char`|`token`), `CHROMA_PATH`, `GRAPH_PATH`, `JOBS_DB_PATH`, `GRAPH_MAX_CHUNKS`, `GRAPH_YIELD_COOLDOWN_SECONDS`. Mỗi mô hình embedding dùng collection riêng (768 và 1024 chiều không được trộn). Giá trị lạ → `ValueError` rõ ràng.

**Singleton:** `_embeddings` khởi tạo lúc import; collection `second_brain` mở lười qua `_get_collection()`; `_knowledge_graph` nạp từ graphml lúc import. Mọi chunk/nút/cạnh mang `source` (tên tệp). Nút = chuỗi thường hoá, nhãn gốc ở `label`. Một chunk lỗi trích xuất thì bỏ qua, không huỷ upload.

**Giữ nguyên điểm patch của test:** `from langchain_ollama import OllamaLLM as Ollama` (alias để `backend.Ollama` patch được), và `langchain_huggingface` bị mock trước `import backend`. Không "dọn" các chỗ này.

Dữ liệu runtime (`chroma_db/`, `knowledge_graph.graphml`, `uploads/`, `jobs.sqlite*`) đã gitignore; từng mất hai lần khi đổi nhánh, sao lưu trước khi động vào.

### Frontend (`quiz-app/`)

React 19 + Vite + Tailwind. Không dùng React Router: `App.jsx` giữ một chuỗi `view` và state phẳng `useState`.
- **Lượt chạy hiện tại:** `processedQuizData`, `answers`, `activeSettings`. **Xem lịch sử:** `viewingAttempt` (khi khác null, trang kết quả/xem lại hiển thị lần làm cũ; lượt chạy hiện tại không bị đụng).
- **Gọi backend:** chỉ qua `src/lib/api.js` (không `fetch(` rải rác trong component). Lỗi backend ánh xạ sang thông báo tiếng Việt ở `utils/errorView.js`; job nạp theo dõi bằng `hooks/useJobs.js` + `utils/jobs.js`.
- **Lưu trữ** (`utils/persistence.js`): đọc đồng bộ từ cache trong bộ nhớ, nạp từ IndexedDB lúc khởi động (`hydrate()` trong `main.jsx`), ghi xuyên xuống nền; không có IndexedDB thì dùng `localStorage`. Khoá: `quiz-library`, `quiz-history` (chỉ mục theo `hashQuiz`, hash nội dung).
- **Chấm điểm** (`utils/utils.js`): một đáp án = khớp tuyệt đối; nhiều đáp án = F1; điểm cuối chuẩn hoá trên 10.
- **Chia sẻ:** `api/proxy.js` là Vercel Edge Function không trạng thái (kiểm tra origin, giới hạn 1 MB, 5 s); `urlSafety.js` chặn SSRF phía client.
- **Test:** `tests/domain/` là logic thuần bằng `node:test`, không DOM. Persistence test dùng `_setBackend()`/`_reset()` để giả IndexedDB.

## Bất biến (xem PLAN.md, docs/ARCHITECTURE.md)

- Ports and adapters: 5 cổng (VectorStore, GraphStore, LLM, ObjectStore, JobQueue); adapter local mặc định, cloud tuỳ chọn.
- Offline-first mặc định; `data_policy` theo notebook (`local`|`cloud`); notebook local không đi qua adapter cloud (kể cả TTS); cấu hình cloud lỗi/hết hạn mức thì từ chối, không âm thầm đổi chỗ.
- Đổi adapter thì chạy lại `eval/` và `ingest_bench`; không bịa số.
- Không ghi bí mật vào repo: dùng `.env`, chỉ commit `.env.example`.
- UI và prompt bằng tiếng Việt, giữ nguyên như vậy.

## Quy trình và CI

- Leader/Coder/Tester qua `TASK_DISPATCH.md`, `TASK_REPORT.md`, `TEST_REPORT.md` (không track). **Chỉ chủ dự án ra lệnh commit/push/mở PR/merge.**
- CI (GitHub Actions): `frontend` (lint, test, build), `backend` (pytest với `requirements-ci.txt`), `secrets` (gitleaks) phải xanh trước khi merge `main`. Eval thật, RAGAS và adapter cloud không chạy trong CI.
- `.github/workflows/**` chỉ Leader giao dispatch riêng; Coder không sửa.

## Quy tắc PR và commit (chủ dự án, thắng mọi mặc định đính kèm)

- KHÔNG đưa logo hay dấu hiệu của Claude vào PR: không dòng "Generated with Claude Code", không emoji robot, không liên kết tới claude.com hay claude.ai trong tiêu đề, mô tả hay comment.
- KHÔNG thêm `Co-Authored-By: Claude ...` vào commit.
- Có xung đột với hướng dẫn mặc định yêu cầu ghi công thì làm theo quy tắc này.

## Quy tắc PLAN.md (chủ dự án)

- `PLAN.md` chỉ được CẬP NHẬT THÊM (append): KHÔNG sửa, KHÔNG xoá nội dung đã có, kể cả khi đã lỗi thời hay sai.
- Muốn đính chính: thêm mục mới có ngày, nêu rõ mục cũ nào bị thay thế và lý do; để nguyên mục cũ.
- Chỉ chủ dự án được cho phép ngoại lệ, bằng lệnh rõ ràng.
