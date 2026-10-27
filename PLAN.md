# PLAN — My-NotebookLM

> Đã được chủ dự án duyệt ghi vào repo ngày 2026-10-27 (chưa commit). Tài liệu sống: sửa trực tiếp, ghi lý do vào mục Nhật ký. Toàn cảnh có sơ đồ: `docs/ARCHITECTURE.md`; sơ đồ riêng: `docs/architecture/*.mmd`.

## 1. Mục tiêu
Tái tạo NotebookLM chạy cục bộ; R&D thực chiến, portfolio kỹ thuật, dùng cá nhân/nhóm nhỏ. Vấn đề trung tâm: giảm thời gian chờ sau upload, đọc tài liệu nhanh hơn, đi từ local sang cloud có kiểm soát. Ngân sách: 0 USD/tháng.

## 2. Bất biến (không đổi nếu chưa hỏi chủ dự án)
1. Offline-first mặc định: Chroma, NetworkX, Ollama, đĩa, hàng đợi trong tiến trình.
2. `data_policy` theo TỪNG notebook: `local` | `cloud`. Notebook local KHÔNG BAO GIỜ đi qua adapter cloud (kể cả TTS). Không tự di chuyển dữ liệu giữa hai chế độ.
3. Cấu hình cloud thiếu/lỗi hoặc chạm hạn mức: từ chối và báo lỗi rõ; không âm thầm chuyển dữ liệu; không tự trả phí.
4. Mỗi lần đổi adapter: chạy lại `eval/` và `ingest_bench`; so sánh ghép cặp trên cùng câu hỏi.
5. Không bịa số; số liệu phải có xuất xứ hoặc ghi "chưa kiểm chứng". Không lưu bí mật trong repo (dùng `.env`, chỉ commit `.env.example`).
6. Không dịch vụ tính phí. Chỉ gói miễn phí Groq / Pinecone Serverless / Neo4j AuraDB, sau khi tra tài liệu chính thức (ghi nguồn + ngày tra).
7. TTS: gTTS chỉ bật ở notebook cloud; notebook local mặc định không có TTS.
8. `backend.py` là mặt tiền: giữ các điểm patch của test (`backend.Ollama`, mock `langchain_huggingface` trước khi import).

## 3. Kiến trúc (xem docs/architecture/target.mmd, current.mmd)
5 cổng: VectorStore, GraphStore, LLM, ObjectStore, JobQueue; adapter local (mặc định) và cloud/học. Embedding luôn chạy cục bộ (sbert 768 chiều); cloud chỉ thấy vector, metadata và (khi trích triplet) văn bản đoạn gửi tới Groq.

