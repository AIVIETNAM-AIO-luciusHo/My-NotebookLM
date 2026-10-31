# Hướng dẫn chạy MVP, đánh giá trước khi push, và lộ trình học

Ngày lập: 2026-10-28. Người viết: Leader (Claude). Người đọc: chủ dự án.
Mục đích: (1) báo cáo tiến độ trung thực; (2) chạy MVP trên máy bạn và có bảng chấm để quyết định push hay chưa; (3) biết cần học gì, theo thứ tự nào, để hiểu sâu từng phần của hệ thống.

Quy ước nhãn: **[ĐO]** = có con số từ lệnh chạy thật (mẫu nhỏ, một máy: RTX 3050 6 GB, WSL2, 11 GB RAM); **[KIỂM]** = một agent độc lập đã thử trên trình duyệt thật; **[CHƯA]** = chưa kiểm chứng; **[ƯỚC]** = suy luận, không phải số đo.

---

## Phần 1. Báo cáo tiến độ

### 1.1 Mục tiêu và vị trí hiện tại

Mục tiêu: tái tạo NotebookLM chạy cục bộ (nạp PDF, hỏi đáp có trích nguồn, quiz, mindmap; sau này slide sửa được), offline-first, 0 USD/tháng, có đường lên đám mây tuỳ chọn.

| Pha | Nội dung | Trạng thái |
|---|---|---|
| P0 | Đo baseline: độ trễ, nhiễu triplet, công cụ so sánh có kiểm định | Xong, đã merge |
| P0.5 | CI (GitHub Actions) + branch protection `main` | Xong, đã merge |
| P0.7 | Thử cắt đoạn theo token | Xong, **giữ `char`** (quy tắc đặt trước không đạt) |
| P1 | Nạp hai pha: `/upload` trả sau vài giây, đồ thị dựng nền | Xong, **chưa commit** |
| P1.6 | UI MVP core (3 cột, theo dõi job, lỗi tiếng Việt) | Xong, **chưa commit** |
| P1.7 | Trả nợ P1.6 (xoá job, PDF mật khẩu, bảng markdown...) | Xong, **chưa commit** |
| P1.5 | Notebook + `data_policy` (local/cloud) | **Chưa làm** |
| P2–P9 | Cổng/adapter, Groq, MinIO/Redis, Pinecone/Neo4j, hybrid+reranker, slide sửa được, quiz đa dạng, Docker+CD | **Chưa làm** |

Mã đang nằm trên nhánh `feat/long-flow`, chưa commit. `main` vẫn là bản đã merge PR #9.

### 1.2 Những gì chạy được (đã kiểm)

- Nạp PDF: pha nhanh (đọc, cắt đoạn, embed, ghi ChromaDB) xong sau khoảng 4 s với PDF 142 đoạn **[ĐO, Tester]**; pha đồ thị (LLM trích bộ ba) chạy nền, khoảng 5 phút cho 142 đoạn **[ĐO, Tester, một lần]**.
- Hỏi đáp có nguồn (tên tệp, trang, điểm cosine): 5,6–26,6 s mỗi câu tuỳ lúc Ollama nóng hay nguội **[ĐO]**; vẫn trả lời được khi đồ thị đang dựng, kèm cờ "chưa dùng đồ thị" **[KIỂM]**.
- Quiz: khoảng 9–12 s cho 5 câu **[ĐO]**; Mindmap: 4–13 s **[ĐO]**.
- Job nền sống sót khi backend bị `kill -9`: khởi động lại hiện "Bị gián đoạn" + "Tiếp tục", chạy tiếp tới xong, số đoạn trong Chroma không đổi **[KIỂM]**. Giới hạn: lúc kill, job mới ở 0/142, chưa thử resume từ giữa chừng.
- Lỗi hiện đúng thông báo tiếng Việt: PDF hỏng, PDF có mật khẩu, không phải PDF, Ollama chưa chạy, mô hình chưa tải, backend tắt **[KIỂM]**.
- Kiểm thử tự động: `pytest` 141 pass; `quiz-app` 163 test; lint, build, 1 e2e Playwright xanh **[ĐO]**. CI chưa chạy trên các thay đổi này (chưa push).

### 1.3 Chất lượng truy hồi (baseline, chưa cải thiện)

Bộ vàng 30 câu (`eval/golden.jsonl`), truy hồi chỉ vector **[ĐO, mẫu nhỏ]**:

| Chỉ số | Giá trị | Ý nghĩa |
|---|---|---|
| hit@4 | 0,467 | 14/30 câu có đoạn đúng nằm trong top-4 |
| hit@8 | 0,767 | 23/30 câu, nếu lấy top-8 |
| MRR | 0,439 | đoạn đúng trung bình đứng khoảng hạng 2–3 |
| cover@8 (multi-hop) | 0,10 | câu cần ghép nhiều đoạn gần như không bao phủ đủ |

