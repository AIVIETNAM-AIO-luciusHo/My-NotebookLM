# P1.8 E3 + E4 — tìm kiếm lai, xếp hạng lại, bge-m3 (THĂM DÒ; mẫu nhỏ, một máy)

Mọi số: RTX 3050 6 GB, WSL2, 11 GB RAM, Ollama của chủ dự án đang chạy, một lần chạy mỗi ô (không lặp, không khoảng tin cậy). HNSW 1 luồng, ef=1000 (gần vét cạn, tất định). Cả hai tập đều `reviewed` = 0 theo `meta` của báo cáo (30 câu cũ và 42 ứng viên chưa ai duyệt đáp án), nên theo mục 13 TẤT CẢ là "thăm dò"; hai tập báo RIÊNG, không gộp. Không có tập xác nhận (< 45 câu đã duyệt) nên KHÔNG có kết luận chấp nhận thật; cột "chấp nhận" chỉ là áp công thức của quy tắc (i)-(iii).

## Tái lập
```
export EVAL_PDF_DIR=/home/lucius/Project/Learning-AI-engineer
.venv/bin/python -m eval.p18_e34 run vector_sbert hybrid_uni hybrid_uni_bi vector_bge-m3 hybrid_rerank
BM25_BEST=uni_bi .venv/bin/python -m eval.p18_e34 run hybrid_bge-m3     # biến thể BM25 tốt hơn, xem dưới
.venv/bin/python -m eval.p18_e34 summary                                  # in các bảng dưới đây
# một biến thể đơn lẻ:
.venv/bin/python src/evaluate_rag.py --live --retrieval hybrid --embedding bge-m3 --bm25-tokens uni_bi --golden eval/golden.jsonl --out /tmp/x.json
# so ghép cặp (b, c, p McNemar chính xác):
.venv/bin/python -m eval.compare eval/p18/e34/g30_vector_sbert.json eval/p18/e34/g30_hybrid_rerank.json
```
Kết quả thô: `eval/p18/e34/{g30,cand}_<biến thể>.json` (`metrics`, `per_question`, `perf`, `meta`). Cờ: `RETRIEVAL=vector|hybrid|hybrid_rerank`, `EMBEDDING=sbert|bge-m3`, `BM25_TOKENS=uni|uni_bi`; mặc định = hành vi cũ (đã kiểm: `metrics` và `per_question` của `g30_vector_sbert.json` bằng `eval/report.json`).

## Quy tắc chọn biến thể BM25 cho hàng hybrid+bge-m3
Quy tắc nêu trong dispatch chỉ nói "biến thể tốt hơn từ hàng trên"; tôi đặt (trước khi chạy hàng đó, trên tập g30 hybrid+sbert): hit@8 cao hơn thắng, hoà thì MRR. g30: uni hit@8 0,9333 / MRR 0,6992; uni_bi hit@8 0,9667 / MRR 0,6856 => `uni_bi`. Chênh một câu, nằm trong nhiễu của n=30; hàng `hybrid_rerank` dùng `uni` (đặt trước, không chỉnh theo kết quả).