## 4. Các pha (mỗi pha: công nghệ gắn kèm + thí nghiệm kiểm chứng)
| Pha | Nội dung | AC chính (lệnh -> kết quả đo được) | Công nghệ gắn kèm / thí nghiệm | Phụ thuộc |
|---|---|---|---|---|
| P0 | Chủ dự án tick `eval/review_sample.md`; đo độ trễ `/chat` rảnh (>=10 lần); golden >=100 câu hoặc quy ước ghép cặp; sửa `.gitignore` (thêm `.env`, `CLAUDE.local.md`) | `grep -c "^- \[x\]" eval/review_sample.md` >= 5; file độ trễ mean/sd/p95; hai lần nạp đồng bộ cho độ lệch số triplet | độ nhiễu nền của trích triplet | người dùng |
| P0.5 | CI GitHub Actions (frontend lint/test/build; backend pytest; gitleaks); branch protection `main` | CI-1..CI-5 (mục 6) | `pytest` gói rút gọn (giả thuyết, cần kiểm) | P0 |
| P0.7 | Thí nghiệm cắt đoạn theo token: đổi hàm đo độ dài của splitter sang token PhoBERT (trần ~230 để chừa token đặc biệt), nạp lại 3 PDF vào Chroma TẠM, chạy `eval --live` | trước/sau: hit@4/6/8, MRR, cover@8 multi-hop, so sánh GHÉP CẶP trên 30 câu; tỉ lệ đoạn >256 token = 0%; báo chi phí (số đoạn, thời gian embedding). Chỉ đổi mặc định nếu cải thiện đo được; nếu có, ĐỔI BASELINE và ghi vào PLAN | `RecursiveCharacterTextSplitter.from_huggingface_tokenizer`; (tuỳ chọn, tách thí nghiệm riêng) tách từ tiếng Việt trước PhoBERT | P0.5 |
| P1 | Nạp hai pha: `POST /upload` trả 202 + job_id; pha nhanh; một worker pha chậm nhường /chat; bảng `jobs` SQLite (job_id, status, progress, error); khoá đồ thị; `graph_ready`; endpoint trạng thái job | xem mục 5 | `ThreadPoolExecutor` / `run_in_executor` + SQLite (không dùng `asyncio.create_task` trần, vì việc nặng vẫn chặn event loop) | P0 |
| P1.5 | Thực thể Notebook: `notebook_id`, `data_policy`, dữ liệu tách theo notebook, TTS theo policy; UI Notebook + trạng thái nạp + chế độ bảo mật | test spy: notebook local gọi adapter cloud -> lỗi; dữ liệu A không lẫn B; endpoint trạng thái job được UI hiển thị | spike shadcn/ui (xem D6) chỉ làm tại đây, vì chỉ lúc này mới có UI mới cần | P1 |
| P2 | Tách 5 cổng/adapter không đổi hành vi; `backend.py` là mặt tiền | `pytest tests/contract -q` 0 failed; `eval` byte-giống baseline | contract test mỗi cổng | P1.5 |
| P3 | Adapter Groq cho cổng LLM; tra giới hạn/mô hình chính thức (ghi nguồn + ngày) | đo giây/đoạn triplet, chất lượng triplet, độ trễ /chat, đo CẢ khi chạm hạn mức (đóng an toàn); chỉ giữ nếu cải thiện đo được | Groq (chưa đo); thử thêm qwen2.5 chỉ nếu vừa 6 GB VRAM | P2 |
| P4 | ObjectStore: đĩa `uploads/` và MinIO (boto3); JobQueue: Redis + Celery như adapter học | contract test chạy cho cả hai adapter; upload thấy lại được PDF gốc | MinIO, Redis, Celery | P2 |
| P5 | Pinecone Serverless (cosine, 768 chiều, filter `notebook_id`+`source`), Neo4j AuraDB | đo lại baseline BẰNG so sánh ghép cặp; không đòi tất định | tra giới hạn gói miễn phí | P2, P0 |
| P6 | Hybrid (BM25+vector, RRF) + reranker (đo trên baseline sau P0.7) | hit@4, cover@8 multi-hop so baseline, ghép cặp | BM25, cross-encoder | P0 |
| P7 | Slide sửa được (JSON có phiên bản, citation từng ý, xuất .pptx/PDF) | mọi bullet có citation; sửa một slide không đụng slide khác | `python-pptx` hoặc pandoc (chưa kiểm có sẵn) | P6 |
| P8 | Quiz đa dạng (Đúng/Sai, điền khuyết, nhiều đáp án, kiểm lại đề) | schema + kiểm lại đề; test 422 cho đầu vào sai (hành vi 422 có sẵn) | `pytest-asyncio` chỉ nếu viết test async | P2 |
| P9 | Docker Compose (backend, frontend, Ollama, MinIO, Redis) + CD (frontend quiz-only với `VITE_BACKEND_URL`; ảnh Docker lên GHCR khi gắn tag); KHÔNG đưa backend lên cloud | `docker compose up` chạy trên máy sạch; GPU vào container Ollama; thời gian khởi động và RAM được đo; volume giữ `chroma_db`, graphml, uploads, SQLite | WSL2 GPU passthrough, tải mô hình lần đầu (llama3.2 ~2 GB, sbert) | P0.5, P2 |