Sai số chuẩn khoảng ±0,18 với n=30: **không thể khẳng định cải tiến nhỏ hơn mức đó**. Đây là lý do mọi thay đổi truy hồi sau này phải so sánh ghép cặp (McNemar) chứ không so trung bình. Chỉ 6/30 câu vàng đã được bạn tick `reviewed:true`; 24 câu còn lại là đề xuất của máy chưa được người duyệt.

Hệ quả thật: nếu bạn hỏi và nhận câu trả lời sai/thiếu, đó **là hành vi đã đo được**, không phải lỗi mới. Truy hồi chỉ vector, top-4, chưa hybrid/reranker (P6).

### 1.4 Điều chưa làm hoặc chưa biết

- **[CHƯA]** Chất lượng câu trả lời (không chỉ truy hồi): chưa có đo RAGAS/faithfulness trên bộ vàng.
- **[CHƯA]** Đồ thị có thực sự giúp trả lời hay không: chưa có thí nghiệm "có đồ thị" so với "không đồ thị" (ablation). Triplet do llama3.2 3B trích có nhiễu (đã đo ở P0, xem `docs/data/`/PLAN mục 7b).
- **[CHƯA]** Chip độ khó `Dễ/Vừa/Khó` đổi từ `Easy/Normal/Hard`: thử 1 mẫu mỗi mức, Dễ và Vừa gần giống nhau.
- **[CHƯA]** Tiếng Việt trong nhúng: sbert không tách từ tiếng Việt trước khi nhúng (ý tưởng D9, chưa thử).
- Nợ kỹ thuật còn lại ghi ở `PLAN.md` mục 5c và mục 12: Ollama client chưa có timeout; upload lỗi 400 vẫn tạo hàng job `failed`; `/generate-*` chưa được worker nhường (tỉ số 1,30–1,45, sát ngưỡng 1,5 **[ĐO, n nhỏ]**); mỗi `/chat` sao chép cả đồ thị.
- Quyền riêng tư: **gTTS gửi văn bản câu trả lời tới Google** ở mọi `/chat`; chưa có `data_policy` để tắt (P1.5). Giao diện không còn tự phát âm thanh, nhưng backend vẫn sinh.

### 1.5 Rủi ro lớn nhất hiện tại (theo thứ tự)

1. **Dồn 5 pha vào một nhánh chưa commit.** Một lần `git checkout` sai có thể mất việc, và lịch sử khó đọc. Hãy commit theo gợi ý ở `PLAN.md` mục 12 trước khi làm gì khác.
2. **Chưa có người dùng thật nào dùng thử.** Mọi số liệu hiện là từ 3 PDF kỹ thuật của chính bạn, một máy.
3. **`requirements.txt` ghim bộ cũ** (langchain 0.3.7, fastapi 0.110) đã kiểm trên CI sạch, còn `.venv` của bạn dùng bản mới hơn. Chưa có ai chạy backend bằng đúng bộ ghim trên máy bạn ngoài thí nghiệm venv tạm.

---

## Phần 2. Chạy MVP trên máy bạn

### 2.1 Kiểm tra điều kiện (đã kiểm 2026-10-28 trên máy bạn)

| Thứ cần | Hiện có |
|---|---|
| `.venv` Python 3.12.3 ở gốc repo | có |
| Ollama + `llama3.2:latest` | có, đang lắng nghe `127.0.0.1:11434` |
| Node 22.22.3 | có |
| GPU RTX 3050 6 GB | có (477 MiB đang dùng) |
| PDF thử | `/home/lucius/Project/Learning-AI-engineer/docs/kmeans-vs-knn.pdf` (và `probability-vs-statistics.pdf`, `bao-cao-bien-doi-gradient.pdf`) |

### 2.2 Chọn chế độ dữ liệu: ĐỌC KỸ TRƯỚC KHI CHẠY

Backend mặc định ghi vào `chroma_db/`, `knowledge_graph.graphml`, `jobs.sqlite` ở gốc repo. Hai tệp đầu là dữ liệu thật của bạn và đã từng bị mất hai lần khi đổi nhánh.

- **Chế độ SẠCH (khuyến nghị cho đánh giá):** trỏ ba đường dẫn vào thư mục tạm; xoá thư mục là xong, dữ liệu thật không bị đụng.
- **Chế độ THẬT:** không đặt biến môi trường; dữ liệu tích luỹ và còn sau khi tắt. Chỉ dùng khi bạn muốn giữ.

