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

## 14. Bổ sung gộp 2026-11-01: nội dung các mục 0, 5b, 5c, 6, 8 (D15, D16), 9–13 của bản làm việc (thêm 2026-11-01)
Khôi phục luật append-only: các mục cũ ở trên được giữ nguyên chữ. Bản làm việc trước đó đã chèn mục 0, đánh số lại (mục 9 cũ "Điểm quyết định" thành mục 8; mục 8 cũ "Nhật ký" thành mục 11) và sửa tiêu đề mục 6; lý do: chèn thêm mục mới làm lệch số thứ tự. Khối dưới đây gom toàn bộ phần thêm vào đó, tiêu đề hạ một cấp; số mục trong khối này theo bản đánh số mới. Với mục trùng, khối này thay thế mục cũ cùng tên ở trên.

### 0. Trạng thái và luồng dài (cập nhật 2026-10-27)
| Pha | Trạng thái | Bằng chứng |
|---|---|---|
| P0 | XONG | mục 7b; golden 6/6 tick (Leader tick theo lệnh chủ dự án) |
| P0.5 | XONG | CI chạy thật trên GitHub (mục 6); branch protection `main` đã bật |
| P0.7 | XONG: giữ `char` làm mặc định (quy tắc quyết định: (b) và (c) trượt) | mục 9.B, kết quả bên dưới |
| P1 | KẾ TIẾP SAU P0.7 (luồng C) | mục 5 và 10.C |
| D (dọn dẹp) | XONG 2026-10-28 (xem trạng thái D ở mục 9.D) | mục 9.D, checkpoint mục 10 |
| P1.5 trở đi | chưa bắt đầu | mục 4 |

**Luồng dài do chủ dự án chọn (2026-10-27): A (xong) → B (P0.7) → C (P1) → D.** Quy tắc vận hành (D15, D16):
- **Chỉ chủ dự án commit/push/mở PR/merge.** Leader không commit. Vì `main` được bảo vệ (PR + `frontend` + `backend` + `secrets` xanh, không bypass), mỗi nhóm thay đổi sẽ đi qua PR do chủ dự án mở.
- **Luồng KHÔNG dừng để chờ commit.** Leader làm tiếp pha sau trên cùng nhánh làm việc `feat/long-flow` và KHÔNG đổi nhánh trong cả luồng (đã mất `chroma_db`/graphml hai lần khi đổi nhánh). Sau khi mỗi pha nghiệm thu, Leader lưu "checkpoint": `git diff` và danh sách file mới vào thư mục scratchpad của phiên, và ghi danh sách file + thông điệp commit đề xuất vào mục 10 (Checkpoint), để chủ dự án có thể tách commit theo pha bất cứ lúc nào.
- **Luồng DỪNG và hỏi chủ dự án khi:** một AC trượt hai vòng; số đo bác bỏ một giả thuyết đã chốt; cần dịch vụ ngoài hoặc tốn phí; có nguy cơ mất dữ liệu hoặc thao tác git phá huỷ/ra ngoài (xoá nhánh từ xa, force-push, đổi remote); hoặc có quyết định thuộc về chủ dự án.
- Mọi pha vẫn theo quy trình Leader dispatch → Coder → Tester → Leader tự chạy lại lệnh AC → nghiệm thu. Không nới AC giữa chừng; muốn đổi AC phải ghi lý do ở mục 11.

#### 5b. Tinh chỉnh hợp đồng API của P1 (2026-10-27, có lý do)
Bản đầu ghi `POST /upload` trả `202 + job_id` ngay. Kiểm chứng: 5 trang frontend gọi `/upload` (`NotebookStudio.jsx`, `WorkspaceDashboard.jsx`, `QuizGeneratorPage.jsx`, `JSONUploadPage.jsx`, `MindmapStudio.jsx`) và `QuizGeneratorPage.jsx:46→54`, `JSONUploadPage.jsx:198→206` gọi `/generate-quiz` NGAY sau khi upload; nếu `/upload` trả trước khi pha nhanh xong thì chúng truy vấn collection rỗng. Vì vậy: `/upload` chạy PHA NHANH trong executor (không chặn event loop) rồi mới trả về (mục tiêu vài giây), kèm `job_id`, `graph_status: "pending"` và các trường cũ giữ nguyên tương thích; PHA CHẬM (trích triplet) chạy nền. Thêm `GET /jobs/{id}` và `GET /jobs`. AC P1-1 đo thời gian từ POST đến khi POST trả về (cùng ngưỡng <= 10 s). Đây là thay đổi hợp đồng, KHÔNG nới ngưỡng.
#### 5c. P1.6 — UI MVP core (chủ dự án duyệt 2026-10-28)
Phạm vi: nạp tài liệu và hỏi đáp RAG chạy được, cộng Quiz/Mindmap hiện có (giữ nguyên logic). Nâng cấp `quiz-app/` hiện có, giữ state `view` (không router), không shadcn, không đổi backend. Ngoài phạm vi: slide, quiz đa dạng, Notebook/`data_policy`.
| AC | Kiểm chứng | Mong đợi |
|---|---|---|
| U1 | `grep -rn "fetch(" quiz-app/src/components quiz-app/src/App.jsx`; test `node --test` cho `lib/api.js` | 0 dòng; test phủ lỗi tiếng Việt cho backend tắt, 4xx, 5xx, timeout (`utils/share.js` được miễn: proxy ngoài) |
| U2 | Tester chụp màn hình 1280 px và 390 px | bố cục Nguồn / Hội thoại / Studio, không tràn ngang |
| U3 | logic thuần của `useJobs` (chọn job chưa xong, quyết định poll, nút "Tiếp tục") tách ra module và test bằng `node --test` | dừng poll khi hết job; nút chỉ hiện với `failed`/`interrupted` |
| U4 | test hàm định dạng nguồn/cờ đồ thị + Tester xem trên trình duyệt | hiện `graph_ready:false`, số trang, điểm cosine |
| U5 | Tester giả lập backend tắt, Ollama tắt, chưa có tệp, PDF hỏng | mỗi trường hợp có thông báo riêng, không trắng màn hình |
| U6 | 1 smoke Playwright trên backend giả: upload → job `done` → chat có nguồn | xanh cục bộ; đưa vào CI chỉ qua dispatch workflow riêng của Leader |
| U7 | `git diff --stat` + `cd quiz-app && npm run lint && npm test && npm run build` | không sửa `src/*.py`, logic Quiz/Mindmap; 3 lệnh xanh |

