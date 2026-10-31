"""P1.8 E3+E4: chạy ma trận biến thể trên golden (30) và golden_candidates (42), rồi dựng summary.md.

Chạy:  EVAL_PDF_DIR=<thư mục> .venv/bin/python -m eval.p18_e34 run      # chạy các biến thể còn thiếu
       .venv/bin/python -m eval.p18_e34 summary [uni|uni_bi]            # dựng eval/p18/e34/summary.md
Mỗi biến thể = một tiến trình riêng (backend đọc cờ lúc import). Kết quả: eval/p18/e34/<tập>_<biến thể>.json
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from eval.compare import compare, load

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "eval" / "p18" / "e34"
SETS = {"g30": "eval/golden.jsonl", "cand": "eval/golden_candidates.jsonl"}
# tên -> (RETRIEVAL, EMBEDDING, BM25_TOKENS)
VARIANTS = {
    "vector_sbert": ("vector", "sbert", "uni"),
    "hybrid_uni": ("hybrid", "sbert", "uni"),
    "hybrid_uni_bi": ("hybrid", "sbert", "uni_bi"),
    "hybrid_rerank": ("hybrid_rerank", "sbert", "uni"),   # BM25 uni: đặt trước, không chỉnh theo kết quả
    "vector_bge-m3": ("vector", "bge-m3", "uni"),
    "hybrid_bge-m3": ("hybrid", "bge-m3", os.environ.get("BM25_BEST", "uni")),  # BM25_BEST = biến thể tốt hơn ở hàng hybrid sbert
}


def run(only: list[str] | None = None) -> None:
    for s, gp in SETS.items():
        for v, (r, e, t) in VARIANTS.items():
            out = OUT / f"{s}_{v}.json"
            if out.exists() or (only and v not in only):
                continue
            cmd = [sys.executable, "src/evaluate_rag.py", "--live", "--retrieval", r, "--embedding", e,
                   "--bm25-tokens", t, "--golden", gp, "--out", str(out)]
            print(" ".join(cmd), flush=True)
            subprocess.run(cmd, cwd=ROOT, check=True, stdout=subprocess.DEVNULL, env=os.environ)


def _tab(pq, key, g):
    return sum(q[key] for q in pq if g(q)), sum(1 for q in pq if g(q))


def summary(best_bm25: str = "uni") -> str:
    L = []
    base_name = {}
    for s in SETS:
        base = json.load(open(OUT / f"{s}_vector_sbert.json"))
        bq = load(str(OUT / f"{s}_vector_sbert.json"))
        kinds = {}
        if s == "cand":
            kinds = {json.loads(l)["id"]: json.loads(l)["kind"]
                     for l in (ROOT / SETS[s]).read_text(encoding="utf-8").splitlines() if l.strip()}
        L += [f"\n## Tập {s} ({SETS[s]}, n={base['meta']['n']}, đã duyệt={base['meta']['reviewed']})\n",
              "| biến thể | hit@4 | hit@6 | hit@8 | MRR | cover@4 | cover@8 | b/c hit@4 | p@4 | b/c hit@8 | p@8 | "
              "(i) | (ii) | (iii-proxy) p95 giai đoạn truy hồi | chấp nhận |", "|" + "---|" * 15]
        for v in VARIANTS:
            f = OUT / f"{s}_{v}.json"
            if not f.exists():
                L.append(f"| {v} | chưa chạy |" + " |" * 13)
                continue
            d = json.load(open(f)); m = d["metrics"]["all"]; p = d["perf"]; bm = base["metrics"]["all"]
            rows = {r[0]: r for r in compare(bq, load(str(f)), ["hit@4", "hit@8"])}
            (_, b4, c4, p4), (_, b8, c8, p8) = rows["hit@4"], rows["hit@8"]
            i_ok = (c4 - b4 >= 0 and c8 - b8 >= 0 and max(c4 - b4, c8 - b8) >= 3) if v != "vector_sbert" else None
            ii_ok = m["mrr"] >= bm["mrr"] - 0.02 if v != "vector_sbert" else None
            ratio = p["hot_p95_ms"] / base["perf"]["hot_p95_ms"]
            iii = ratio <= 1.5
            acc = None if v == "vector_sbert" else (i_ok and ii_ok and iii)
            fm = lambda x: "-" if x is None else ("ĐẠT" if x else "KHÔNG")
            L.append(f"| {v} | {m['hit@4']} | {m['hit@6']} | {m['hit@8']} | {m['mrr']} | {m['cover@4']} | {m['cover@8']} | "
                     f"{b4}/{c4} | {p4:.3f} | {b8}/{c8} | {p8:.3f} | {fm(i_ok)} | {fm(ii_ok)} | "
                     f"{p['hot_p95_ms']} ms (x{ratio:.2f}) {fm(iii)} | {fm(acc)} |")
        L += ["\nTheo `type` (hit@4 / hit@8 đúng trên n):\n", "| biến thể | " +
              " | ".join(sorted(base["metrics"] .keys() - {"all"})) + " |", "|" + "---|" * (1 + len(base["metrics"]) - 1)]
        types = sorted(base["metrics"].keys() - {"all"})
        for v in VARIANTS:
            f = OUT / f"{s}_{v}.json"
            if f.exists():
                pq = json.load(open(f))["per_question"]
                L.append(f"| {v} | " + " | ".join(
                    "{}/{} , {}/{}".format(*_tab(pq, "hit@4", lambda q, t=t: q["type"] == t),
                                           *_tab(pq, "hit@8", lambda q, t=t: q["type"] == t)) for t in types) + " |")
        if kinds:
            ks = sorted(set(kinds.values()))
            L += ["\nTheo `kind` (hit@4 , hit@8):\n", "| biến thể | " + " | ".join(ks) + " |", "|" + "---|" * (1 + len(ks))]
            for v in VARIANTS:
                f = OUT / f"{s}_{v}.json"
                if f.exists():
                    pq = json.load(open(f))["per_question"]
                    L.append(f"| {v} | " + " | ".join(
                        "{}/{} , {}/{}".format(*_tab(pq, "hit@4", lambda q, k=k: kinds[q["id"]] == k),
                                               *_tab(pq, "hit@8", lambda q, k=k: kinds[q["id"]] == k)) for k in ks) + " |")
        L += ["\nHiệu năng (một máy; nóng = lượt 2, p50/p95 giai đoạn truy hồi k=8 gồm nhúng truy vấn; lạnh = câu đầu):\n",
              "| biến thể | chỉ mục (s) | dung lượng chỉ mục | lạnh (ms) | nóng p50/p95 (ms) | dựng BM25 (s) | RSS đỉnh (MB) | GPU used cuối (MiB, mọi tiến trình) |",
              "|" + "---|" * 8]
        for v in VARIANTS:
            f = OUT / f"{s}_{v}.json"
            if f.exists():
                p = json.load(open(f))["perf"]
                L.append(f"| {v} | {p['index_s']} | {p['index_bytes']/1e6:.1f} MB | {p['cold_first_query_ms']} | "
                         f"{p['hot_p50_ms']}/{p['hot_p95_ms']} | {p.get('bm25_build_s', '-')} | {p['rss_peak_mb']} | "
                         f"{p['gpu_used_mib_at_end_all_processes']} |")
    return "\n".join(L)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    if sys.argv[1] == "run":
        run(sys.argv[2:] or None)
    else:
        print(summary())