### 2.3 Bật ba thứ (ba cửa sổ terminal)

**Terminal A. Ollama** (bạn đã có sẵn; kiểm tra bằng lệnh dưới, không cần khởi động lại):

```bash
curl -s localhost:11434/api/tags | head -c 150
# nếu lỗi: ollama serve   (để chạy ở terminal riêng)
```

**Terminal B. Backend**, chế độ SẠCH:

```bash
cd ~/Project/My-NotebookLM
export MVP_DIR=$(mktemp -d /tmp/mvp-XXXX); echo "$MVP_DIR"
CHROMA_PATH="$MVP_DIR/chroma" GRAPH_PATH="$MVP_DIR/graph.graphml" JOBS_DB_PATH="$MVP_DIR/jobs.sqlite" \
  .venv/bin/python -m uvicorn backend:app --app-dir src --port 8000
```

Chế độ THẬT: bỏ ba biến `CHROMA_PATH=... GRAPH_PATH=... JOBS_DB_PATH=...` ở đầu lệnh.

Đợi tới khi thấy `Application startup complete`. **Lần đầu mô hình `keepitreal/vietnamese-sbert` nạp mất khoảng 45 s [ĐO]**; trong lúc đó `/health` chưa trả lời. Kiểm tra:

```bash
curl -s localhost:8000/health
# kỳ vọng: {"status":"ok", ..., "chunk_count":0, "graph_ready":true ...}
```

**Terminal C. Giao diện:**

```bash
cd ~/Project/My-NotebookLM/quiz-app
npm install          # chỉ lần đầu
npm run dev          # mở http://localhost:5173
```

> **Bẫy hay gặp:** mở `http://localhost:5173`, **không phải** `http://127.0.0.1:5173`. Backend chỉ cho CORS các origin `localhost:5173` và `localhost:5174` (`src/backend.py`, `_CORS_ORIGINS`). Mở bằng `127.0.0.1` sẽ ra "Backend đang tắt" dù backend sống.

### 2.4 Mười kịch bản đánh giá (làm theo thứ tự; ghi vào cột cuối)

Ngày giờ máy, ai làm, kết quả: ghi lại để so sánh sau này. Mỗi kịch bản có "kỳ vọng" để bạn biết lúc nào là đạt.

| # | Việc làm | Kỳ vọng | Ghi chú của bạn |
|---|---|---|---|
| 1 | Mở `localhost:5173`. Thanh trên: chấm "Backend: hoạt động" | xanh; cột Nguồn trống, hiện hướng dẫn | |
| 2 | Kéo `kmeans-vs-knn.pdf` vào ô Nguồn, bấm "Nạp tài liệu". **Bấm đồng hồ.** | trả lời sau vài giây; hàng "Tác vụ nền" chạy tới `graph_running` | thời gian: ___ s |
| 3 | Trong lúc đồ thị đang dựng (hàng job chưa `Hoàn tất`), hỏi: *"Theo phần tóm tắt, k-NN thuộc loại học nào và K-means thuộc loại học nào?"* | có câu trả lời (khoảng 5–25 s), có cờ vàng "Đồ thị chưa đầy đủ", nguồn kèm tên tệp, số trang, cosine. Đáp án đúng: *k-NN có giám sát; K-means không giám sát* | trả lời đúng? ___ ; thời gian ___ s |
| 4 | Câu số liệu: *"Khi số chiều d vượt khoảng bao nhiêu thì KD-Tree suy biến về tìm kiếm vét cạn?"* (đáp án: khoảng 20) và *"Theo chặn Cover–Hart, sai số tiệm cận của 1-NN không quá bao nhiêu lần sai số của bộ phân loại tối ưu?"* (đáp án: gấp đôi) | xem câu trả lời có nêu đúng số; xem nguồn có đúng trang chứa số đó không | đúng? ___ / ___ |
| 5 | Câu multi-hop (khó): *"Vì sao ngoại lai làm hỏng K-means, và nếu đổi hàm mục tiêu sang tổng chuẩn L1 thì tâm cụm tối ưu là gì?"* (đáp án: trung bình không bền với ngoại lai; chuẩn L1 cho trung vị) | baseline đo được: loại câu này **hay trượt**; ghi lại đúng/sai để thấy giới hạn thật | đúng? ___ |
| 6 | Khi job xong (`Hoàn tất`), hỏi lại câu 5 | so với lúc đồ thị chưa xong: có khác không? Cờ vàng biến mất | khác? ___ |
| 7 | Chuyển tab Studio, "Quiz": chủ đề "K-means", độ khó "Vừa", 5 câu, "Tạo và làm quiz" | khoảng 9–12 s; 5 câu; làm bài, xem điểm, "Xem lại" | số câu đúng nội dung? ___ /5 |
| 8 | Tab "Mindmap": tự sinh sơ đồ; bấm "Tạo lại" | sơ đồ cây hiện; nút nằm trọn trong khung | |
| 9 | **Kill giữa chừng:** nạp PDF thứ hai (`probability-vs-statistics.pdf`), khi job ở `graph_running`, ở terminal khác chạy `pkill -9 -f "uvicorn backend:app"`, rồi bật lại backend (cùng lệnh, **cùng `MVP_DIR`**), tải lại trang | hàng job "Bị gián đoạn" + nút "Tiếp tục"; bấm thì chạy tiếp tới xong; số đoạn không đổi (`curl localhost:8000/health`) | |
| 10 | **Lỗi:** (a) kéo một file `.txt` vào ô Nguồn; (b) nạp file rác: `echo junk > /tmp/junk.pdf` rồi nạp | (a) "Không phải tệp PDF"; (b) "PDF không đọc được"; mỗi lỗi có nút "Xoá" ở hàng job (b) | |

