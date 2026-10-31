"""Thống kê token của đoạn theo cách chia char/token cho 3 PDF golden.

Chạy: EVAL_PDF_DIR=<thư mục> python -m eval.chunk_stats
Ghi eval/p07/chunk_stats.json. Đếm token kèm token đặc biệt (như lúc embedding), giới hạn 256.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIMIT = 256


def main() -> int:
    os.environ.setdefault("CHROMA_PATH", str(ROOT / "eval" / "_work" / "p07" / "chroma_db"))
    os.environ.setdefault("GRAPH_PATH", str(ROOT / "eval" / "_work" / "p07" / "knowledge_graph.graphml"))
    sys.path[:0] = [str(ROOT), str(ROOT / "src")]
    import backend
    from pypdf import PdfReader

    from eval.check_quotes import find_pdf, load_golden

    tok = backend._load_tokenizer()
    names = sorted({g["doc"] for g in load_golden()})
    pages = {n: [p.extract_text() or "" for p in PdfReader(find_pdf(n)).pages] for n in names}
    out: dict = {"limit": LIMIT, "stats": {}}
    print(f"{'chunking':<6} {'doc':<28} {'chunks':>6} {'>256':>5} {'%':>6} {'max':>4} {'mean':>6}")
    for mode in ("char", "token"):
        for n in names:
            chunks, _ = backend._chunk_pages(pages[n], mode)
            lens = [len(tok.encode(c, add_special_tokens=True)) for c in chunks]
            over = sum(x > LIMIT for x in lens)
            r = {"chunks": len(chunks), "over_256": over, "pct_over": round(100 * over / len(lens), 1),
                 "max": max(lens), "mean": round(sum(lens) / len(lens), 1)}
            out["stats"][f"{mode}/{n}"] = r
            print(f"{mode:<6} {n:<28} {r['chunks']:>6} {over:>5} {r['pct_over']:>6} {r['max']:>4} {r['mean']:>6}")
    dst = ROOT / "eval" / "p07" / "chunk_stats.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