**Công nghệ ĐÃ có, không tạo việc tích hợp lại:** Tailwind (`^3.4.13`), Lucide (`^0.553.0`), Mermaid (`^11.16.0`), `MindmapVisualizer.jsx`/`MindmapStudio.jsx` (kiểm trong `quiz-app/package.json` và thư mục `pages/`).

## 5. P1 — AC chi tiết (đã tinh chỉnh so với bản đề xuất; lý do ghi bên cạnh)
| AC | Kiểm chứng | Mong đợi | Lý do tinh chỉnh |
|---|---|---|---|
| P1-1 | script >=5 lần: T_ready = từ bắt đầu POST /upload (PDF 27 trang) đến khi job pha nhanh xong | mean và sd được báo; mean <= 10 s | dự đoán từ ingest_bench ~3,3 s (chưa đo trên pha nhanh thật); đo "sẵn sàng hỏi", không phải "upload trả về" |
| P1-2 | /chat ngay sau T_ready, lặp >=5 lần, CẢ KHI nền đang chạy và KHI rảnh | báo hai bộ mean/sd/p95; ngưỡng p95(nền chạy) <= 1,5x p95(rảnh) chốt SAU P0 | /chat chưa đo, ngưỡng 10 s của bản đề xuất là đoán; đo trường hợp xấu nhất tranh GPU |
| P1-3 | số triplet nạp hai pha so với nạp đồng bộ | trong ±10% NẾU hai lần đồng bộ lệch nhau nhỏ hơn 10% (đo ở P0) | nền LLM có thể không tất định; không đặt ngưỡng trước khi biết nhiễu |
| P1-4 | `python src/evaluate_rag.py --live` rồi `cmp` với report baseline | byte-giống | P1 không đổi đường truy hồi nên chặt hơn "tụt <=2/30" |
| P1-5 | `pytest tests -q` | 0 failed, test mới >= 8 (job, khoá, huỷ, graph_ready) | giữ |
| P1-6 | kill tiến trình giữa pha chậm, khởi động lại | số đoạn trong Chroma không đổi; job ở trạng thái `interrupted`/`resumable`; /chat vẫn trả lời | bảng job bền; không mất dữ liệu |
| P1-7 | test song song: /chat liên tục trong khi worker ghi đồ thị | 0 lỗi, 0 500; `graph_ready=false` rồi `true` | NetworkX là biến toàn cục |

## 9. Điểm quyết định chờ chủ dự án
- D1 [ĐÃ XONG 2026-10-27]: 6/6 ô `eval/review_sample.md` được tick bởi Leader THEO LỆNH của chủ dự án, dựa trên đối chiếu của Leader với trang PDF (chủ dự án không tự đọc lại từng câu). `golden.jsonl` giữ `reviewed:false` vì `tests/test_golden_schema.py:40` bắt buộc; 24/30 câu còn lại chưa ai duyệt.
- D2 [ĐÃ CHỐT 2026-10-27]: AC P1-2 = so sánh GHÉP CẶP theo câu (cùng 10 câu golden gradient đo lúc rảnh và lúc nền chạy, tính tỉ số median theo từng câu rồi lấy median): median nền <= 1,5x median rảnh. Ngưỡng 1,5 là đề xuất, chưa có dữ liệu lúc nền chạy; nếu P1 cho thấy không khả thi thì ghi lại và đề xuất lại, không âm thầm nới.
- D3 [ĐÃ CHỐT 2026-10-27]: so sánh ghép cặp McNemar trên 30 câu bằng `eval/compare.py` trước; chỉ mở rộng golden khi một so sánh thật sự cần độ nhạy cao hơn.
- D12 [ĐÃ CHỐT 2026-10-27]: CI backend dùng `requirements-ci.txt` rút gọn (không torch/sentence-transformers/ragas/datasets), ghim đúng bộ đã thử (kèm `httpx<0.28`); `requirements.txt` giữ nguyên (sửa cho khớp môi trường thật là việc riêng, vì file đó đang lệch: ghi `fastapi==0.110.0`/`langchain==0.3.7` nhưng máy dev chạy `fastapi 0.138.1`/`langchain 1.3.11`, và thiếu `httpx` mà `TestClient` cần).
- D13 [ĐÃ CHỐT]: branch protection cho `main` KHÔNG cho admin bỏ qua (chủ dự án cũng phải qua PR và CI xanh).
- D14 [ĐÃ CHỐT]: CI chạy cho PR vào `main` và push vào `main`, không chạy trên mọi nhánh.
- D4: có cần MinIO (mở PDF tại trang trích dẫn) hay hoãn.
- D5: giữ Groq sau P3 hay không (theo số đo).
- D6 [ĐÃ CHỐT 2026-10-27]: spike shadcn/ui chỉ tại P1.5 khi có UI Notebook; AC: Modal/Button hiện có thay bằng bản shadcn, `npm run build` và 115 test vẫn xanh, kích thước bundle được báo trước/sau.
- D7 [ĐÃ CHỐT]: cắt đoạn theo token làm ở P0.7 (sau P0.5, trước P1); phải nạp lại dữ liệu cũ nếu đổi mặc định.
- D8 [ĐÃ CHỐT]: giữ `chroma_db/` và `knowledge_graph.graphml` ở gốc repo; thêm `uploads/` và `jobs.sqlite` cạnh đó; Compose mount đúng các đường dẫn này; sao lưu trước mọi thao tác nhánh/di chuyển.