**Thử Ollama chưa chạy mà không tắt Ollama của bạn** (backend phụ trên cổng 8001, giao diện phụ trên 5174 trỏ vào nó):

```bash
# terminal D
cd ~/Project/My-NotebookLM
OLLAMA_HOST=127.0.0.1:11999 CHROMA_PATH=/tmp/mvp-x/c GRAPH_PATH=/tmp/mvp-x/g.graphml JOBS_DB_PATH=/tmp/mvp-x/j.sqlite \
  .venv/bin/python -m uvicorn backend:app --app-dir src --port 8001
# terminal E
cd quiz-app && VITE_BACKEND=http://127.0.0.1:8001 npm run dev -- --port 5174   # mở http://localhost:5174
```

Nạp một PDF rồi hỏi: kỳ vọng khung "Ollama chưa sẵn sàng" (không phải "Backend đang tắt"). Đóng terminal D và E khi xong.

### 2.5 Bảng chấm trước khi push

Đánh dấu khi bạn đã tự thử. Gợi ý ngưỡng của mình, bạn có quyền đổi:

| Hạng mục | Ngưỡng "đủ để push" | Đạt? |
|---|---|---|
| Kịch bản 1–2, 7, 8, 10 | tất cả chạy đúng kỳ vọng | |
| Kịch bản 3 | trả lời trong lúc đồ thị dựng, không lỗi | |
| Kịch bản 9 | resume chạy tới xong | |
| Kịch bản 4–6 | **không có ngưỡng đúng/sai**: đây là chất lượng truy hồi đã biết là mới 47–77%; hãy ghi lại để so với P6 | ghi nhận |
| `pytest tests -q` | 0 failed | |
| `cd quiz-app && npm run lint && npm test && npm run build` | xanh | |
| Không có bí mật trong thay đổi | `git diff` không có khoá, token, đường dẫn riêng | |

Nếu có hạng mục "đủ để push" không đạt: ghi lại chính xác bước làm, thông báo thấy, giờ chạy, rồi đưa cho mình xử lý (Coder/Tester). Đừng sửa tay trên nhánh đang chờ commit.

### 2.6 Dọn dẹp sau khi thử

```bash
# Ctrl+C ở các terminal B, C (D, E nếu có)
rm -rf "$MVP_DIR" /tmp/mvp-x          # chỉ chế độ SẠCH; không đụng dữ liệu thật
cd ~/Project/My-NotebookLM && git status --short | head   # kiểm tra không có tệp lạ
```

### 2.7 Khi gặp sự cố

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| UI ghi "Backend đang tắt" nhưng `curl localhost:8000/health` được | mở bằng `127.0.0.1` thay vì `localhost` (CORS) | mở lại `http://localhost:5173` |
| `curl /health` không trả lời ~1 phút sau khi bật backend | đang nạp sbert (≈45 s) | chờ `Application startup complete` |
| `Address already in use` | còn tiến trình cũ trên cổng 8000 hoặc 5173 | `ss -ltnp \| grep -E ':8000\|:5173'` rồi tắt đúng tiến trình |
| Hỏi đáp rất chậm (>1 phút) lần đầu | Ollama đang nạp `llama3.2` vào GPU | hỏi lại; lần sau nhanh hơn |
| Job `failed` "Không kết nối được Ollama" | Ollama không chạy | bật Ollama rồi bấm "Tiếp tục" |
| Lỗi import khi bật backend | dùng nhầm Python hệ thống | luôn dùng `.venv/bin/python` |

---

## Phần 3. Cần học gì để hiểu sâu