**Kết quả P1.6 (nghiệm thu 2026-10-28, mẫu nhỏ, một máy, backend giả + backend thật với Ollama thật qua Tester):** 4 vòng Coder, 2 vòng Tester độc lập. U1–U6 ĐẠT; U7 ĐẠT có ngoại lệ được chủ dự án duyệt (sửa `src/backend.py` cho L1 và M1). Số liệu Leader tự chạy lại: `pytest` 128 passed; `quiz-app` 147 test, lint/build/e2e xanh; `evaluate_rag.py --live` có `metrics`+`per_question` bằng `eval/report.json` (chỉ `git_rev`, `date` khác); dữ liệu thật không đổi. Đã sửa: L1 (500 không CORS => UI nhầm "Backend tắt"; nay 400/503/500 JSON có CORS), M1/C2 một nửa (`/generate-*` chạy threadpool; Coder đo `/health` p95 6–11 ms trong lúc mindmap chạy, trước đó Tester đo 3,7 s; số của Coder, Leader chưa đo lại), L2–L5, L6, L9, T2, T5, T7; xoá `NotebookStudio`, `MindmapStudio`, `QuizGeneratorPage`. Nợ còn lại: T1 (màn quiz/kết quả còn tiếng Anh), T3 (job lỗi không xoá được), T4 (PDF mật khẩu báo "hỏng"), T6 (placeholder/tên tệp bị cắt ở 390/768 px), L7 (bảng markdown thô, TTS tự phát), worker đồ thị chưa nhường `/generate-*`, thông báo "Only PDF files…" hiện như PDF hỏng, nhận diện Ollama dựa vào kiểu ngoại lệ (đổi phiên bản thư viện có thể gãy), chưa kiểm trình duyệt cho `interrupted`/T5, chưa chạy tay mutation "bỏ bọc PyPdfError". Chip độ khó đổi `Easy/Normal/Hard` -> `Dễ/Vừa/Khó`: 1 mẫu mỗi mức, Dễ và Vừa gần như cùng bộ câu; chưa đo chất lượng.