## Xếp hạng lại: mô hình đã chọn
- `BAAI/bge-reranker-v2-m3` (cross-encoder, XLM-RoBERTa, đa ngôn ngữ), https://huggingface.co/BAAI/bge-reranker-v2-m3 (tra cứu 2026-10-28 qua API HF: `license: apache-2.0`, `language: multilingual`, `library_name: sentence-transformers`, `model.safetensors` = 2 271 071 852 byte, không gated). Nạp bằng `sentence_transformers.CrossEncoder` (đã cài, v2.6.1), fp16 trên GPU, nạp lười, `max_length=512`, ứng viên = top-30 sau RRF.
- Lý do chọn (định tính, không thử mô hình khác): cùng họ bge-m3, giấy phép Apache-2.0, đa ngôn ngữ. Chưa đọc mục đánh giá tiếng Việt trong model card; không có số riêng cho tiếng Việt từ tôi. Đã cân nhắc `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (nhỏ hơn, Apache-2.0, tag có `vi`) nhưng KHÔNG đo.
- Chi phí đo được: tải 2,27 GB; lượt truy vấn đầu (gồm nạp mô hình) 6-11 s; nóng p95 ~0,48-0,49 s/truy vấn (30 cặp); RSS đỉnh 4,4-4,6 GB; GPU dùng cuối 4,2-4,4 GB (đo toàn máy, gồm tiến trình khác ~1,4 GB và sbert).

## Cách đọc cột (iii)
Quy tắc (iii) nói p95 `/chat` <= 1,5x baseline. Tôi KHÔNG đo `/chat` đầu-cuối (sinh câu trả lời bằng llama3.2 chiếm phần lớn). Cột "(iii-proxy)" là tỷ lệ p95 CHỈ giai đoạn truy hồi (gồm nhúng truy vấn) so baseline: thước đo khắt khe hơn nhiều so với (iii) thật vì mẫu số bé (~17-26 ms). Tham chiếu: `eval/p0/latency_v2.json` (chạy khác, mẫu khác) cho `/chat` p95 ~10,0 s, trung vị ~3,4 s; cộng thêm ~0,3-0,5 s truy hồi sẽ là ~+3-5% ở p95, nhưng đó là ước lượng thô, KHÔNG phải số đo, và chưa tính tranh chấp GPU/RAM khi llama3.2 đang nạp cùng. Vì vậy cột "chấp nhận" ở hàng rerank/bge-m3 là "KHÔNG" chỉ theo proxy; theo ước lượng /chat có thể đạt (i) và (ii) đã ĐẠT. Cần đo `/chat` đầu-cuối (Leader) trước khi kết luận (iii).

## Bảng (b = baseline đúng, biến thể sai; c = baseline sai, biến thể đúng; p = McNemar chính xác hai phía; baseline = vector_sbert cùng tập)

## Tập g30 (eval/golden.jsonl, n=30, đã duyệt=0)

| biến thể | hit@4 | hit@6 | hit@8 | MRR | cover@4 | cover@8 | b/c hit@4 | p@4 | b/c hit@8 | p@8 | (i) | (ii) | (iii-proxy) p95 giai đoạn truy hồi | chấp nhận |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vector_sbert | 0.4667 | 0.5333 | 0.7667 | 0.4393 | 0.3667 | 0.5333 | 0/0 | 1.000 | 0/0 | 1.000 | - | - | 25.7 ms (x1.00) ĐẠT | - |
| hybrid_uni | 0.8333 | 0.9 | 0.9333 | 0.6992 | 0.6 | 0.8 | 0/11 | 0.001 | 0/5 | 0.062 | ĐẠT | ĐẠT | 26.6 ms (x1.04) ĐẠT | ĐẠT |
| hybrid_uni_bi | 0.8333 | 0.9 | 0.9667 | 0.6856 | 0.6 | 0.8333 | 0/11 | 0.001 | 0/6 | 0.031 | ĐẠT | ĐẠT | 25.2 ms (x0.98) ĐẠT | ĐẠT |
| hybrid_rerank | 1.0 | 1.0 | 1.0 | 0.9833 | 0.9333 | 1.0 | 0/16 | 0.000 | 0/7 | 0.016 | ĐẠT | ĐẠT | 493.2 ms (x19.19) KHÔNG | KHÔNG |
| vector_bge-m3 | 1.0 | 1.0 | 1.0 | 0.9056 | 0.9 | 0.9 | 0/16 | 0.000 | 0/7 | 0.016 | ĐẠT | ĐẠT | 322.3 ms (x12.54) KHÔNG | KHÔNG |
| hybrid_bge-m3 | 1.0 | 1.0 | 1.0 | 0.9333 | 0.9 | 0.9667 | 0/16 | 0.000 | 0/7 | 0.016 | ĐẠT | ĐẠT | 381.1 ms (x14.83) KHÔNG | KHÔNG |

Theo `type` (hit@4 / hit@8 đúng trên n):

| biến thể | fact | multi-hop | number |
|---|---|---|---|
| vector_sbert | 5/10 , 6/10 | 4/10 , 8/10 | 5/10 , 9/10 |
| hybrid_uni | 8/10 , 9/10 | 8/10 , 10/10 | 9/10 , 9/10 |
| hybrid_uni_bi | 8/10 , 9/10 | 8/10 , 10/10 | 9/10 , 10/10 |
| hybrid_rerank | 10/10 , 10/10 | 10/10 , 10/10 | 10/10 , 10/10 |
| vector_bge-m3 | 10/10 , 10/10 | 10/10 , 10/10 | 10/10 , 10/10 |
| hybrid_bge-m3 | 10/10 , 10/10 | 10/10 , 10/10 | 10/10 , 10/10 |

Hiệu năng (một máy; nóng = lượt 2, p50/p95 giai đoạn truy hồi k=8 gồm nhúng truy vấn; lạnh = câu đầu):

| biến thể | chỉ mục (s) | dung lượng chỉ mục | lạnh (ms) | nóng p50/p95 (ms) | dựng BM25 (s) | RSS đỉnh (MB) | GPU used cuối (MiB, mọi tiến trình) |
|---|---|---|---|---|---|---|---|
| vector_sbert | 7.7 | 6.4 MB | 18.3 | 16.2/25.7 | - | 1526 | 2495 |
| hybrid_uni | 8.3 | 6.4 MB | 18.3 | 17.9/26.6 | 0.019 | 1527 | 2495 |
| hybrid_uni_bi | 8.6 | 6.4 MB | 23.3 | 18.3/25.2 | 0.046 | 1527 | 2495 |
| hybrid_rerank | 8.3 | 6.4 MB | 11015.0 | 417.6/493.2 | 0.022 | 4402 | 4219 |
| vector_bge-m3 | 31.3 | 7.7 MB | 215.8 | 254.3/322.3 | - | 882 | 2167 |
| hybrid_bge-m3 | 16.9 | 7.7 MB | 252.9 | 292.7/381.1 | 0.034 | 903 | 2167 |

## Tập cand (eval/golden_candidates.jsonl, n=42, đã duyệt=0)

| biến thể | hit@4 | hit@6 | hit@8 | MRR | cover@4 | cover@8 | b/c hit@4 | p@4 | b/c hit@8 | p@8 | (i) | (ii) | (iii-proxy) p95 giai đoạn truy hồi | chấp nhận |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vector_sbert | 0.4762 | 0.5 | 0.5238 | 0.3197 | 0.3571 | 0.4286 | 0/0 | 1.000 | 0/0 | 1.000 | - | - | 16.8 ms (x1.00) ĐẠT | - |
| hybrid_uni | 0.7143 | 0.7381 | 0.9048 | 0.5935 | 0.5714 | 0.7619 | 0/10 | 0.002 | 0/16 | 0.000 | ĐẠT | ĐẠT | 32.7 ms (x1.95) KHÔNG | KHÔNG |
| hybrid_uni_bi | 0.6905 | 0.7857 | 0.881 | 0.5984 | 0.5952 | 0.7619 | 1/10 | 0.012 | 0/15 | 0.000 | ĐẠT | ĐẠT | 29.3 ms (x1.74) KHÔNG | KHÔNG |
| hybrid_rerank | 0.9762 | 1.0 | 1.0 | 0.9056 | 0.9286 | 0.9286 | 1/22 | 0.000 | 0/20 | 0.000 | ĐẠT | ĐẠT | 480.1 ms (x28.58) KHÔNG | KHÔNG |
| vector_bge-m3 | 0.9286 | 0.9524 | 0.9524 | 0.8571 | 0.9048 | 0.9524 | 1/20 | 0.000 | 0/18 | 0.000 | ĐẠT | ĐẠT | 310.7 ms (x18.49) KHÔNG | KHÔNG |
| hybrid_bge-m3 | 0.9524 | 0.9762 | 0.9762 | 0.869 | 0.9286 | 0.9762 | 0/20 | 0.000 | 0/19 | 0.000 | ĐẠT | ĐẠT | 351.2 ms (x20.90) KHÔNG | KHÔNG |

Theo `type` (hit@4 / hit@8 đúng trên n):

| biến thể | fact | multi-hop | number |
|---|---|---|---|
| vector_sbert | 8/16 , 10/16 | 6/9 , 6/9 | 6/17 , 6/17 |
| hybrid_uni | 13/16 , 15/16 | 7/9 , 9/9 | 10/17 , 14/17 |
| hybrid_uni_bi | 13/16 , 15/16 | 6/9 , 8/9 | 10/17 , 14/17 |
| hybrid_rerank | 16/16 , 16/16 | 8/9 , 9/9 | 17/17 , 17/17 |
| vector_bge-m3 | 15/16 , 15/16 | 8/9 , 9/9 | 16/17 , 16/17 |
| hybrid_bge-m3 | 15/16 , 16/16 | 9/9 , 9/9 | 16/17 , 16/17 |

Theo `kind` (hit@4 , hit@8):

| biến thể | formula | prose | table |
|---|---|---|---|
| vector_sbert | 7/16 , 7/16 | 7/11 , 7/11 | 6/15 , 8/15 |
| hybrid_uni | 10/16 , 14/16 | 8/11 , 10/11 | 12/15 , 14/15 |
| hybrid_uni_bi | 9/16 , 14/16 | 8/11 , 9/11 | 12/15 , 14/15 |
| hybrid_rerank | 15/16 , 16/16 | 11/11 , 11/11 | 15/15 , 15/15 |
| vector_bge-m3 | 14/16 , 15/16 | 11/11 , 11/11 | 14/15 , 14/15 |
| hybrid_bge-m3 | 15/16 , 15/16 | 11/11 , 11/11 | 14/15 , 15/15 |

Hiệu năng (một máy; nóng = lượt 2, p50/p95 giai đoạn truy hồi k=8 gồm nhúng truy vấn; lạnh = câu đầu):

| biến thể | chỉ mục (s) | dung lượng chỉ mục | lạnh (ms) | nóng p50/p95 (ms) | dựng BM25 (s) | RSS đỉnh (MB) | GPU used cuối (MiB, mọi tiến trình) |
|---|---|---|---|---|---|---|---|
| vector_sbert | 15.7 | 9.4 MB | 14.8 | 11.3/16.8 | - | 1524 | 3277 |
| hybrid_uni | 16.6 | 9.4 MB | 26.9 | 20.1/32.7 | 0.041 | 1526 | 3277 |
| hybrid_uni_bi | 18.0 | 9.4 MB | 28.3 | 23.1/29.3 | 0.072 | 1527 | 3277 |
| hybrid_rerank | 14.8 | 9.4 MB | 6001.9 | 385.6/480.1 | 0.053 | 4618 | 4427 |
| vector_bge-m3 | 108.6 | 10.8 MB | 249.4 | 251.0/310.7 | - | 916 | 2167 |
| hybrid_bge-m3 | 31.3 | 10.8 MB | 200.8 | 286.5/351.2 | 0.064 | 917 | 2167 |

## Điều kiện (i)-(iv) của mục 13, áp công thức (thăm dò)
- (i) c-b >= 0 ở hit@4 và hit@8, và >= +3 ở ít nhất một: ĐẠT ở cả 5 biến thể trên cả hai tập (b gần như luôn 0; ngoại lệ: hybrid_uni_bi b=1 ở hit@4 trên cand, hybrid_rerank b=1 hit@4 trên cand, vector_bge-m3 b=1 hit@4 trên cand).
- (ii) MRR >= MRR baseline - 0,02: ĐẠT ở cả 5 trên cả hai tập (MRR tăng).
- (iii): xem mục "Cách đọc cột (iii)": proxy KHÔNG đạt với rerank và bge-m3 (x12-x29), ĐẠT với hybrid (BM25 sbert) trên g30 (x1,04, x0,98) và KHÔNG ở cand (x1,95, x1,74, trên mẫu 17-33 ms, dao động nhiễu hệ thống; p95 trên 42 truy vấn). Bộ nhớ: rerank thêm ~3 GB RSS và ~1,7 GB GPU; bge-m3 qua Ollama dùng bộ nhớ của tiến trình Ollama (không nằm trong RSS của tiến trình đo; `ollama ps` không được ghi lại).
- (iv): p-value ghi ở bảng; không dùng làm cổng.
- Hạn chế: tập chưa duyệt; golden cũ được tạo/chọn khi baseline là sbert (có thể thiên lệch khó đoán); n nhỏ => p-value rời rạc (c=16 -> p<0,0001); không hiệu chỉnh đa so sánh.

## Bàn luận (không vượt dữ liệu)
- Trên cả hai tập, mọi biến thể đều tăng hit@4/hit@8 so baseline sbert; `bge-m3` thuần vector (E4) và `hybrid_rerank` (E3) đạt hit@4 = 1,0 trên g30 và 0,93-0,98 trên cand. Hai ứng viên không phân biệt được ở n này.
- Chi phí khác nhau: BM25 lai gần như miễn phí (dựng 0,02-0,07 s trong RAM, +vài ms/truy vấn) nhưng chỉ lên 0,83 hit@4 ở g30; bge-m3 làm truy hồi ~10-15x chậm hơn (qua HTTP Ollama, ~250-300 ms/truy vấn nóng), nạp chỉ mục chậm hơn (g30: 31 s so 7,7 s, đo một lần; cand vector_bge-m3 108 s so hybrid_bge-m3 31 s cùng mô hình cùng 3 PDF mới chắc chắn do nhiễu/tranh chấp Ollama, nên số thời gian nạp bge-m3 KHÔNG đáng tin ngoài bậc độ lớn), dung lượng chỉ mục +19-15% (7,7 so 6,4 MB; 10,8 so 9,4 MB).
- Nhóm D của E0 (q13, q25: trang đúng không có trong top-30 vector): hybrid_uni vẫn trượt@8 đúng hai câu này (BM25 `uni` không cứu); hybrid_uni_bi cứu q25 nhưng không cứu q13; rerank, vector_bge-m3 và hybrid_bge-m3 đạt hit@8 = 1,0 trên g30 nên cứu cả hai. Chênh lệch uni và uni_bi là một câu.
- Chưa làm/chưa đo: `/chat` đầu-cuối; tranh chấp GPU khi llama3.2 nạp cùng bge-reranker (6 GB, nguy cơ tràn); `ollama ps` cho bộ nhớ bge-m3; lặp nhiều lần để lấy phương sai; chưa kiểm Ollama chạy bge-m3 trên GPU hay CPU.