Nguyên tắc: học theo hệ thống bạn đã có, không học dàn trải. Mỗi mô-đun có (a) vì sao quan trọng ở dự án này, (b) đọc ở đâu trong mã, (c) tài liệu, (d) bài thực hành chạy được, (e) câu tự kiểm tra: **nếu trả lời được hết bằng lời của mình, bạn đã hiểu**.

Sách nội bộ `docs/book/NotebookLM-Sach.pdf` (110 trang, 9 chương + phụ lục, chỉ có trên máy bạn; `.tex` cũng ở `docs/book/`) là tài liệu chính; mỗi mô-đun trỏ tới chương tương ứng. Sách viết trước P1.6/P1.7 nên phần UI/job có thể lỗi thời; sự thật nằm ở mã và `PLAN.md`.

### Mô-đun 1. Embedding, cosine, HNSW, chunking (nền tảng của mọi thứ)

- **Vì sao:** chất lượng truy hồi 47–77% xuất phát từ đây. Muốn cải thiện (P6) phải hiểu thứ đang hỏng.
- **Mã:** `src/backend.py`: `_get_collection()` (`hnsw:space=cosine`), cắt đoạn `char` 600/75 và nhánh `token`, `_query_workspace()`; `eval/chunk_stats.py` (thấy 15–20% đoạn vượt 256 token của sbert và bị cắt âm thầm).
- **Sách:** chương 3 (nền tảng RAG), chương 5 (đo lường).
- **Tài liệu:** bài báo *Sentence-BERT* (Reimers và Gurevych, 2019); bài báo *HNSW* (Malkov và Yashunin, 2016); phần "Embeddings" và "Distance metrics" trong tài liệu chính thức của ChromaDB; sách `natural-language-processing-with-transformers` trong `Learning-AI-engineer/docs/`.
- **Thực hành (30 phút):**
  ```bash
  cat eval/p07/chunk_stats.json | head -40      # số đoạn >256 token của từng PDF, kết quả đã đo sẵn
  EVAL_PDF_DIR=$HOME/Project/Learning-AI-engineer .venv/bin/python src/evaluate_rag.py --live --out /tmp/r.json
  ```
  (Đừng chạy lại `eval/chunk_stats.py` chỉ để xem: nó ghi đè `eval/p07/chunk_stats.json`.) Mở `/tmp/r.json`, tìm 3 câu `hit@4` sai; với mỗi câu, mở `eval/golden.jsonl` xem `gold_quote` và đoạn thật nằm ở hạng nào.
- **Tự kiểm tra:** (1) Vì sao `distance = 1 − cosine` khi dùng `hnsw:space=cosine`? (2) Một đoạn dài hơn `max_seq_length=256` token sẽ ra sao khi nhúng? (3) Vì sao tăng top-k từ 4 lên 8 tăng hit từ 0,47 lên 0,77 nhưng không phải là "cải tiến"? (4) HNSW là gần đúng: vì sao bộ đánh giá đặt 1 luồng và `ef=1000`?

### Mô-đun 2. GraphRAG và đồ thị tri thức

- **Vì sao:** đồ thị là điểm khác biệt của dự án, nhưng **chưa có bằng chứng nó giúp** (xem 1.4). Bạn cần hiểu để quyết định có giữ không.
- **Mã:** `src/backend.py`: `_parse_triplets()`, trích triplet bằng llama3.2 (nhiệt độ 0,0), ghép nút theo chữ thường, `_build_hybrid_context()`, mở rộng 1–2 bước; `eval/p0_triplet_noise.py` và `eval/p0/*.json` (đo nhiễu).
- **Sách:** chương 4 (giải phẫu hệ thống hiện tại).
- **Tài liệu:** bài báo *From Local to Global: A Graph RAG Approach to Query-Focused Summarization* (Microsoft, 2024); tài liệu NetworkX về `DiGraph`, `ego_graph`.
- **Thực hành:** sau khi đồ thị dựng xong ở kịch bản 2, chạy:
  ```bash
  .venv/bin/python - <<'EOF'
  import networkx as nx, os
  g = nx.read_graphml(os.environ["GRAPH_PATH"])
  print(g.number_of_nodes(), g.number_of_edges())
  for u, v, d in list(g.edges(data=True))[:15]: print(u, "-", d.get("relation"), "->", v)
  EOF
  ```
  (đặt `GRAPH_PATH` đúng như lúc bật backend). Đọc 15 cạnh đầu và tự chấm: bao nhiêu cạnh đúng nghĩa so với tài liệu? Đó là "nhiễu triplet" bằng tay.
