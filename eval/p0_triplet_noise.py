"""P0-3: độ nhiễu trích triplet (nhiệt độ mặc định của repo). Mẫu nhỏ, một máy.

Chạy: EVAL_PDF_DIR=<dir> python eval/p0_triplet_noise.py
"""
import argparse, itertools, json, os, statistics as st, sys
from pathlib import Path

ap = argparse.ArgumentParser(); ap.add_argument("--runs", type=int, default=0, help="R2-2: số lượt (ghi *_v2.json)"); ARGS = ap.parse_args()
ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "eval" / "_work" / "p0" / "noise"
os.environ["CHROMA_PATH"] = str(WORK / "chroma")
os.environ["GRAPH_PATH"] = str(WORK / "graph.graphml")
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
WORK.mkdir(parents=True, exist_ok=True)

import backend
from pypdf import PdfReader

N, RUNS = 40, ARGS.runs or 2
_temps = set(); _Real = backend.Ollama
def _Spy(*a, **k):
    _temps.add(k.get("temperature", "mặc định của lớp")); return _Real(*a, **k)
backend.Ollama = _Spy
pages = [p.extract_text() or "" for p in PdfReader(Path(os.environ["EVAL_PDF_DIR"]) / "bao-cao-bien-doi-gradient.pdf").pages]
chunks, _ = backend._chunk_pages(pages)
chunks = chunks[:N]
assert len(chunks) >= 40, len(chunks)

norm = lambda ts: {tuple(x.lower() for x in t) for t in ts}
runs = [[norm(backend._extract_triplets_from_chunk(c)) for c in chunks] for _ in range(RUNS)]
tot = [sum(len(s) for s in r) for r in runs]
def jac_of(r1, r2): return [1.0 if not (a | b) else len(a & b) / len(a | b) for a, b in zip(r1, r2)]
pairs = {f"{i+1}-{j+1}": jac_of(runs[i], runs[j]) for i, j in itertools.combinations(range(RUNS), 2)}
jac = pairs["1-2"]
differ = sum(len({frozenset(r[n]) for r in runs}) > 1 for n in range(len(chunks)))
out = {"label": "mẫu nhỏ, một máy, chưa có CI", "doc": "bao-cao-bien-doi-gradient.pdf", "n_chunks": len(chunks), "runs": RUNS,
       "temperature": sorted(_temps, key=str), "temperature_source": "bắt kwargs thật của backend.Ollama khi chạy",
       "note": "so khớp tập triplet chữ thường (khử trùng lặp trong đoạn)",
       "triplets_per_run": tot, "relative_diff": (max(tot) - min(tot)) / max(tot),
       "mean_jaccard_per_chunk": st.mean(jac), "chunks_differing": differ,
       "jaccard_pairs_mean": {k: st.mean(v) for k, v in pairs.items()},
       "jaccard_mean_all_pairs": st.mean(st.mean(v) for v in pairs.values())}
(ROOT / f"eval/p0/triplet_noise{'_v2' if ARGS.runs else ''}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=2))