## 6. P0.5 — CI (AC)
| AC | Kiểm chứng | Mong đợi |
|---|---|---|
| CI-1 | mở PR thử | workflow xanh; báo thời gian từng job (chưa biết, sẽ đo) |
| CI-2 | PR cố ý phá một test | workflow đỏ, merge bị chặn |
| CI-3 | PR cố ý thêm chuỗi giống khoá API (đã xoá sau khi thử, không dùng khoá thật) | gitleaks đỏ |
| CI-4 | branch protection `main` yêu cầu job `ci` xanh | không merge được khi đỏ |
| CI-5 | pytest trong CI chạy với bộ phụ thuộc rút gọn | số test chạy bằng số test local (74 hoặc hơn); nếu không chạy được thì ghi nguyên nhân và dùng bộ đầy đủ + cache |
Đã thử (2026-10-27, máy dev, Python 3.12.3, venv rút gọn 639 MB, cài 100 s): `pytest tests -q` = 88 passed trong 29 s khi thêm `httpx<0.28`; không có `httpx<0.28` thì `starlette 0.36.3` (kéo bởi `fastapi==0.110.0`) lỗi `TypeError` ở `testclient.py:429`. Chưa kiểm trên runner GitHub. Quy tắc: `.github/workflows/**` KHÔNG nằm trong allowlist của Coder; chỉ dispatch riêng của Leader được sửa (tránh CI xanh giả). `eval/` đo thật, RAGAS, adapter cloud KHÔNG chạy trong CI (cần mô hình, Ollama, khoá); chỉ chạy tay. Khoá API không bao giờ đưa vào PR từ fork.

## 7. Phát hiện kiểm chứng được khi lập bản đồ công nghệ (2026-10-27)
- Tokenizer của `keepitreal/vietnamese-sbert` là `PhobertTokenizer`; `max_seq_length` 256. Chia theo 600 ký tự + 75 chồng (như `_chunk_pages`) rồi đếm token (kèm token đặc biệt): gradient27 24/119 đoạn (20,2%) vượt 256, max 373; prob55 20/137 (14,6%), max 364; kmeans53 29/142 (20,4%), max 332 [lệnh chạy bằng `AutoTokenizer.from_pretrained(..., local_files_only=True)`]. Phần vượt bị cắt khi embedding (chưa đo ảnh hưởng lên hit@k).
- Repo không tách từ tiếng Việt trước khi đưa vào sbert dựa trên PhoBERT; ảnh hưởng chưa đo.
- `backend.py` không có `503` (grep); `422` có sẵn (`:513`, `:671`, `:675`) cộng 422 tự động của FastAPI/Pydantic cho body sai. `requirements.txt` không có `pytest-asyncio`; test hiện đồng bộ.
- Docker 29.5.2 + Compose v5.1.4 có trên máy; `nvidia-ctk` không có (GPU vào container: chưa kiểm chứng).
- `quiz-app` chưa có shadcn/ui, `class-variance-authority`, `clsx`, `tailwind-merge`, Radix, alias `@/`; đã có bộ UI tự viết gồm 18 file trong `components/ui`.
- PDF gốc không được lưu (file tạm bị xoá sau khi đọc); cổng ObjectStore là chức năng mới, không phải di chuyển.