- **Tự kiểm tra:** (1) Vì sao hai chuỗi "Marie Curie" và "marie curie" ra cùng một nút? (2) Khi nào mở rộng 2 bước làm tệ hơn mở rộng 1 bước? (3) Thí nghiệm nào chứng minh đồ thị giúp (hoặc không)? Hãy thiết kế bằng lời: nhóm so sánh, chỉ số, kiểm định.

### Mô-đun 3. Đánh giá RAG (đây là phần phân biệt kỹ sư AI với người dùng API)

- **Vì sao:** không đo thì không biết thay đổi tốt hay xấu; n=30 rất nhỏ nên cách so sánh quyết định kết luận.
- **Mã:** `eval/golden.jsonl` (schema: `id, doc, question, answer, gold_pages, gold_quote, type, reviewed`), `src/evaluate_rag.py`, `eval/compare.py` (McNemar chính xác ghép cặp), `tests/test_eval_compare.py`, `tests/test_golden_schema.py`; quy tắc quyết định đặt trước trong `PLAN.md` mục 9 (P0.7).
- **Sách:** chương 5 trọn vẹn.
- **Tài liệu:** hit@k, MRR (tài liệu *Introduction to Information Retrieval*, Manning et al.); kiểm định McNemar; BEIR benchmark; RAGAS (đã có trong `requirements.txt`).
- **Thực hành:**
  ```bash
  .venv/bin/python -m eval.compare eval/p07/report_char.json eval/p07/report_token.json --metric hit@8
  ```
  Đọc kết quả `b, c` (số câu đổi từ sai sang đúng và ngược lại) và p-value. Tự giải thích vì sao 23/30 so với 21/30 chưa phải khác biệt có ý nghĩa thống kê.
  Rồi **duyệt tay 5 câu vàng** `reviewed:false`: đọc `gold_quote` trong PDF thật, sửa nếu sai, đặt `reviewed:true`. Mỗi câu bạn duyệt làm baseline đáng tin hơn.
- **Tự kiểm tra:** (1) hit@k và MRR khác nhau thế nào, câu nào hợp "lần đầu có đúng đoạn" hơn? (2) Với n=30, SE ≈ 0,18 nghĩa là gì? (3) Vì sao phải đặt quy tắc quyết định **trước** khi chạy thí nghiệm (xem P0.7 và P1-2: quy tắc đã chặn một kết luận sai)? (4) Vì sao P1-2 vòng 2 "đạt" 0,816 mà vẫn bị loại?

### Mô-đun 4. Backend đồng thời: event loop, threadpool, khoá

- **Vì sao:** lỗi nghiêm trọng nhất ở P1.6–P1.7 là loại này (`async def` gọi LLM đồng bộ làm `/health` mất 3,7 s; lỗi 500 không có CORS bị nhầm là backend tắt).
- **Mã:** `src/backend.py`: `/chat`, `/generate-quiz`, `/generate-mindmap` (hàm `def` chạy trong threadpool), `_graph_lock` (RLock), `_chat_active` + cooldown (worker đồ thị nhường `/chat`), `@app.exception_handler(Exception)` `_unhandled_error` (lý do phải tự gắn CORS); `tests/test_generate_threadpool.py` (dùng `threading.Event` thay `sleep`).
- **Sách:** chương 7 (nạp tài liệu nhanh), phần ngân sách thời gian chương 1.
- **Tài liệu:** tài liệu FastAPI mục *Concurrency and async/await*; sách `FAST API.pdf` trong `Learning-AI-engineer/docs/`; tài liệu Python về `threading` (Lock, RLock, Condition, Event) và GIL.
- **Thực hành:** bật backend, ở terminal khác chạy trong lúc đang tạo mindmap:
  ```bash
  for i in $(seq 20); do curl -s -o /dev/null -w "%{time_total}\n" localhost:8000/health; sleep 0.3; done
  ```
  Thời gian `/health` phải vài ms. Rồi tự đổi `def generate_mindmap` thành `async def` **trên bản sao**, chạy lại, quan sát `/health` đứng.
- **Tự kiểm tra:** (1) Vì sao `async def` gọi hàm đồng bộ chặn cả server? (2) Vì sao gọi LLM **ngoài** khoá đồ thị? (3) Vì sao lỗi 500 từ `ServerErrorMiddleware` không có header CORS? (4) Quy tắc 1,5× của D2 đo cái gì, và vì sao đo bằng median ghép cặp?

### Mô-đun 5. Job nền, bền vững và hồi phục

