# P1.8 E0 — phân loại câu trượt (quy tắc cố định; mẫu nhỏ, một máy)

Lệnh: `EVAL_PDF_DIR=/home/lucius/Project/Learning-AI-engineer .venv/bin/python -m eval.p18_failure_analysis`

## Đối chiếu với eval/report.json

- Tệp này: hit@4 = 14/30, hit@8 = 23/30. report.json: hit@4 = 14/30, hit@8 = 23/30.
- Khớp từng câu (cả hit@4 và hit@8): TẤT CẢ KHỚP.

- Trượt@8 (7): q01, q10, q11, q13, q22, q25, q29
- Chỉ trúng@8, trượt@4 (9): q04, q07, q09, q15, q18, q20, q24, q26, q27

## Số câu mỗi cờ (một câu có thể mang nhiều cờ)

| Nhóm | n | A | B | C4 | C8 | D | E |
|---|---|---|---|---|---|---|---|
| tất cả | 30 | 0 | 2 | 14 | 5 | 2 | 19 |
| trượt@8 | 7 | 0 | 1 | 5 | 5 | 2 | 5 |
| chỉ trúng@8 | 9 | 0 | 0 | 9 | 0 | 0 | 8 |
| trúng@4 | 14 | 0 | 1 | 0 | 0 | 0 | 6 |

Theo loại câu:

| Loại | n | A | B | C4 | C8 | D | E |
|---|---|---|---|---|---|---|---|
| fact | 10 | 0 | 2 | 4 | 3 | 1 | 6 |
| number | 10 | 0 | 0 | 4 | 0 | 1 | 4 |
| multi-hop | 10 | 0 | 0 | 6 | 2 | 0 | 9 |

Theo tài liệu:

| Tài liệu | n | A | B | C4 | C8 | D | E |
|---|---|---|---|---|---|---|---|
| bao-cao-bien-doi-gradient.pdf | 10 | 0 | 2 | 5 | 2 | 0 | 5 |
| kmeans-vs-knn.pdf | 10 | 0 | 0 | 5 | 2 | 1 | 8 |
| probability-vs-statistics.pdf | 10 | 0 | 0 | 4 | 1 | 1 | 6 |

## Từng câu

| id | loại | hạng đoạn đúng | cos top1 | cos đúng | cờ | hit@4 | hit@8 |
|---|---|---|---|---|---|---|---|
| q01 | fact | 9 | 0.5655 | 0.4904 | B,C4,C8 | 0 | 0 |
| q02 | fact | 1 | 0.4869 | 0.4869 | E | 1 | 1 |
| q03 | fact | 1 | 0.6449 | 0.6449 | B | 1 | 1 |
| q04 | number | 8 | 0.6632 | 0.6047 | C4 | 0 | 1 |
| q05 | number | 3 | 0.5524 | 0.5429 | - | 1 | 1 |
| q06 | number | 1 | 0.6426 | 0.6426 | - | 1 | 1 |
| q07 | multi-hop | 7 | 0.6619 | 0.6275 | C4,E | 0 | 1 |
| q08 | multi-hop | 4 | 0.6471 | 0.6126 | E | 1 | 1 |
| q09 | multi-hop | 8 | 0.6508 | 0.6192 | C4,E | 0 | 1 |
| q10 | multi-hop | 9 | 0.562 | 0.4898 | C4,C8,E | 0 | 0 |
| q11 | fact | 23 | 0.6195 | 0.5228 | C4,C8,E | 0 | 0 |
| q12 | fact | 1 | 0.4989 | 0.4989 | - | 1 | 1 |
| q13 | fact | không có | 0.4924 | - | D,E | 0 | 0 |
| q14 | number | 1 | 0.6684 | 0.6684 | - | 1 | 1 |
| q15 | number | 7 | 0.5074 | 0.47 | C4,E | 0 | 1 |
| q16 | number | 4 | 0.4494 | 0.3952 | - | 1 | 1 |
| q17 | number | 1 | 0.5873 | 0.5873 | E | 1 | 1 |
| q18 | multi-hop | 7 | 0.6637 | 0.593 | C4,E | 0 | 1 |
| q19 | multi-hop | 1 | 0.636 | 0.636 | - | 1 | 1 |
| q20 | multi-hop | 5 | 0.5935 | 0.5862 | C4,E | 0 | 1 |
| q21 | fact | 1 | 0.7139 | 0.7139 | - | 1 | 1 |
| q22 | fact | 14 | 0.588 | 0.5333 | C4,C8,E | 0 | 0 |
| q23 | fact | 1 | 0.5176 | 0.5176 | E | 1 | 1 |
| q24 | fact | 7 | 0.5387 | 0.402 | C4,E | 0 | 1 |
| q25 | number | không có | 0.6608 | - | D | 0 | 0 |
| q26 | number | 8 | 0.5699 | 0.5014 | C4,E | 0 | 1 |
| q27 | number | 5 | 0.5974 | 0.5749 | C4,E | 0 | 1 |
| q28 | multi-hop | 1 | 0.5323 | 0.5323 | E | 1 | 1 |
| q29 | multi-hop | 26 | 0.6148 | 0.5305 | C4,C8,E | 0 | 0 |
| q30 | multi-hop | 1 | 0.6247 | 0.6247 | E | 1 | 1 |