## 7b. Kết quả P0 đã nghiệm thu (2026-10-27, mẫu nhỏ, một máy, chưa có CI)
Nguồn: `eval/p0/latency_v2.json`, `eval/p0/triplet_noise_v2.json` (Coder đo; Leader tự tính lại từ `per_call`, khớp). Vòng 1 (`latency.json`, `triplet_noise.json`) giữ làm bằng chứng nhưng KHÔNG dùng để chốt ngưỡng vì Tester chạy lại ra số khác.
- `/chat` lúc rảnh, gTTS stub, 30 lượt (10 câu golden × 3 lượt, seed 1): median 3,44 s; Q1 1,97; Q3 6,44; mean 5,97; sd 8,95; p90 9,31; max 51,11 (một lượt q07). Trung bình theo câu từ 1,5 s (q01) đến 22,3 s (q07): phụ thuộc mạnh vào câu hỏi. Nguyên nhân outlier 51 s: chưa xác định.
- Vòng 1 và Tester: mean 7,97 s và 6,24 s (n=10), tức dao động giữa các lần chạy; upload (giới hạn 30 đoạn): 91,8 / 46,3 / 47,7 s.
- Triplet (40 đoạn, 3 lượt, temperature 0,0 đọc từ kwargs thật): 153/153/153, Jaccard 1,0. Vòng 1 từng cho 154/153 (Jaccard 0,953); chưa giải thích được khác biệt.
- gTTS thật: vòng 1 mean 59 s (max 270), Tester 11,7 s (max 40,7): bị nhiễu mạng, không dùng làm ngưỡng; củng cố quyết định tắt TTS ở notebook local.
- Công cụ: `python -m eval.compare A.json B.json` (McNemar chính xác, ghép theo id; lỗi người dùng -> thông báo tiếng Việt, exit 2). 88 test pass.
Hệ quả cho P1: P1-2 nên so sánh GHÉP CẶP theo từng câu và dùng median/IQR, không dùng mean hay p95 với n nhỏ; P1-3 khả thi (nhiễu 0 đến 0,65%).

## 8. Nhật ký thay đổi
- 2026-10-27: bản nháp đầu; thêm P1.5 (Notebook); AC P1 tinh chỉnh.
- 2026-10-27: P0 (đo độ trễ, nhiễu triplet, compare.py) nghiệm thu sau 2 vòng; kết quả ở mục 7b.
- 2026-10-27: chốt D2 (ghép cặp, median nền <= 1,5x rảnh) và D3 (McNemar trên 30 câu); chủ dự án tự commit kết quả P0.
- 2026-10-27: tick 6/6 review_sample theo lệnh chủ dự án (D1); `docs/book/` đưa vào .gitignore (D10: không version sách); commit nhóm tài liệu.
- 2026-10-27: chốt D12 (requirements-ci.txt), D13 (không bypass), D14 (PR+main); thí nghiệm venv rút gọn: 88 passed.
- 2026-10-27: bản đồ công nghệ gắn vào pha; thêm P0.7 (cắt đoạn theo token, phát hiện 15–20% đoạn >256 token); chốt D6, D7, D8.
- 2026-10-27: thêm P0.5 (CI) theo quyết định chủ dự án; P9 đổi thành Docker + CD xuất bản sản phẩm (không backend cloud); bật branch protection `main`.