- **Vì sao:** đây là cách tách "nạp nhanh" khỏi "dựng đồ thị chậm", và nền tảng cho Celery/Redis sau này (P4).
- **Mã:** `src/jobs.py` (sqlite3, `Worker` một luồng, `claim()` compare-and-set, `mark_interrupted()`), `src/backend.py` (`_fast_phase`, pha đồ thị, `/jobs`, `resume`, `DELETE /jobs/{id}`), `tests/test_jobs.py`, `tests/test_two_phase_upload.py`; sơ đồ `docs/architecture/ingest-two-phase.mmd`.
- **Sách:** chương 7.
- **Tài liệu:** tài liệu SQLite (transactions, WAL); "idempotency" và "at-least-once"; mô hình máy trạng thái hữu hạn.
- **Thực hành:** làm kịch bản 9 xong, mở CSDL job:
  ```bash
  sqlite3 "$MVP_DIR/jobs.sqlite" "select id,status,chunks_done,chunks_total,error from jobs;"
  ```
  (nếu thiếu `sqlite3`: `.venv/bin/python -c "import sqlite3,sys;[print(r) for r in sqlite3.connect(sys.argv[1]).execute('select * from jobs')]" "$MVP_DIR/jobs.sqlite"`). Vẽ tay máy trạng thái `queued → fast_running → fast_done → graph_running → done|failed|interrupted` và nêu bước nào kill gây hậu quả gì.
- **Tự kiểm tra:** (1) Vì sao chỉ tăng `chunks_done` sau khi đã lưu `.graphml`? (2) `claim()` giải quyết lỗi gì khi hai request cùng `resume`? (3) Vì sao job `failed` ở pha nhanh không cho "Tiếp tục"? (4) SQLite chịu được những gì và vỡ ở đâu (nhiều tiến trình)?

### Mô-đun 6. Kiểm thử, CI/CD, an toàn chuỗi cung ứng

- **Vì sao:** "quy trình công nghiệp" bạn nhắc: PR bắt buộc, CI xanh, không bí mật trong repo.
- **Mã:** `.github/workflows/ci.yml` (3 job: `frontend`, `backend`, `secrets`; action ghim SHA; gitleaks ghim phiên bản + sha256), `requirements-ci.txt` vs `requirements.txt`, `tests/conftest.py`, mutation tay (xem báo cáo Tester).
- **Sách:** phần CI trong chương 8; `docs/ARCHITECTURE.md` mục 7.
- **Tài liệu:** tài liệu GitHub Actions và Branch protection; OWASP về supply chain; "mutation testing" (khái niệm).
- **Thực hành:** chạy cả bộ như CI:
  ```bash
  .venv/bin/python -m pytest tests -q
  cd quiz-app && npm run lint && npm test && npm run build && npm run e2e
  ```
  Rồi phá một dòng trong một **bản sao** của `src/backend.py` (ví dụ đổi mã 503 thành 500 ở handler) và xem test nào fail. Đó là cách đo "test có thật sự bắt lỗi không".
- **Tự kiểm tra:** (1) Vì sao ghim SHA của action tốt hơn ghim tag? (2) Vì sao CI không chạy `eval/` thật? (3) Một test dùng `sleep` làm điều kiện sai ở đâu? (4) `pip check` sạch mà `datasets` vẫn không import được (pyarrow/NumPy): bài học gì về kiểm thử môi trường?

### Mô-đun 7. Frontend: lớp API, trạng thái, lỗi

- **Vì sao:** UI đúng hay sai nằm ở cách nó diễn giải lỗi; phần lớn lỗi P1.6 là "hiển thị sai nguyên nhân".
- **Mã:** `quiz-app/src/lib/api.js` (lớp gọi duy nhất, hằng timeout `T_FAST`, `T_UPLOAD`, `T_LLM`, `ApiError`), `utils/errorView.js`, `utils/jobs.js`, `hooks/useJobs.js`, `hooks/useHealth.js`, `components/pages/WorkspaceDashboard.jsx`, `components/ui/StatePanel.jsx`, `components/ui/RichText.jsx`; test trong `quiz-app/tests/domain/` (`node --test`), `quiz-app/e2e/smoke.spec.js` (Playwright, backend giả).
- **Tài liệu:** tài liệu React về `useEffect` và dọn dẹp (cleanup), thiết kế "state machine" cho UI; tài liệu Playwright; MDN về CORS và `fetch` + `AbortController`.
- **Thực hành:** đọc `errorView.js`, rồi tự thêm (trên bản sao) một loại lỗi mới, viết test cho nó trước bằng `node --test`.
- **Tự kiểm tra:** (1) Vì sao tách logic thuần (`utils/jobs.js`) khỏi hook? (2) Vì sao trình duyệt coi 500 không có CORS là "lỗi mạng"? (3) Vì sao mặc định 503 được coi là "Ollama" còn chữ "ollama" ngẫu nhiên trong lỗi 500 thì không?

