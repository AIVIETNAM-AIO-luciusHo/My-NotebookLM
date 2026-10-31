"""P1.8 E0: phân loại câu trượt của eval/golden.jsonl bằng QUY TẮC CỐ ĐỊNH (không phân loại tay).

Chạy: EVAL_PDF_DIR=<thư mục> .venv/bin/python -m eval.p18_failure_analysis
Dựng chỉ mục TẠM ở eval/_work/p18/ bằng đúng pipeline hiện tại (char 600/75, sbert, cosine,
HNSW 1 luồng như evaluate_rag --live), truy hồi top-30 mỗi câu. Không đụng chroma_db/ thật,
không ghi eval/report.json. Ghi eval/p18/failure_analysis.json và eval/p18/failure_summary.md.

Cờ (mỗi câu có thể mang nhiều cờ):
  A  trích dẫn vàng (một đoạn của nó) bị cắt sau 256 token của đoạn chứa nó: đếm token tiền tố
     (chuẩn hoá khoảng trắng) tới hết đoạn trích, kèm token đặc biệt, > 256. Chỉ xét khi MỌI đoạn
     chứa đoạn trích đều cắt nó (nếu có đoạn giữ trọn thì không phải A).
  B  không đoạn nào (cùng trang vàng) chứa trọn một đoạn trích (bị cắt ngang ranh giới đoạn).
  C4/C8  có đoạn đúng (đúng doc, trang vàng) trong top-30 nhưng hạng > 4 / > 8.
  D  không có đoạn đúng trong top-30.
  E  HEURISTIC dấu hiệu vỡ trích xuất ở đoạn chứa trích dẫn (xem E_PATTERNS). Không chứng minh
     nguyên nhân: regex có dương tính giả (tên riêng như PyTorch, công thức hợp lệ).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "eval" / "p18"
TOPN = 30
LIMIT = 256

# Lớp chữ Latin (gồm dấu tiếng Việt), dựng từ Unicode thay vì khoảng à-ỹ (khoảng đó lẫn Hy Lạp/Cyrillic).
_LAT = [chr(c) for c in list(range(0x41, 0x250)) + list(range(0x1E00, 0x1F00)) if chr(c).isalpha()]
LOW = "".join(c for c in _LAT if c.islower())
UP = "".join(c for c in _LAT if c.isupper())
DIAC = "".join(c for c in LOW if ord(c) > 0x7F)  # chữ thường có dấu: không xuất hiện trong tên hàm toán ASCII

E_PATTERNS = {
    "lower_upper_glue": rf"[{LOW}][{UP}]",           # chữ thường dính chữ hoa: "VậyJ", "gradientBiến"
    "paren_close_glue": rf"\)[{LOW}{UP}]",           # ")với": ngoặc đóng dính chữ
    "diacritic_paren_open": rf"[{DIAC}]\(",           # "với(": chữ có dấu dính ngoặc mở
    "digit_diacritic_glue": rf"\d[{DIAC}]",           # "107lần": số dính chữ có dấu
    "split_symbol_lines": r"(?:^|\n)[^\s]{1,2}(?:\n[^\s]{1,2}){3,}",  # >= 4 dòng liên tiếp <= 2 ký tự (công thức vỡ dòng)
}
E_DESC = {  # mô tả đọc được (regex đầy đủ ở E_PATTERNS và trong failure_analysis.json)
    "lower_upper_glue": "chữ Latin thường liền chữ Latin hoa",
    "paren_close_glue": "')' liền chữ Latin",
    "diacritic_paren_open": "chữ thường có dấu liền '('",
    "digit_diacritic_glue": "chữ số liền chữ thường có dấu",
    "split_symbol_lines": ">= 4 dòng liên tiếp mỗi dòng <= 2 ký tự",
}
_E_RE = {k: re.compile(v) for k, v in E_PATTERNS.items()}
SEP = " [...] "


def norm(s: str) -> str:
    return " ".join(s.split())


def e_scan(text: str) -> dict:
    counts, covered = {}, 0
    for k, rx in _E_RE.items():
        ms = list(rx.finditer(text))
        counts[k] = len(ms)
        covered += sum(m.end() - m.start() for m in ms)
    return {"counts": counts, "matched_chars": covered, "chars": len(text),
            "char_ratio": round(covered / max(1, len(text)), 5), "flag": sum(counts.values()) > 0}


def main() -> int:
    work = ROOT / "eval" / "_work" / "p18"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    os.environ["CHROMA_PATH"] = str(work / "chroma_db")  # TRƯỚC khi import backend
    os.environ["GRAPH_PATH"] = str(work / "knowledge_graph.graphml")
    sys.path[:0] = [str(ROOT), str(ROOT / "src")]
    import backend
    from pypdf import PdfReader

    from eval.check_quotes import find_pdf, load_golden

    assert Path(backend.CHROMA_PATH).resolve() == (work / "chroma_db").resolve()
    golden = load_golden()
    tok = backend._load_tokenizer()
    ntok = lambda s: len(tok.encode(s, add_special_tokens=True))  # noqa: E731

    client = backend.chromadb.PersistentClient(path=str(backend.CHROMA_PATH))
    client.get_or_create_collection(backend.COLLECTION_NAME, metadata={
        "hnsw:space": "cosine", "hnsw:num_threads": 1,
        "hnsw:construction_ef": 1000, "hnsw:search_ef": 1000})
    del client
    col = backend._get_collection()
    chunks_of: dict[str, list[tuple[int, str]]] = {}  # doc -> [(page, chunk)] theo thứ tự id
    for name in sorted({g["doc"] for g in golden}):
        pages = [p.extract_text() or "" for p in PdfReader(find_pdf(name)).pages]
        chunks, cpages = backend._chunk_pages(pages, "char")
        chunks_of[name] = list(zip(cpages, chunks))
        col.add(ids=[f"{name}:{i}" for i in range(len(chunks))], documents=chunks,
                embeddings=backend._embeddings.embed_documents(chunks),
                metadatas=[{"source": name, "page": p} for p in cpages])

    # Nền so sánh cho cờ E: tỉ lệ đoạn có khớp regex trên TOÀN BỘ đoạn của 3 PDF.
    all_chunks = [c for v in chunks_of.values() for _, c in v]
    base_e = sum(e_scan(c)["flag"] for c in all_chunks) / len(all_chunks)
    base_pat = {k: round(sum(bool(rx.search(c)) for c in all_chunks) / len(all_chunks), 4) for k, rx in _E_RE.items()}
    over256 = sum(ntok(c) > LIMIT for c in all_chunks)

    rep = {r["id"]: r for r in json.loads((ROOT / "eval" / "report.json").read_text(encoding="utf-8"))["per_question"]}
    rows = []
    for g in golden:
        doc, gp = g["doc"], g["gold_pages"]
        res = col.query(query_embeddings=[backend._embeddings.embed_query(g["question"])],
                        n_results=min(TOPN, col.count()), include=["distances", "metadatas"])
        ids, dist, metas = res["ids"][0], res["distances"][0], res["metadatas"][0]
        cos = [round(1 - d, 4) for d in dist]
        rank = next((i + 1 for i, m in enumerate(metas) if m["source"] == doc and m["page"] in gp), None)

        # --- vị trí trích dẫn trong các đoạn (cờ A, B, E) ---
        segs = g["gold_quote"].split(SEP)
        seg_info, a_hit, b_hit, e_texts = [], False, False, []
        qchunk_rank = None
        for seg in segs:
            ns = norm(seg)
            holders = []  # (chunk_idx, page, norm_chunk, pos)
            for ci, (pg, ch) in enumerate(chunks_of[doc]):
                if pg in gp:
                    nc = norm(ch)
                    pos = nc.find(ns)
                    if pos >= 0:
                        holders.append((ci, pg, nc, pos, ch))
            info = {"segment": seg, "holders": [h[0] for h in holders]}
            if not holders:
                b_hit = True
                info["status"] = "B_cut_across_boundary"
                e_texts.append(seg)
            else:
                cut = []
                for ci, pg, nc, pos, ch in holders:
                    end_tok = ntok(nc[: pos + len(ns)])
                    cut.append(end_tok > LIMIT)
                    info.setdefault("end_tokens", []).append(end_tok)
                    e_texts.append(ch)
                    if f"{doc}:{ci}" in ids:
                        r_ = ids.index(f"{doc}:{ci}") + 1
                        qchunk_rank = r_ if qchunk_rank is None else min(qchunk_rank, r_)
                if all(cut):
                    a_hit = True
                    info["status"] = "A_truncated_256"
                else:
                    info["status"] = "ok"
            seg_info.append(info)
        e = e_scan("\n".join(e_texts))
        gold_cos = cos[rank - 1] if rank else None
        r0 = rep[g["id"]]
        row = {
            "id": g["id"], "doc": doc, "type": g["type"], "gold_pages": gp,
            "gold_rank": rank, "cos_top1": cos[0], "cos_gold": gold_cos,
            "top1_page": [metas[0]["source"], metas[0]["page"]],
            "quote_chunk_rank_top30": qchunk_rank,
            "hit@4": bool(rank and rank <= 4), "hit@8": bool(rank and rank <= 8),
            "matches_report": (bool(rank and rank <= 4) == r0["hit@4"]) and (bool(rank and rank <= 8) == r0["hit@8"]),
            "flags": {"A": a_hit, "B": b_hit, "C4": bool(rank and rank > 4), "C8": bool(rank and rank > 8),
                      "D": rank is None, "E": e["flag"]},
            "E_detail": e, "segments": seg_info,
        }
        rows.append(row)

    OUT.mkdir(parents=True, exist_ok=True)
    out = {"meta": {"note": "mẫu nhỏ, một máy; cờ E là HEURISTIC", "topn": TOPN, "token_limit": LIMIT,
                    "E_patterns": E_PATTERNS, "E_baseline_chunk_rate_all_chunks": round(base_e, 4),
                    "n_chunks": len(all_chunks),
                    "E_baseline_by_pattern": base_pat, "chunks_over_256_tokens": over256}, "questions": rows}
    (OUT / "failure_analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "failure_summary.md").write_text(summary(rows, rep, base_e, len(all_chunks), base_pat, over256), encoding="utf-8")
    print((OUT / "failure_summary.md").read_text(encoding="utf-8"))
    return 0


def summary(rows: list[dict], rep: dict, base_e: float, n_chunks: int, base_pat: dict, over256: int) -> str:
    FL = ["A", "B", "C4", "C8", "D", "E"]
    n = len(rows)
    h4, h8 = sum(r["hit@4"] for r in rows), sum(r["hit@8"] for r in rows)
    rh4, rh8 = sum(v["hit@4"] for v in rep.values()), sum(v["hit@8"] for v in rep.values())
    mism = [r["id"] for r in rows if not r["matches_report"]]
    miss8 = [r["id"] for r in rows if not r["hit@8"]]
    only8 = [r["id"] for r in rows if r["hit@8"] and not r["hit@4"]]
    L = ["# P1.8 E0 — phân loại câu trượt (quy tắc cố định; mẫu nhỏ, một máy)", "",
         "Lệnh: `EVAL_PDF_DIR=/home/lucius/Project/Learning-AI-engineer .venv/bin/python -m eval.p18_failure_analysis`", "",
         "## Đối chiếu với eval/report.json", "",
         f"- Tệp này: hit@4 = {h4}/{n}, hit@8 = {h8}/{n}. report.json: hit@4 = {rh4}/{n}, hit@8 = {rh8}/{n}.",
         f"- Khớp từng câu (cả hit@4 và hit@8): {'TẤT CẢ KHỚP' if not mism else 'LỆCH ở ' + ', '.join(mism)}.", "",
         f"- Trượt@8 ({len(miss8)}): {', '.join(miss8)}", f"- Chỉ trúng@8, trượt@4 ({len(only8)}): {', '.join(only8)}", "",
         "## Số câu mỗi cờ (một câu có thể mang nhiều cờ)", "",
         "| Nhóm | n | " + " | ".join(FL) + " |", "|---|---|" + "---|" * len(FL)]

    def line(name, rs):
        return f"| {name} | {len(rs)} | " + " | ".join(str(sum(r['flags'][f] for r in rs)) for f in FL) + " |"

    L.append(line("tất cả", rows))
    L.append(line("trượt@8", [r for r in rows if not r["hit@8"]]))
    L.append(line("chỉ trúng@8", [r for r in rows if r["hit@8"] and not r["hit@4"]]))
    L.append(line("trúng@4", [r for r in rows if r["hit@4"]]))
    L += ["", "Theo loại câu:", "", "| Loại | n | " + " | ".join(FL) + " |", "|---|---|" + "---|" * len(FL)]
    for t in ("fact", "number", "multi-hop"):
        L.append(line(t, [r for r in rows if r["type"] == t]))
    L += ["", "Theo tài liệu:", "", "| Tài liệu | n | " + " | ".join(FL) + " |", "|---|---|" + "---|" * len(FL)]
    for d in sorted({r["doc"] for r in rows}):
        L.append(line(d, [r for r in rows if r["doc"] == d]))
    L += ["", "## Từng câu", "",
          "| id | loại | hạng đoạn đúng | cos top1 | cos đúng | cờ | hit@4 | hit@8 |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        fl = ",".join(f for f in FL if r["flags"][f]) or "-"
        L.append(f"| {r['id']} | {r['type']} | {r['gold_rank'] or 'không có'} | {r['cos_top1']} | "
                 f"{r['cos_gold'] if r['cos_gold'] is not None else '-'} | {fl} | {int(r['hit@4'])} | {int(r['hit@8'])} |")

    e_miss = [r for r in rows if not r["hit@8"]]
    e_hit = [r for r in rows if r["hit@4"]]
    eq = lambda rs: f"{sum(r['flags']['E'] for r in rs)}/{len(rs)}"  # noqa: E731
    L += ["", "## Cờ E: regex (HEURISTIC) và mức tin cậy", "",
          "Regex (đầy đủ trong `E_PATTERNS` của script và `failure_analysis.json`; tỉ lệ đoạn khớp trên toàn bộ đoạn):", "",
          *[f"- `{k}`: {E_DESC[k]}; {base_pat[k]:.1%} số đoạn" for k in E_PATTERNS], "",
          f"- Số đoạn > {LIMIT} token (kèm token đặc biệt) trên toàn bộ {n_chunks} đoạn: {over256}. (Liên quan cờ A.)",
          f"- Tỉ lệ ĐOẠN có khớp ít nhất một regex trên toàn bộ {n_chunks} đoạn của 3 PDF (nền): {base_e:.1%}.",
          f"- Cờ E ở câu trượt@8: {eq(e_miss)}; ở câu trúng@4: {eq(e_hit)}; tất cả: {eq(rows)}.",
          f"- Tỉ lệ ký tự khớp (trung bình các câu): {sum(r['E_detail']['char_ratio'] for r in rows) / n:.4%}.", ""]

    cnt = {f: sum(r["flags"][f] for r in rows) for f in FL}
    cm = {f: sum(r["flags"][f] for r in e_miss) for f in FL}
    L += ["## Nhận xét (sinh theo số; đọc cùng bảng)", "",
          f"- Trong {len(e_miss)} câu trượt@8: " + ", ".join(f"{f}={cm[f]}" for f in FL) + ".",
          f"- Trong toàn bộ {n} câu: " + ", ".join(f"{f}={cnt[f]}" for f in FL) + ".",
          "- C (đoạn đúng có trong top-30 nhưng hạng thấp) và D (không có) chỉ MÔ TẢ vị trí xếp hạng, không giải thích vì sao: "
          "chúng cùng tồn tại với mọi nguyên nhân thật (ngữ nghĩa, kích thước đoạn, nhúng yếu, dữ liệu vỡ).",
          "- A và B là kiểm tra cơ học trên chữ pypdf và độ dài đoạn nên khá chắc về PHÁT HIỆN; còn việc chúng gây trượt hay không "
          "thì chỉ là tương quan (cùng câu có thể còn nguyên nhân khác). Đoạn trích có thể nằm ở đoạn khác không bị cắt (A chỉ bật khi mọi đoạn chứa đều cắt).",
          "- E chỉ là heuristic: so với nền ở trên; nếu tỉ lệ ở câu trượt không cao hơn rõ rệt so với nền hoặc câu trúng thì KHÔNG được kết luận 'do pypdf'. "
          "Muốn kết luận phải đo E1 (Docling so pypdf) theo hit@k.",
          "- Mọi con số: mẫu nhỏ (30 câu, 3 PDF), một máy; không suy rộng.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())
