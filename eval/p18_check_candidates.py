"""Kiểm tra gold_quote của tệp ứng viên bộ vàng (dùng lại eval.check_quotes.check) + thống kê + review sheet.

Chạy: EVAL_PDF_DIR=<thư mục> python -m eval.p18_check_candidates [eval/golden_candidates.jsonl] [--review-sheet]
Thoát 1 nếu có trích dẫn lệch. Thống kê in từ chính tệp.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

from eval.check_quotes import check

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = ROOT / "eval" / "golden_candidates.jsonl"
SHEET = ROOT / "eval" / "p18" / "review_sheet.md"
# Ký hiệu toán mà pypdf thường làm vỡ dòng/ghép chữ: câu có trong gold_quote được đếm là "rủi ro méo" (heuristic).
MATH_RISK = re.compile(r"[⊤∑√∥ˆ∂⋆∆]")
HEADER = """# Phiếu duyệt ứng viên bộ vàng (P1.8)

Cách duyệt:
1. Mở PDF ở trang ghi trong khối, đối chiếu "Trích dẫn" với văn bản trên trang (trích dẫn lấy bằng pypdf nên có thể dính chữ/méo ký hiệu; chỉ cần đúng nghĩa).
2. Câu hỏi phải tiếng Việt tự nhiên, không chứa sẵn đáp án, và trả lời được từ trích dẫn mà không cần kiến thức ngoài tài liệu.
3. Đáp án phải đúng so với PDF: đánh dấu [x] Đúng, hoặc [x] Sai (sửa đáp án ở dòng ghi chú).
4. Câu mơ hồ, trùng ý câu khác, hoặc quote lệch trang: đánh dấu [x] Loại.
5. Chỉ chủ dự án đổi `reviewed` thành true; mọi câu hiện là reviewed:false, proposed_by:model.
"""


def load(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def stats(rows):
    out = [f"tổng: {len(rows)} câu"]
    for k in ("type", "kind", "doc"):
        out.append(f"{k}: " + ", ".join(f"{a}={b}" for a, b in sorted(Counter(r[k] for r in rows).items())))
    risky = [r["id"] for r in rows if r["kind"] in ("table", "formula") and MATH_RISK.search(r["gold_quote"])]
    tf = sum(r["kind"] in ("table", "formula") for r in rows)
    out.append(f"table+formula: {tf}; trong đó quote có dấu hiệu méo (heuristic): {len(risky)} ({', '.join(risky)})")
    return "\n".join(out)


def sheet(rows):
    L = [HEADER]
    for doc in sorted({r["doc"] for r in rows}):
        L.append(f"\n## {doc}\n")
        for r in sorted((x for x in rows if x["doc"] == doc), key=lambda x: (x["type"], x["id"])):
            L += [f"### {r['id']} — trang {', '.join(map(str, r['gold_pages']))} — {r['type']} / {r['kind']}", "",
                  f"- Câu hỏi: {r['question']}", f"- Đáp án: {r['answer']}", f"- Trích dẫn: {r['gold_quote']}",
                  "- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại", "- Ghi chú: ", ""]
    return "\n".join(L)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    rows = load(args[0] if args else DEFAULT)
    bad = check(rows)
    print(f"{len(rows) - len(bad)}/{len(rows)} gold_quote khớp; lệch: {', '.join(bad) or 0}")
    print(stats(rows))
    if "--review-sheet" in sys.argv:
        SHEET.parent.mkdir(parents=True, exist_ok=True)
        SHEET.write_text(sheet(rows), encoding="utf-8")
        print(f"đã ghi {SHEET}")
    sys.exit(1 if bad else 0)