### Mô-đun 8. Thiết kế hệ thống: cổng và adapter, `data_policy`

- **Vì sao:** P1.5–P9 xoay quanh đây; quyết định kiến trúc đã chốt nằm ở đó.
- **Mã/tài liệu:** `docs/ARCHITECTURE.md`, `docs/architecture/{current,target,roadmap,data-policy}.mmd` (mở bằng trình xem Mermaid), `PLAN.md` mục 2 (bất biến), mục 3, mục 8 (quyết định D2–D16).
- **Sách:** chương 2 (tư duy thiết kế hệ thống), chương 6 (đã làm và chưa làm), chương 8 (lộ trình).
- **Tài liệu:** *Ports and Adapters* (Alistair Cockburn, "Hexagonal architecture"); *Designing Data-Intensive Applications* (Kleppmann) các chương về lưu trữ và xử lý lô.
- **Thực hành:** vẽ tay (giấy) luồng của một lượt `/chat` hiện tại và chỉ ra 5 chỗ sẽ thành "cổng" (VectorStore, GraphStore, LLM, ObjectStore, JobQueue); rồi tự trả lời: notebook `local` gặp lỗi cấu hình Groq thì hệ thống làm gì? (đáp án đã chốt: từ chối, không âm thầm đổi chỗ.)
- **Tự kiểm tra:** (1) Vì sao TTS không phải một cổng? (2) Vì sao mọi adapter mới phải chạy lại `eval/` ghép cặp? (3) Thứ tự P1.5 → P2 tối thiểu hoá rủi ro như thế nào?

### 3.9 Lịch học gợi ý (khoảng 10 buổi, mỗi buổi 1,5–2 giờ; điều chỉnh theo bạn)

| Buổi | Nội dung | Sản phẩm bạn mang ra |
|---|---|---|
| 1 | Phần 2 trọn vẹn (chạy MVP, 10 kịch bản) | bảng ghi chú đã điền, danh sách lỗi/điều lạ |
| 2 | Mô-đun 1 (embedding, chunking) + sách ch.3 | giải thích bằng lời vì sao có 15–20% đoạn bị cắt |
| 3 | Mô-đun 3 (đánh giá) + sách ch.5 + duyệt 5 câu vàng | 5 câu `reviewed:true` đã kiểm nguồn |
| 4 | Mô-đun 2 (đồ thị) | bản chấm tay 15 cạnh; thiết kế thí nghiệm ablation |
| 5 | Mô-đun 4 (đồng thời) | tái hiện được `/health` đứng khi dùng `async def` |
| 6 | Mô-đun 5 (job) | sơ đồ máy trạng thái vẽ tay + kịch bản kill |
| 7 | Mô-đun 6 (CI/test) | phá được 3 dòng và chỉ ra test bắt |
| 8 | Mô-đun 7 (frontend) | thêm 1 loại lỗi có test |
| 9 | Mô-đun 8 (kiến trúc) + `docs/ARCHITECTURE.md` | luồng `/chat` 5 cổng vẽ tay |
| 10 | Tổng kết: tự giải thích cả hệ thống 10 phút không nhìn tài liệu | ghi âm hoặc ghi chép |

Mốc kiểm "đã hiểu sâu": bạn tự viết được **thiết kế một thí nghiệm** (giả thuyết, nhóm so sánh, chỉ số, quy tắc quyết định đặt trước, kiểm định) cho câu hỏi "đồ thị tri thức có cải thiện câu multi-hop không?", rồi để mình giao Coder/Tester chạy.

---

## Phần 4. Việc nên làm tiếp (đề xuất, bạn quyết định)

1. Chạy Phần 2 và điền bảng 2.4/2.5.
2. Commit theo gợi ý ở `PLAN.md` mục 12 (5 commit; không dòng ghi công Claude), mở PR, đợi CI xanh lần đầu cho bộ `requirements-ci.txt` mới.
3. Duyệt thêm câu vàng (Mô-đun 3) để baseline đáng tin hơn trước P6.
4. Chọn pha tiếp: P1.5 (Notebook + `data_policy`, cần trước mọi thứ cloud và để tắt gTTS cho notebook local) hoặc đi thẳng P6 (hybrid + reranker) nếu chất lượng truy hồi ở kịch bản 4–6 làm bạn không hài lòng; slide sửa được (P7) và quiz đa dạng (P8) phụ thuộc P6 hơn là P1.5.

*Mọi con số ở trên là mẫu nhỏ, một máy; mọi chỗ ghi [CHƯA]/[ƯỚC] là điều mình chưa chứng minh được.*