## Cờ E: regex (HEURISTIC) và mức tin cậy

Regex (đầy đủ trong `E_PATTERNS` của script và `failure_analysis.json`; tỉ lệ đoạn khớp trên toàn bộ đoạn):

- `lower_upper_glue`: chữ Latin thường liền chữ Latin hoa; 30.1% số đoạn
- `paren_close_glue`: ')' liền chữ Latin; 19.1% số đoạn
- `diacritic_paren_open`: chữ thường có dấu liền '('; 1.3% số đoạn
- `digit_diacritic_glue`: chữ số liền chữ thường có dấu; 6.3% số đoạn
- `split_symbol_lines`: >= 4 dòng liên tiếp mỗi dòng <= 2 ký tự; 0.2% số đoạn

- Số đoạn > 256 token (kèm token đặc biệt) trên toàn bộ 398 đoạn: 73. (Liên quan cờ A.)
- Tỉ lệ ĐOẠN có khớp ít nhất một regex trên toàn bộ 398 đoạn của 3 PDF (nền): 37.9%.
- Cờ E ở câu trượt@8: 5/7; ở câu trúng@4: 6/14; tất cả: 19/30.
- Tỉ lệ ký tự khớp (trung bình các câu): 0.6709%.

## Nhận xét (sinh theo số; đọc cùng bảng)

- Trong 7 câu trượt@8: A=0, B=1, C4=5, C8=5, D=2, E=5.
- Trong toàn bộ 30 câu: A=0, B=2, C4=14, C8=5, D=2, E=19.
- C (đoạn đúng có trong top-30 nhưng hạng thấp) và D (không có) chỉ MÔ TẢ vị trí xếp hạng, không giải thích vì sao: chúng cùng tồn tại với mọi nguyên nhân thật (ngữ nghĩa, kích thước đoạn, nhúng yếu, dữ liệu vỡ).
- A và B là kiểm tra cơ học trên chữ pypdf và độ dài đoạn nên khá chắc về PHÁT HIỆN; còn việc chúng gây trượt hay không thì chỉ là tương quan (cùng câu có thể còn nguyên nhân khác). Đoạn trích có thể nằm ở đoạn khác không bị cắt (A chỉ bật khi mọi đoạn chứa đều cắt).
- E chỉ là heuristic: so với nền ở trên; nếu tỉ lệ ở câu trượt không cao hơn rõ rệt so với nền hoặc câu trúng thì KHÔNG được kết luận 'do pypdf'. Muốn kết luận phải đo E1 (Docling so pypdf) theo hit@k.
- Mọi con số: mẫu nhỏ (30 câu, 3 PDF), một máy; không suy rộng.
