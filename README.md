# My-NotebookLM

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-LLM-black?style=for-the-badge)

Bản tái tạo NotebookLM chạy cục bộ cho tiếng Việt: nạp PDF một lần, rồi **hỏi đáp có trích nguồn**, **sinh đề trắc nghiệm** và **vẽ sơ đồ tư duy** từ chính tài liệu đó. Backend FastAPI dùng **Hybrid GraphRAG** (ChromaDB + đồ thị tri thức NetworkX); giao diện là ứng dụng React trong `quiz-app/`.

## Quyền riêng tư

Mặc định mọi thứ chạy trên máy: vector trong ChromaDB, đồ thị trong NetworkX (`.graphml`), LLM qua Ollama. Hai ngoại lệ:
- **TTS (gTTS):** `/chat` gửi văn bản câu trả lời tới Google để tạo giọng đọc; lỗi thì `audio_base64` rỗng.
- **Tải mô hình lần đầu:** `keepitreal/vietnamese-sbert` (HuggingFace) và `llama3.2` (Ollama) tải một lần rồi chạy từ bộ nhớ đệm.

Chính sách `data_policy` theo notebook mới là kế hoạch (`PLAN.md`), chưa cài trong mã.

## Cách hoạt động

- **Nạp hai pha:** `/upload` đọc PDF, chia chunk, embed, ghi ChromaDB rồi trả lời ngay kèm `job_id`. Việc trích bộ ba bằng LLM để xây đồ thị chạy nền; theo dõi qua `/jobs`. Trong lúc đó `graph_ready` là `false`, `/chat` vẫn trả lời bằng vector.
- **Hỏi đáp:** top-4 chunk (cosine) cộng sự kiện đồ thị 1–2 bước, trả lời bằng suy luận chuỗi, kèm nguồn, điểm cosine, `graph_facts` và audio.
- **Không gian đa tệp:** mỗi lần upload *nối thêm* vào `chroma_db/` và đồ thị; còn nguyên sau khi khởi động lại.

| Endpoint | Method | Chức năng |
|---|---|---|
| `/health` | GET | Trạng thái, số chunk, số nút/cạnh, `graph_ready` |
| `/files` | GET | Tệp nguồn trong workspace |
| `/upload` | POST | Nạp PDF (pha nhanh đồng bộ, đồ thị chạy nền) |
| `/jobs`, `/jobs/{id}` | GET | Danh sách / trạng thái job |
| `/jobs/{id}/resume` | POST | Chạy lại pha đồ thị của job gián đoạn hoặc lỗi |
| `/jobs/{id}` | DELETE | Xoá bản ghi job đã kết thúc |
| `/chat` | POST `{query}` | Hỏi đáp lai vector + đồ thị |
| `/generate-quiz` | POST | Sinh đề trắc nghiệm |
| `/generate-mindmap` | POST | Sinh sơ đồ tư duy Mermaid |

## Chạy dự án

```bash
ollama serve && ollama pull llama3.2
pip install -r requirements.txt

cd src && uvicorn backend:app --reload --port 8000     # backend
cd quiz-app && npm install && npm run dev              # giao diện, http://localhost:5173
```

Biến môi trường tuỳ chọn: `RETRIEVAL` (`vector`|`hybrid`|`hybrid_rerank`), `EMBEDDING` (`sbert`|`bge-m3`), `CHUNKING` (`char`|`token`), `CHROMA_PATH`, `GRAPH_PATH`, `JOBS_DB_PATH`, `GRAPH_MAX_CHUNKS`. Chi tiết trong `CLAUDE.md`. Dữ liệu runtime (`chroma_db/`, `knowledge_graph.graphml`, `jobs.sqlite`) đã nằm trong `.gitignore`.

## Kiểm thử và CI

```bash
pytest tests                                              # backend, offline
cd quiz-app && npm run lint && npm test && npm run build  # frontend
```

GitHub Actions chạy `frontend`, `backend`, `secrets` (gitleaks) trên PR vào `main`; CI không cần Ollama và không chạy eval thật.

## Cấu trúc

```text
src/        backend.py, retrieval.py, jobs.py, evaluate_rag.py
quiz-app/   React 19 + Vite + Tailwind
eval/       công cụ đo và so sánh
tests/      pytest
docs/       ARCHITECTURE.md, MVP_HUONG_DAN.md, sơ đồ
PLAN.md     kế hoạch (chỉ append)
```