### 6. P0.5 — CI (AC) — XONG 2026-10-27
Kết quả trên runner GitHub (nguồn: `gh run list/view`, lần chạy PR `feat/ci` #9 và push `main`): PR: backend 74 s, frontend 27 s, secrets 6 s; push main: 82 s, 24 s, 6 s. Log runner: `pytest` 88 passed trong 3,24 s; frontend 115/115; build 11 s; gitleaks "no leaks found". CI-1 và CI-5 đạt.
CI-2 (PR #10 thử, đã đóng và xoá nhánh): thêm test cố ý hỏng → job `backend` ĐỎ, `frontend`/`secrets` xanh, `mergeStateStatus: BLOCKED`. CI-3 (PR #11 thử, đã đóng và xoá nhánh): chuỗi giống khoá → job `secrets` ĐỎ (gitleaks `generic-api-key`, entropy 5,195, `fake_secret_for_ci_test.py:1`), `BLOCKED`. CI-4: branch protection `main` bật qua `gh api` ngày 2026-10-27: bắt buộc PR (0 người duyệt), bắt buộc 3 job `frontend`/`backend`/`secrets` (strict=false), `enforce_admins=true`, cấm force-push và xoá nhánh; kiểm lại bằng `gh api .../branches/main/protection`.
Phát hiện: `actions/checkout` với `fetch-depth: 0` lấy MỌI nhánh từ xa nên gitleaks quét cả nhánh khác; khi PR #10 và #11 cùng tồn tại, job `secrets` của #10 đỏ vì nhánh của #11. Hệ quả: một nhánh đã push có chuỗi giống khoá làm job `secrets` đỏ ở MỌI PR cho tới khi nhánh đó bị xoá (có lợi cho repo public; cần biết khi thử). Chuỗi giả vẫn nằm vĩnh viễn trong `refs/pull/11/head` của GitHub (hoàn toàn ngẫu nhiên, không phải khoá thật).
(Bản AC gốc:)
### 8. Điểm quyết định chờ chủ dự án
- D15 [ĐÃ CHỐT 2026-10-27]: chỉ chủ dự án commit/push/PR/merge; Leader chuẩn bị file, thông điệp commit (không dòng ghi công Claude) và checkpoint.
- D16 [ĐÃ CHỐT]: luồng dài chỉ dừng khi có vấn đề hoặc cần quyết định (điều kiện ở mục 0).

### 9. Luồng dài chi tiết
#### B — P0.7: cắt đoạn theo token (thí nghiệm có quy tắc quyết định đặt TRƯỚC)
Cơ sở (đã đo, PLAN mục 7): 15–20% đoạn 600 ký tự vượt 256 token của sbert nên phần đuôi không được embedding. Ảnh hưởng lên hit@k CHƯA đo.
Thiết kế: `_chunk_pages(page_texts, chunking="char")`; `chunking="token"` đo độ dài bằng tokenizer của `keepitreal/vietnamese-sbert` (tải lười, `local_files_only`), kích thước ~230 token và chồng lấn ~20 token (xấp xỉ 75 ký tự); chọn bằng biến môi trường `CHUNKING` (mặc định `char`, tức hành vi hiện tại và CI không cần `transformers`). Nếu chọn `token` mà thiếu tokenizer thì báo lỗi rõ, KHÔNG âm thầm quay về `char`.
| AC | Lệnh | Mong đợi |
|---|---|---|
| P07-1 | `python -m eval.chunk_stats` (mới) với `EVAL_PDF_DIR` | in số đoạn, % đoạn > 256 token, max, mean cho `char` và `token` của 3 PDF; `char` TÁI LẬP đúng số đã đo (24/119, 20/137, 29/142); `token` = 0% đoạn > 256 |
| P07-2 | `pytest tests -q` | 0 failed; >= 5 test mới cho `chunking` (dùng tokenizer giả, không cần `transformers`); mặc định `char` giữ nguyên kết quả cũ (số đoạn các PDF mẫu không đổi) |
| P07-3 | `python src/evaluate_rag.py --live` với `CHUNKING=char` rồi `CHUNKING=token` | hai report lưu ở `eval/p07/` (không bị ignore); `char` byte-giống `eval/report.json` hiện tại |
| P07-4 | `python -m eval.compare eval/p07/report_char.json eval/p07/report_token.json` | bảng b, c, p cho hit@4/6/8; thêm MRR, cover@8 multi-hop |
| P07-5 | tính chi phí | tỉ lệ số đoạn token/char, thời gian embedding, ước tính thời gian trích triplet = số đoạn × 1,4–1,7 s (ngoại suy từ số đo, nêu rõ) |
| P07-6 | `git status`/`stat` dữ liệu thật | chỉ file trong allowlist; `chroma_db`/graphml thật không đổi |
**Quy tắc quyết định (đặt trước khi thấy số):** đổi mặc định sang `token` nếu và chỉ nếu (a) % đoạn > 256 token = 0, (b) với mỗi hit@4/6/8 thì c − b >= −1 (không metric nào mất ròng quá 1 câu), (c) MRR_token >= MRR_char − 0,02. Lý do: cắt cụt là lỗi đúng-sai (văn bản không được embedding), nên chỉ cần không gây hồi quy là sửa; n = 30 không đủ để đòi p < 0,05. Nếu không đạt: giữ `char`, ghi lại số. Nếu đổi mặc định: ĐỔI BASELINE, lưu report mới làm mốc, ghi vào mục 11; dữ liệu `chroma_db` cũ phải nạp lại (chủ dự án quyết lúc đó, không tự xoá). Ngoài phạm vi: tách từ tiếng Việt (D9).


**KẾT QUẢ P0.7 (2026-10-27, mẫu nhỏ n=30, một máy; Coder đo, Tester tái lập độc lập, Leader tự chạy lại `eval.compare`):**
- (a) THOẢ: `token` 0 đoạn > 256 ở cả 3 PDF (125/109/104 đoạn, max 243/238/234); `char` tái lập đúng 24/119, 20/137, 29/142. (Kích thước đoạn token phải hạ từ 230 xuống 210 vì bộ chia cộng độ dài từng mảnh nên đoạn ghép lại có thể lệch; quét 230/220/210/200 chỉ bằng thống kê token, chưa chạy retrieval.)
- (b) TRƯỢT: hit@4 b=1 c=2 (p=1,0); hit@6 b=0 c=3 (p=0,25); hit@8 b=4 c=2 (p=0,6875) ⇒ c−b ở hit@8 = −2.
- (c) TRƯỢT: MRR 0,4393 → 0,3762 (−0,0632 < ngưỡng −0,02). cover@8: all 0,5333 giữ nguyên; multi-hop 0,1 → 0,3; number 0,9 → 0,7.
- Không khác biệt nào có ý nghĩa thống kê (p >= 0,25). Chi phí `token`: 338 đoạn so với 398 (tỉ lệ 0,849); embedding 3,59 s so với 4,56 s (1 lần đo); ước tính triplet −15% (ngoại suy).
- **Quyết định theo quy tắc: GIỮ `char`, KHÔNG đổi baseline.** `CHUNKING=token` vẫn có sẵn nhưng tắt mặc định. Đoạn 600 ký tự vẫn có ~15–20% vượt 256 token (ảnh hưởng thực lên retrieval chưa chứng minh); nguyên nhân MRR tụt chưa phân tích; overlap/separators chưa đo; golden còn 24/30 câu chưa ai duyệt.
- Việc nhỏ còn lại: docstring `_chunk_pages` ghi "230/20" nhưng hằng số là 210 (`src/backend.py`), sửa trong dispatch P1.

#### C — P1: nạp hai pha (dùng AC ở mục 5, kèm tinh chỉnh API ở mục 5b)
Bước: C1 kho job SQLite (`jobs.sqlite` ở gốc repo, bảng `jobs`: job_id, notebook_id tạm null, source, status, progress, error, timestamps) + máy trạng thái `queued→fast_running→fast_done→graph_running→done|failed|interrupted`; C2 pha nhanh trong executor, `/upload` trả sau pha nhanh; C3 worker pha chậm 1 luồng, tạm dừng khi có `/chat` đang chạy; khoá cho `_knowledge_graph` và cờ `graph_ready` trong `/health`, `/chat`; C4 `GET /jobs/{id}`, `GET /jobs`; C5 khởi động lại: job `graph_running` thành `interrupted`, có thể chạy lại, dữ liệu vector còn nguyên. `requirements-ci.txt` KHÔNG đổi. Frontend: không đổi trong P1 (UI trạng thái nạp thuộc P1.5).
AC: P1-1..P1-7 ở mục 5 (P1-1 đo thời gian POST /upload trả về; P1-4 so với baseline MỚI nếu P0.7 đổi mặc định).

**KẾT QUẢ P1 (nghiệm thu 2026-10-28, mẫu nhỏ, một máy; Coder đo, Tester đo lại độc lập, Leader tự chạy lại pytest/`stat`/`jobs.sqlite`):**
| AC | Kết quả | Ngưỡng |
|---|---|---|
| P1-1 `/upload` trả về (>= 5 lượt) | Coder mean 7,62 s (5,32–12,13); Tester mean 2,73 s (2,60–3,02, sd 0,17) | mean <= 10 s: ĐẠT (hai bên khác nhau do trạng thái máy) |
| P1-2 `/chat` nền/rảnh, ghép cặp theo câu | liên tục: 0,816 (vacuous: worker bị nhường hết, 1 lời gọi triplet); nhịp người dùng 10 câu × 3 lượt cách 10 s: Coder 1,289 (27 lượt hợp lệ), Tester 1,251 (IQR 0,935–1,436, 30/30; 118 lời gọi triplet) | median tỉ số <= 1,5: ĐẠT, nhưng 4/10 câu (Coder) và 2/10 câu (Tester) vượt 1,5; dải 0,43–4,37; ngoại lai 52,6 s và 99,8 s (Coder, "Ollama đứng", chưa kiểm chứng) |
| P1-3 triplet hai pha so với đồng bộ (40 đoạn) | Coder 184/182 (1,1%); Tester 182/177 (2,8%) | ±10%: ĐẠT |
| P1-4 `eval` | `metrics` và `per_question` giống hệt `eval/report.json` | ĐẠT |
| P1-5/P1-7 test | 119 passed ở `.venv` và venv CI sạch (không `transformers`); 8+ test mới, test song song | ĐẠT |
| P1-6 thật (uvicorn, `kill -9`) | `/upload` 3,08 s với 119 đoạn; kill lúc 40/119 (Tester) và 20/119 (Coder vòng 4); Chroma vẫn 119 đoạn; khởi động lại `interrupted`; `/chat` 200; resume tới `done`; resume lần hai 409 | ĐẠT |
| P1-8 dữ liệu thật | `chroma_db`/graphml không đổi (622592 và 1062579 byte, mtime không đổi) | ĐẠT |
Chẩn đoán độ trễ: phần `/chat` chậm hơn khi nền chạy nằm ở lời gọi LLM đầu tiên (trích thực thể median 0,50–0,53 s rảnh, 1,09–1,13 s nền): nó chờ lời gọi triplet đang chạy dở (không ngắt được); pha sinh gần như không đổi. Biện pháp: thời gian nguội `GRAPH_YIELD_COOLDOWN_SECONDS` (mặc định 3 s) + nhường khi có `/chat`, trần chờ 60 s.
Lỗi Tester tìm thấy và đã sửa ở vòng 4: B1 (Ollama tắt mà job vẫn `done` 0 triplet, `error` null → giờ `failed` có thông báo; lỗi lẻ tẻ → `done` kèm cảnh báo; resume cho `failed`/`interrupted`), B2 (`chunks_done` chỉ tăng khi lưu graphml thành công), B3 (resume job chết lúc `fast_running` → 409), C1 (resume nguyên tử bằng compare-and-set). Lỗi Coder tự sửa ở vòng 2: `fast_done` → `interrupted` khi khởi động lại; ghi `chunks_done` sau khi lưu graphml. Sự cố cô lập: test cũ ghi vào `jobs.sqlite` thật (260 job test) → `tests/conftest.py` đặt `JOBS_DB_PATH` tạm và cooldown 0; file đã xoá sau khi truy vấn xác nhận toàn tên file test.
**Nợ kỹ thuật P1 (chưa sửa):** C2 `/generate-quiz` và `/generate-mindmap` còn `async def` gọi LLM đồng bộ và worker không nhường chúng; C3 mỗi `/chat` sao chép toàn đồ thị; C4 PDF hỏng trả 500 (hành vi cũ), `on_event("startup")` deprecated; C5 không giới hạn kích thước upload, `GET /jobs` không phân trang, SQLite không an toàn đa tiến trình; test yếu: nhường `/chat` dùng `sleep` thật (`tests/test_two_phase_upload.py` khoảng dòng 138–154), đồng hồ giả không phủ nhánh `_chat_active>0` hay chat ném ngoại lệ, chưa kiểm resume chỉ chạy từ `chunks_done`.

#### D — dọn dẹp (xen kẽ, cuối luồng)
| Việc | Cách | Cổng |
|---|---|---|
| D1 `git pull --ff-only` cập nhật `main` cục bộ | lệnh | tự làm |
| D2 Sửa remote `origin` thành `AIVIETNAM-AIO-luciusHo/My-NotebookLM` | `git remote set-url` (cấu hình cục bộ; kiểm `git remote -v` trước/sau) | hỏi trước (đổi cấu hình) |
| D3 Đồng bộ `requirements.txt` với môi trường thật (ghi `fastapi==0.110.0`, `langchain==0.3.7` nhưng máy dev `fastapi 0.138.1`, `langchain 1.3.11`; thiếu `httpx`) | dispatch riêng: dựng venv sạch từ file mới, `pytest` 0 failed, CI xanh | chủ dự án quyết hướng (ghim theo máy dev hay theo CI) |
| D4 Sửa README: "100% offline" chưa đúng vì gTTS; thêm cách chạy CI/eval | dispatch tài liệu | tự làm |
| D5 Xoá nhánh từ xa đã merge/đóng (`feat/eval`, `feat/foundation`, `feat/lockfile`, `feat/ci`, `feat/plan-docs-clean`, `refactor/monorepo-architecture`; `feat/plan-docs` đã đóng, chứa commit có dòng ghi công) | liệt kê rồi xoá | DỪNG hỏi (xoá nhánh từ xa) |
| D6 Daily Note + dòng MOC cho từng pha | `python3 src/daily_note.py` | tự làm |
| D7 `langchain-community` trong `requirements-ci.txt` có thừa không | gỡ thử trong venv sạch, `pytest` | tự làm nếu chạy xanh |

**Trạng thái D (2026-10-28):** D1 XONG (main cục bộ khớp origin/main). D2 XONG (`origin` → `AIVIETNAM-AIO-luciusHo/My-NotebookLM`, `git fetch` ổn). D3 XONG (chủ dự án chọn "khớp bộ đã kiểm trên CI"): `requirements.txt` = lõi của `requirements-ci.txt` (cùng ghim, kèm `httpx<0.28`) + runtime nặng + `langchain-community==0.3.7` (Streamlit) + eval; thêm `pyarrow==24.0.0` ngoài dự kiến (pyarrow >= 25 cần NumPy 2 nhưng `chromadb==0.4.24` giữ NumPy 1.26.4 làm `datasets` không import được; `pip check` không bắt lỗi này, pytest mới bắt). Kiểm trong venv sạch (cài 19 phút 13 s mạng chậm, 6,5 GB): `pip check` sạch, 119 passed, `evaluate_rag.py --live` GIỐNG HỆT `eval/report.json` (stack mới không đổi embedding/kết quả), smoke thật upload (5,5 s) + chat 200. Khác máy dev: dev chạy langchain 1.3.11, fastapi 0.138.1, starlette 1.3.1, pandas 2.3.3; venv mới theo ghim: 0.3.7, 0.110.0, 0.36.3, pandas 3.0.6 (không ghim); máy dev CHƯA đổi, mã chưa được kiểm trên stack mới ngoài các phép thử này và CI. D4 XONG (README viết lại, bảng đối chiếu endpoint/biến → file:dòng, gTTS ghi là ngoại lệ offline). D5 XONG (xoá 7 nhánh từ xa; trên GitHub chỉ còn `main`; xoá 5 nhánh cục bộ đã merge; còn `feat/long-flow`, `feat/time-skip`, và `feat/plan-docs` cục bộ chưa merge). D6 XONG (Daily Note 27 và 28/10 + MOC). D7 XONG (gỡ `langchain-community` khỏi `requirements-ci.txt`: 119 passed ở venv sạch; CI trên runner sẽ xác nhận khi có PR).

### 10. Checkpoint (Leader điền sau mỗi pha nghiệm thu)
**P0.7 (nghiệm thu 2026-10-27).** Snapshot: scratchpad `checkpoints/P0.7/diff.patch` và `untracked.txt` của phiên. Nếu bạn commit riêng pha này:
- File: `src/backend.py`, `src/evaluate_rag.py`, `eval/chunk_stats.py`, `eval/p07/` (`chunk_stats.json`, `report_char.json`, `report_token.json`, `summary.json`), `tests/test_chunking.py`, `PLAN.md`.
- Thông điệp đề xuất: `feat(chunking): add optional token-based chunking (CHUNKING=token), keep char as default` kèm thân bài: kết quả quy tắc quyết định (a thoả; b, c trượt) và các số trên. Không thêm dòng ghi công Claude.
- Lưu ý: `PLAN.md` mang cả thay đổi của luồng dài (mục 0, 9, 10, 11); tách riêng nếu muốn.

**P1 (nghiệm thu 2026-10-28).** Snapshot: scratchpad `checkpoints/P1/diff.patch` và `untracked.txt`. `src/backend.py` và `src/evaluate_rag.py` mang CẢ thay đổi P0.7 lẫn P1 nên khó tách commit nếu không dùng `git add -p`; gợi ý đơn giản: một commit chung cho P0.7 + P1.
- File P1: `src/backend.py`, `src/jobs.py` (mới), `src/evaluate_rag.py`, `eval/p1_measure.py`, `eval/p1/` (kết quả đo), `tests/conftest.py`, `tests/test_jobs.py`, `tests/test_two_phase_upload.py`, `tests/test_multi_file.py` (+1 dòng `backend.wait_for_jobs()`), `tests/test_page_metadata.py` (+1 dòng), `PLAN.md`.
- File P0.7 (nếu gộp): `eval/chunk_stats.py`, `eval/p07/`, `tests/test_chunking.py`.
- Thông điệp đề xuất (một commit chung cho P0.7+P1): `feat(ingest): two-phase upload with background graph jobs, optional token chunking` kèm thân bài: pha nhanh trả sau vài giây, pha chậm một luồng nhường `/chat`, `GET /jobs`, resume, `graph_ready`; `CHUNKING=token` tắt mặc định. Không thêm dòng ghi công Claude.

**D (nghiệm thu 2026-10-28).** Snapshot: scratchpad `checkpoints/D/`. Gợi ý một PR từ `feat/long-flow` (main được bảo vệ, cần CI xanh) gồm 3 commit theo thứ tự:
1. `feat(ingest): two-phase upload with background graph jobs, optional token chunking` — `src/backend.py`, `src/jobs.py`, `src/evaluate_rag.py`, `eval/chunk_stats.py`, `eval/p07/`, `eval/p1_measure.py`, `eval/p1/`, `tests/conftest.py`, `tests/test_chunking.py`, `tests/test_jobs.py`, `tests/test_two_phase_upload.py`, `tests/test_multi_file.py`, `tests/test_page_metadata.py`.
2. `chore(deps): sync requirements.txt with the CI-verified core, drop langchain-community from CI` — `requirements.txt`, `requirements-ci.txt` (CI sẽ xác nhận lần đầu trên runner).
3. `docs: update README and PLAN for two-phase ingest, CI and cleanup` — `README.md`, `PLAN.md`.
Không thêm dòng ghi công Claude vào commit hay mô tả PR (quy tắc trong `CLAUDE.md`). `TASK_*.md`, `TEST_REPORT.md` không track. Sau khi merge: `git checkout main && git pull --ff-only` rồi xoá `feat/long-flow` (nhánh cục bộ và từ xa nếu đã đẩy).

### 11. Nhật ký thay đổi
- 2026-10-28: P1.6 nghiệm thu (4 vòng Coder, 2 vòng Tester; kết quả ở mục 5c). Chưa commit: `quiz-app/` là commit riêng, `src/backend.py` + tests lẫn với P1 nên đi cùng commit P1.
- 2026-10-28: chủ dự án duyệt P1.6 (UI MVP core, mục 5c); làm trên `feat/long-flow` khi P0.7+P1+D chưa commit => khi commit phải tách theo đường dẫn (`quiz-app/` là commit riêng).
- 2026-10-28: D xong (D1–D7); `requirements.txt` khớp lõi CI + `pyarrow==24.0.0`; xoá 7 nhánh từ xa; đổi remote; README viết lại; checkpoint D và gợi ý 3 commit/1 PR ở mục 10.
- 2026-10-28: P1 nghiệm thu (4 vòng; P1-2 vòng 1 trượt 1,777 rồi sửa bằng thời gian nguội; Tester tìm B1–B3, C1 đã sửa); nợ C2–C5 ghi ở mục 9.C; D1 xong (main cục bộ khớp origin/main).
- 2026-10-27: P0.7 nghiệm thu: giữ `char` (quy tắc quyết định: (b) và (c) trượt); `CHUNKING=token` có sẵn, tắt mặc định; baseline không đổi.
- 2026-10-27: P0.5 XONG (CI-1..CI-5 có bằng chứng); thêm mục 0 (trạng thái, luồng dài, D15 D16), mục 9 (B, C, D chi tiết), mục 10 (checkpoint); sửa hợp đồng `/upload` của P1: trả sau pha nhanh thay vì 202 ngay (lý do: 5 trang frontend chuỗi `/upload` rồi `/generate-*`).


### 12. P1.7 — trả nợ P1.6 và kiểm định phần chưa kiểm (thêm 2026-10-28; luật: PLAN.md chỉ append)
Mục này BỔ SUNG mục 5c ("Kết quả P1.6"); không thay thế dòng nào của mục cũ. Chủ dự án yêu cầu: trả phần nợ chưa sửa và kiểm định phần chưa kiểm. 2 vòng Coder, 1 vòng Tester độc lập (mẫu nhỏ, một máy).

**Số liệu Leader tự chạy lại sau vòng 2:** `pytest` 141 passed; `quiz-app` 163 test, lint/build/e2e xanh; `evaluate_rag.py --live --out <tmp>` có `metrics` và `per_question` bằng `eval/report.json`; `chroma_db/` và `knowledge_graph.graphml` không đổi; không có `jobs.sqlite*` ở gốc; không còn `fetch(` trong `components/` và `App.jsx`.

**Đã trả (nợ ở mục 5c):** T1 dịch giao diện (Tester bắt thêm phần còn sót ở `QuizLibraryPane`, `QuestionEditor`, `index.html`; vòng 2 quét bằng parser và dịch thêm "Remove/Cancel"); T3 `DELETE /jobs/{id}` (404 không có, 409 còn chạy, không đụng Chroma/đồ thị) + nút "Xoá"; T4 PDF có mật khẩu báo riêng; không-PDF báo "Chỉ nhận tệp PDF."; Ollama: mô hình chưa tải 503, quá lâu 504; T6 placeholder/tên tệp; L7 bảng markdown bằng React (không `dangerouslySetInnerHTML`), TTS không tự phát (backend vẫn sinh audio qua gTTS; tắt theo notebook là P1.5); L1 `RichText` không gạch chân `__x__` trong từ/inline code, L2 `graph_ready` chỉ `true` khi không còn job `queued|fast_running|fast_done|graph_running|interrupted|failed` (ĐỊNH NGHĨA LẠI so với P1: trước đó chỉ xét job đang chạy), L4 hàng job lỗi nêu nguyên nhân Ollama, L5 tệp không-PDF chặn phía client đúng khung, L6 bỏ cổng ghi cứng, L7 tab Quiz/Mindmap dùng `StatePanel`, L9 key React.

**Quy tắc đo yield (đặt trước, ngưỡng 1,5 như D2) cho `/generate-mindmap`:** Coder đo median A (đồ thị đang dựng) 4,092 s (n=8) so với B (rảnh) 3,141 s (n=12), tỉ số 1,303 => KHÔNG cài nhường. Tester đo lại n=4 mỗi bên: 1,446 (biên mỏng; p95 A/B khoảng 1,58; mọi mẫu A đều ở đầu pha đồ thị, `chunks_done` còn 0). Kết luận theo quy tắc không đổi, nhưng biên mỏng; mẫu nhỏ, một máy, một PDF, một chủ đề; chưa đo `/generate-quiz`. Nếu trải nghiệm thật thấy generate chậm khi đồ thị đang dựng, đo lại với n lớn hơn và mẫu ở giữa pha đồ thị.

**Kiểm định phần chưa kiểm (Tester, trình duyệt thật + backend thật + Ollama thật):** `interrupted` ĐẠT (kill -9 khi `graph_running`, bật lại hiện "Bị gián đoạn" + "Tiếp tục"; resume tới `done`; Chroma giữ 142 đoạn; `/chat` có nguồn; giới hạn: lúc kill job mới ở 0/142 nên chưa kiểm resume từ giữa chừng); T5 ĐẠT (tự hồi phục khoảng 1 s); mutation bỏ bọc `PyPdfError` làm 2 test fail (ĐẠT); 4 mutation khác (T3, T4, Ollama 504, bảng markdown) đều bị test bắt; luồng quiz đơn/đa lựa chọn và lịch sử cũ trong IndexedDB đọc được; preflight CORS cho `DELETE` đúng.

**Nợ còn lại (ghi trung thực):** L3 client Ollama không đặt timeout nên 504 chưa xảy ra thật (chỉ test bằng ngoại lệ giả; UI timeout 300 s che được); L8 upload 400 vẫn tạo hàng job `failed` (xoá được bằng T3); `__init__` đứng trần trong nội dung quiz vẫn gạch chân (không phân biệt được với `__x__` mà test cũ yêu cầu); proxy chia sẻ Vercel chưa kiểm dưới Vite; "Xoá" ở job `failed`/`interrupted` chỉ có pytest, chưa bấm thật trên UI; phía Python chưa quét import chết (`.venv` thiếu pyflakes/ruff); thông điệp backend vẫn tiếng Anh ở các `detail` ngoài bảng dịch của `api.js`; `api/proxy.js` còn thông báo tiếng Anh (ngoài luồng core); worker đồ thị chưa nhường `/generate-*` (theo quy tắc yield). Chip độ khó đổi sang `Dễ/Vừa/Khó` (1 mẫu mỗi mức, Dễ và Vừa gần giống nhau; chưa đo chất lượng).

**Sự cố nhỏ:** Tester đã kill một tiến trình Vite mồ côi (cổng 5199) vì chặn e2e; không rõ chủ sở hữu.

**Gợi ý commit (chủ dự án tự commit; không ghi công Claude):** nhánh `feat/long-flow` giờ chứa P0.7+P1+D+P1.6+P1.7. Đề xuất 5 commit theo đường dẫn: (1) `src/jobs.py`, `src/backend.py`, `src/evaluate_rag.py`, `tests/`, `eval/` (P0.7+P1+P1.6+P1.7 backend: không tách riêng được `backend.py`); (2) `requirements*.txt`; (3) `quiz-app/` (UI P1.6+P1.7, kèm `.gitignore` của `quiz-app`); (4) `README.md`; (5) `PLAN.md`, `CLAUDE.md` (kèm luật PLAN append-only).

### 13. P1.8 — nâng chất lượng nạp và truy hồi (thêm 2026-10-28; chủ dự án duyệt)
Bối cảnh: chủ dự án chạy thử MVP, mọi thứ chạy được nhưng chất lượng nạp/hiểu/trả lời còn yếu; chủ dự án đã fork ba repo tham khảo: `llama_index` (MIT), `docling` (MIT), `ragflow` (Apache-2.0). Leader đã đọc (bản HEAD ngày 2026-10-14/2026-10-28), kết luận: KHÔNG dùng RAGFlow làm phụ thuộc (README yêu cầu tối thiểu 4 CPU, 16 GB RAM, 50 GB đĩa, nhiều dịch vụ Docker; máy dự án 11 GB RAM); KHÔNG cài nguyên LlamaIndex (framework lớn, xung đột điểm patch `backend.py`); CHỈ mượn ý tưởng nhỏ tự cài lại; Docling thử như gói tuỳ chọn tách riêng. Số tốc độ Docling trong tài liệu của họ đo trên máy khác (L40S, RTX 5090/5070), KHÔNG có số cho RTX 3050 6 GB: phải đo (E1). Mình chỉ đọc README/cấu trúc của RAGFlow, chưa đọc mã thuật toán.

**Dữ kiện nền (baseline, mẫu nhỏ, một máy; `eval/report.json`):** hit@4 14/30, hit@8 23/30; 7 câu trượt cả top-8 (q01, q10, q11, q13, q22, q25, q29), 9 câu chỉ trúng ở top-8 (q04, q07, q09, q15, q18, q20, q24, q26, q27). Dấu hiệu trích xuất: `gold_quote` (trích bằng pypdf) có dính chữ/mất khoảng trắng/vỡ công thức ("P(A|B)vớiP(B|A)", "VậyJđơn điệu", "107lầnn"). Đây là DẤU HIỆU, chưa phải kết luận nguyên nhân; E0 phân loại. Vì `gold_pages` chấm theo trang, đổi bộ đọc PDF hay cách cắt đoạn vẫn so sánh được miễn là giữ metadata `page`.

**Các thí nghiệm (mỗi cái so ghép cặp với baseline, quy tắc dưới đây đặt TRƯỚC khi chạy):**
| Bước | Nội dung | Ghi chú |
|---|---|---|
| E0 | Phân loại câu trượt theo nguyên nhân bằng quy tắc cố định (không phân loại tay): (A) trích dẫn nằm ở phần bị cắt sau 256 token của đoạn; (B) trích dẫn bị cắt ngang ranh giới đoạn; (C) đoạn đúng trang có trong top-30 nhưng hạng > k; (D) trang đúng không có trong top-30; (E) dấu hiệu vỡ trích xuất (dính chữ, mất khoảng trắng, ký hiệu rời) ở đoạn đúng | chỉ đọc, không đổi mã sản phẩm |
| E3 | Tìm kiếm lai (BM25 + vector, hợp nhất RRF) rồi xếp hạng lại bằng cross-encoder | cờ `RETRIEVAL`, mặc định không đổi; ý từ `QueryFusionRetriever`, `SentenceTransformerRerank` của LlamaIndex |
| E4 | `bge-m3` (đã có trong Ollama của chủ dự án) thay `keepitreal/vietnamese-sbert` | cần nạp lại chỉ mục; báo thời gian và dung lượng |
| E1 | Docling so với pypdf (venv riêng; 3 PDF: thời gian, RAM, chất lượng chữ, rồi hit@k theo trang) | gói tuỳ chọn, KHÔNG vào `requirements-ci.txt`, mặc định giữ pypdf |
| E2 | Cắt đoạn theo cấu trúc (HybridChunker hoặc theo tiêu đề), giữ `page` | sau E1 |
| E5 | Cửa sổ câu hoặc gộp cha–con | sau E3/E4 nếu còn lỗi do kích thước đoạn |
| E6 | Tách câu hỏi multi-hop (ý từ RAGFlow) | cuối; llama3.2 3B có thể yếu |

**Quy tắc quyết định chung (đặt trước):** tập xác nhận = các câu `reviewed:true` của bộ vàng mở rộng. Nếu số câu đã duyệt < 45 thì mọi kết quả chỉ gọi là "thăm dò". Một ứng viên được CHẤP NHẬN chỉ khi đồng thời: (i) với hit@4 và hit@8, c − b >= 0 ở cả hai và c − b >= +3 ở ít nhất một (c: câu ứng viên đúng, baseline sai; b: ngược lại); (ii) MRR_ứng_viên >= MRR_baseline − 0,02; (iii) độ trễ `/chat` p95 <= 1,5 lần baseline đo cùng điều kiện (E3, E4) và bộ nhớ vừa máy 11 GB; (iv) báo p-value McNemar chính xác nhưng KHÔNG dùng nó làm cổng duy nhất (n nhỏ). Với E1 thêm: báo thời gian nạp mỗi PDF 27 trang; nếu pha nhanh vượt ngưỡng P1-1 (<= 10 s), cần thêm pha "đọc tài liệu" vào job nền và chủ dự án quyết định đổi AC (bằng mục mới trong PLAN). Mọi con số ghi "mẫu nhỏ, một máy".

**Bộ vàng mở rộng:** chủ dự án đồng ý duyệt thêm câu. Mở rộng lên khoảng 60 câu bằng PDF thật có bảng/công thức; ứng viên nằm ở tệp RIÊNG `eval/golden_candidates.jsonl` (reviewed:false) cho đến khi chủ dự án duyệt; `eval/golden.jsonl` (30 câu) và `eval/report.json` GIỮ NGUYÊN làm baseline cũ. Khi gộp, tính baseline mới bằng pipeline hiện tại (không đổi mã) và lưu ở tệp mới, KHÔNG ghi đè `eval/report.json`.

**Thứ tự chủ dự án chọn:** E0, rồi E3+E4, rồi E1. Việc làm ngay: E0 và sinh ứng viên bộ vàng (giao Coder, dispatch ngày 2026-10-28). Trong lúc chủ dự án duyệt câu, phần cài E3/E4 sau cờ có thể làm song song nhưng CHỈ đo trên tập đã duyệt.

#### 13.1 Kết quả E0 và ứng viên bộ vàng (thêm 2026-10-28; mẫu nhỏ, một máy; Leader tự chạy lại)
**E0 (`eval/p18/failure_summary.md`, 30 câu, quy tắc cố định):** khớp baseline từng câu (hit@4 14/30, hit@8 23/30). Số câu mỗi cờ: A=0 (trích dẫn nằm sau 256 token), B=2 (q01, q03: cắt ngang ranh giới), C4=14 (đoạn đúng trang có trong top-30 nhưng hạng >4), C8=5, D=2 (q13, q25: trang đúng không có trong top-30), E=19 (heuristic vỡ trích xuất).
**Đính chính giả thuyết (bổ sung, không thay mục cũ):** mục 13 ("dữ kiện nền") và mục 7 nêu 15–20% đoạn vượt 256 token; E0 cho thấy với 30 câu này MỌI trích dẫn vàng đều nằm trong 254 token đầu của đoạn chứa nó, nên cắt 256 token KHÔNG giải thích câu trượt nào (A=0; xấp xỉ có thể lệch 1 token). Nguyên nhân thấy rõ hơn là xếp hạng: 14/30 câu có đoạn đúng nhưng hạng 5–9 (C4), cosine của đoạn đúng thường chỉ 0,39–0,68 và sát cosine top-1 => nhúng hiện tại phân biệt yếu giữa các đoạn gần nghĩa. Cờ E yếu: regex khớp 37,9% toàn bộ đoạn; có ở 5/7 câu trượt@8 và 6/14 câu trúng@4; không đủ để kết luận "do pypdf" (E1 mới trả lời). Hệ quả cho thứ tự: E3 (lai + xếp hạng lại) và E4 (`bge-m3`) đúng ưu tiên; D (q13, q25) gợi ý thành phần từ khoá có thể cứu; E2 theo cấu trúc hạ ưu tiên.
**Ứng viên bộ vàng:** `eval/golden_candidates.jsonl` có 42 câu (fact 16, number 17, multi-hop 9; kind prose 11, table 15, formula 16; 3 PDF mới: `math-linear-regression.pdf` 13 câu, `module3-trees-xai-timeseries.pdf` 15, `module4-deeplearning-optimization.pdf` 14), 42/42 `gold_quote` khớp văn bản pypdf, TẤT CẢ `reviewed:false`, chưa ai duyệt đáp án. 12 câu (c02, c03, c04, c06, c07, c12, c14, c15, c18, c21, c35, c39) có trích dẫn có dấu hiệu méo ký hiệu toán (heuristic), cần đối chiếu PDF thật; cặp cùng chủ đề (c12 với c03/c04, c28 với c26) có thể trùng ý. 42 < mục tiêu khoảng 60 của mục 13; nếu chủ dự án duyệt được bao nhiêu thì bấy nhiêu, thiếu thì sinh thêm. `eval/report.json` và `eval/golden.jsonl` giữ nguyên (sha256 trước/sau trùng). `pytest` 146 passed.

#### 13.2 Kết quả thăm dò E3/E4 (thêm 2026-10-28; mẫu nhỏ, một máy, một lần chạy mỗi ô; Leader tự chạy lại một phần)
Cài đặt: `src/retrieval.py` (BM25 tự cài, RRF k=60, tách âm tiết `uni`/`uni_bi`), cờ `RETRIEVAL=vector|hybrid|hybrid_rerank`, `EMBEDDING=sbert|bge-m3`, `BM25_TOKENS=uni|uni_bi`; mặc định = hành vi cũ. Mô hình xếp hạng lại `BAAI/bge-reranker-v2-m3` (Apache-2.0, 2,27 GB, tra cứu 2026-10-28 qua API Hugging Face, chọn theo lý lẽ định tính, chưa so mô hình khác). Ma trận 6 biến thể x 2 tập; số thô ở `eval/p18/e34/`, bảng ở `eval/p18/e34/summary.md`.

| Biến thể | g30 hit@4 / hit@8 | MRR | cover@8 multi-hop | hit@4 cand(42) / hit@8 |
|---|---|---|---|---|
| vector + sbert (baseline) | 0,47 / 0,77 | 0,439 | 0,1 | 0,48 / 0,52 |
| hybrid (uni) | 0,83 / 0,93 | 0,699 | 0,6 | 0,71 / 0,90 |
| hybrid_rerank | 1,00 / 1,00 | 0,983 | 1,0 | 0,98 / 1,00 |
| vector + bge-m3 | 1,00 / 1,00 | 0,906 | 0,7 | 0,93 / 0,95 |
| hybrid (uni_bi) + bge-m3 | 1,00 / 1,00 | 0,933 | (xem tệp) | 0,95 / 0,98 |
McNemar chính xác hit@4 trên g30: p = 0,001 (hybrid), < 0,001 (rerank, bge-m3); b = 0 ở mọi biến thể (không câu nào baseline đúng mà biến thể sai); rerank và bge-m3 không phân biệt được ở n này.
**Leader tự chạy lại:** `--embedding bge-m3` cho `metrics` và `per_question` bằng tệp của Coder (True/True); chạy mặc định bằng `eval/report.json` (True/True); `pytest` 157 passed; `chroma_db/`, `knowledge_graph.graphml` không đổi.
Chi phí đo được (Coder, một lần): truy hồi nóng p50/p95: sbert 16/26 ms, hybrid 18/27 ms, rerank 418/493 ms (lượt đầu 6–11 s do nạp mô hình), bge-m3 254/322 ms; RSS đỉnh rerank 4,4–4,6 GB (sbert 1,5 GB), GPU toàn máy 4,2–4,4 GB; chỉ mục bge-m3 lớn hơn ~15–19%; thời gian dựng chỉ mục bge-m3 17–109 s giữa các lần (chỉ tin bậc độ lớn).

**Chưa thể chấp nhận biến thể nào (quy tắc mục 13):** (a) cả hai tập `reviewed`=0 nên tất cả là "thăm dò"; (b) điều kiện (iii) (`/chat` p95 <= 1,5x) CHƯA đo đầu-cuối, chỉ có proxy giai đoạn truy hồi; (c) chưa đo `T_ready` khi nạp bằng bge-m3: nhúng qua Ollama chậm hơn sbert nhiều lần (dựng chỉ mục 3 PDF 17–109 s) và có thể làm pha nhanh vượt ngưỡng P1-1 (<= 10 s); (d) chưa đo nạp đồng thời reranker + llama3.2 trên GPU 6 GB; (e) mỗi ô chạy một lần, không có phương sai.
**Mối đe doạ tính hợp lệ (quan trọng):** cả 30 và 42 câu hỏi do mô hình viết SAU khi đọc đoạn trích vàng, nên từ vựng câu hỏi trùng nhiều với văn bản đích; điều này có lợi cho BM25 và xếp hạng lại hơn so với câu hỏi thật của người dùng. Mức tăng 0,47 -> 1,00 có thể là CẬN TRÊN. Cần tập câu hỏi giữ ngoài (do người dùng viết, không nhìn trích dẫn) trước khi tin con số. Hit tính theo (tài liệu, trang), chỉ nhìn câu hỏi khi truy hồi (đã đọc mã, không thấy rò gold).
**Rủi ro sản phẩm đã ghi:** `cosine_score` = 0,0 cho đoạn chỉ do BM25 tìm ra (UI đang hiện điểm cosine); dùng bge-m3 phải nạp lại tài liệu vào bộ sưu tập riêng, không tự migrate; tách từ tiếng Việt mới là âm tiết; BM25 dựng trong RAM mỗi khi số đoạn đổi; `requirements*.txt` không đổi nhờ không thêm phụ thuộc.
**Ảnh hưởng tới thứ tự (bổ sung, không thay mục 13):** kết quả E3/E4 lớn hơn mọi kỳ vọng trước đó; E1 (Docling) và E2 hạ ưu tiên cho tới khi tập giữ ngoài xác nhận mức tăng, vì phần lớn khoảng cách có thể đã đóng bằng xếp hạng/nhúng mà không đổi trích xuất.

#### 13.3 Kiểm độc lập E3/E4 (Tester, thêm 2026-10-28; mẫu nhỏ, một máy; máy thiếu RAM: swap 2–3 GB, RAM trống có lúc 0,18 GB nên độ trễ nhiễu)
- **Không rò gold (đối chứng tiêu cực):** xoay câu hỏi i -> i+1 làm cả 4 biến thể tụt về 0,1–0,3 hit@4/8 (khác tài liệu gần 0; chọn ngẫu nhiên 5–9% hit@8). Dùng `gold_quote` làm truy vấn: sbert chỉ 0,67 hit@4, rerank và bge-m3 chạm trần.
- **Trùng từ vựng không nghiêng lợi rõ:** tỉ lệ âm tiết câu hỏi có trong `gold_quote` trung bình 0,30 (g30) và 0,26 (cand); hit không tăng theo mức trùng. Điều này làm yếu (không loại bỏ) mối nghi ở 13.2 rằng 0,47 -> 1,00 là cận trên do câu hỏi viết từ trích dẫn; vẫn cần tập giữ ngoài do chủ dự án viết (chờ chủ dự án gửi ~15 câu).
- **Đầu-cuối (n=6 cho `T_ready`; 10 câu x 3 lượt cho `/chat`):** `T_ready` `kmeans-vs-knn.pdf` (142 đoạn): sbert 3,08 s (sd 0,34), bge-m3 5,98 s (sd 0,42; 5,16–6,31); cả hai dưới ngưỡng P1-1 (<= 10 s); khi Ollama nguội lần nạp đầu bge-m3 tới 13,9 s. `/chat` p50/p95 (s): vector+sbert 2,09/5,22; baseline chạy lại 2,37/6,11 (nhiễu máy: p95 lệch x1,17); hybrid 2,44/5,16; hybrid_rerank 2,78/8,15 (p95 x1,33 so lần chạy lại, x1,56 so lần đầu); vector+bge-m3 3,19/5,13. Median tỉ số ghép cặp: hybrid 1,06, rerank 1,14, bge-m3 1,20. Điều kiện (iii): hybrid ĐẠT, vector+bge-m3 ĐẠT, hybrid_rerank median ĐẠT nhưng p95 không kết luận được ở n=30. TTS bị stub khi đo. RSS backend: sbert 1,4 GB, bge-m3 0,9 GB, rerank 4,2 GB; GPU toàn máy 5,8/6,1 GiB khi xếp hạng lại (gồm tiến trình khác và bge-m3 còn trong Ollama), không OOM, llama3.2 vẫn "100% GPU"; lượt `/chat` đầu của hybrid_rerank mất 11–23 s do nạp mô hình.
- **Chất lượng đáp án thật (8 mẫu, không kết luận thống kê):** Đúng/Một phần/Sai: sbert 2/1/5, bge-m3 5/2/1, rerank 7/0/1. Truy hồi đúng vẫn có thể ra "không biết": q13 ở rerank trả "không biết" 4/4 lượt dù nguồn hạng 1–2 đúng trang 14 (lỗi sinh của llama3.2 3B).
- **Kết luận:** hướng và độ lớn của mức tăng đáng tin hơn; con số "1,00" thì không (hit tính theo trang, 3 PDF nhỏ cùng chủ đề, không có tập giữ lại, 30 câu cũng dùng để chọn biến thể, một lần chạy mỗi ô, rerank và bge-m3 không phân biệt được ở n này). Vẫn CHƯA chấp nhận biến thể nào (cả hai tập `reviewed`=0).
- **Lỗi Tester tìm ra (để sửa):** (TB) `EMBEDDING=bge-m3` mà Ollama thiếu mô hình thì `/upload` trả 500 "Vector indexing failed." và job `failed` không nói nguyên nhân; (TB) đoạn chỉ do BM25 tìm ra có `cosine_score=0.0`, UI hiện `0.000` dù đoạn có thể đúng trang (ví dụ q25 ở hybrid_rerank, cả 4 nguồn 0.0); (thấp) cache BM25 khoá theo `id(collection)` và `count()` nên xoá một đoạn rồi thêm đoạn khác thì `KeyError` (chưa chạm tới được vì API không có đường xoá/thay tệp); (thấp) nạp reranker lười không có khoá, 3 luồng đồng thời có thể dựng 3 `CrossEncoder` (2,3 GB mỗi bản); (thấp) lượt đầu rerank chậm vì không prewarm. Hồi quy sạch: `pytest` 157 passed; `npm test` 163 pass; mặc định bằng `eval/report.json`.

#### 13.4 Sửa lỗi E3/E4 vòng 3 (thêm 2026-10-28; Leader tự chạy lại)
Đã sửa 5 lỗi ở 13.3: (1) `/upload` với `EMBEDDING!=sbert` ánh xạ lỗi Ollama khi nhúng như `/chat` (503 "Mô hình chưa được tải. Chạy `ollama pull <tên>`." có CORS; job `failed` mang cùng `error`; kiểm thật bằng backend thật + `OllamaEmbeddings("no-such-model")`); (2) đoạn chỉ do BM25 tìm ra có `cosine_score` thật từ embedding đã lưu, không lấy được thì `null` và giao diện hiện "—" (`SourceDoc.cosine_score` là `float | None`); (3) cache BM25 khoá theo băm sha1 của (id, văn bản) mọi đoạn; (4) nạp reranker có khoá (một `CrossEncoder`); (5) nạp trước reranker ở nền khi `RETRIEVAL=hybrid_rerank` (lỗi nạp chỉ log; chỉ kiểm bằng stub, chưa đo lượt đầu thật).
Leader chạy lại: `pytest` 165 passed; `quiz-app` 164 test pass; `evaluate_rag.py --live` mặc định có `metrics` và `per_question` bằng `eval/report.json`; `--retrieval hybrid` giữ nguyên kết quả cũ (True/True). Coder: `vector_bge-m3`, `hybrid_rerank`, `hybrid_bge-m3` ở `eval/p18/e34_v3/` giống `eval/p18/e34/` (lần đầu `hybrid_bge-m3` dùng nhầm `uni` nên khác; chạy lại đúng `uni_bi` thì khớp). `eval/report.json`, `eval/golden.jsonl` không đổi; dữ liệu thật không đổi.
**Chi phí mới (đo bởi Leader, mẫu nhỏ, một máy, một lần):** độ trễ truy hồi nóng của `hybrid` tăng từ p50/p95 17,9/26,6 ms lên 25,8/35,0 ms (+44% p50) vì mỗi truy vấn đọc lại mọi đoạn để băm cache; chi phí này tỉ lệ với số đoạn (O(N); trần ghi ở mã khoảng 10^5 đoạn), nhỏ so với `/chat` (vài giây) ở quy mô hiện tại (~400 đoạn) nhưng cần khoá cache bằng cách rẻ hơn (ví dụ phiên bản chỉ mục tăng khi nạp) nếu số đoạn lớn. Chưa chạy lại `cand`, `vector_sbert`, `hybrid_uni*` sau sửa; chưa chạy test mới trên mã cũ để xác nhận chúng đỏ trước khi sửa.
**Trạng thái P1.8:** E0 xong; E3/E4 cài sau cờ và đo thăm dò, độc lập đã kiểm; CHƯA chấp nhận biến thể nào (cần tập đã duyệt >= 45 câu và tập giữ ngoài do chủ dự án viết). Chờ chủ dự án: (a) ~15 câu hỏi thật; (b) duyệt `eval/p18/review_sheet.md`. Chưa quyết: đổi mặc định sang bge-m3 hay bật xếp hạng lại (cần nạp lại tài liệu, tách bộ sưu tập; chủ dự án quyết).
