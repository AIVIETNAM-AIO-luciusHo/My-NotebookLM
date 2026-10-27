"""P0-2: đo độ trễ /chat (Ollama + embedding thật, Chroma/graph tạm). Mẫu nhỏ, một máy.

Chạy: EVAL_PDF_DIR=<dir> python eval/p0_latency.py
"""
import argparse, json, os, random, statistics as st, subprocess, sys, time
from pathlib import Path

ap = argparse.ArgumentParser(); ap.add_argument("--repeat", type=int, default=0, help="R2-1: đo lặp N lượt toàn bộ câu doc gradient"); ARGS = ap.parse_args()
ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "eval" / "_work" / "p0" / ("latency_v2" if ARGS.repeat else "latency")
os.environ["CHROMA_PATH"] = str(WORK / "chroma")
os.environ["GRAPH_PATH"] = str(WORK / "graph.graphml")
os.environ["GRAPH_MAX_CHUNKS"] = "30"
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
import shutil
shutil.rmtree(WORK, ignore_errors=True); WORK.mkdir(parents=True)

import backend
from fastapi.testclient import TestClient

DOC = "bao-cao-bien-doi-gradient.pdf"
rows = [json.loads(l) for l in open(ROOT / "eval/golden.jsonl", encoding="utf-8")]
rows = [r for r in rows if r["doc"] == DOC]
qs = [r["question"] for r in rows]
assert len(qs) >= 10, len(qs)

# bọc tại điểm gọi (không sửa src/) để tách pha
phase: dict[str, float] = {}
def timed(name, fn):
    def w(*a, **k):
        t = time.perf_counter()
        try: return fn(*a, **k)
        finally: phase[name] = phase.get(name, 0) + time.perf_counter() - t
    return w
for n, f in [("entities", "_extract_query_entities"), ("classify", "_classify_query"), ("retrieval", "_query_workspace")]:
    setattr(backend, f"{f}", timed(n, getattr(backend, f)))

real_gtts = backend.gTTS
class NoTTS:
    def __init__(self, *a, **k): pass
    def write_to_fp(self, buf): buf.write(b"")

def stats(x):
    return {"n": len(x), "mean": st.mean(x), "sd": st.stdev(x), "p95": sorted(x)[min(len(x) - 1, int(round(0.95 * (len(x) - 1) + 0.4999)))],
            "min": min(x), "max": max(x)}

def run(c, questions):
    tot, ph = [], []
    for q in questions:
        phase.clear(); t = time.perf_counter()
        r = c.post("/chat", json={"query": q}); dt = time.perf_counter() - t
        assert r.status_code == 200, r.text
        tot.append(dt); p = dict(phase); p["generation_and_other"] = dt - sum(p.values()); ph.append(p)
    return tot, ph

c = TestClient(backend.app)
pdf = Path(os.environ["EVAL_PDF_DIR"]) / DOC
t = time.perf_counter()
r = c.post("/upload", files={"file": (DOC, pdf.read_bytes(), "application/pdf")})
up = time.perf_counter() - t
assert r.status_code == 200, r.text
upj = r.json()

backend.gTTS = NoTTS
run(c, qs[:1])  # warm-up, bỏ đi
def gpu():
    q = ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"]
    try:
        u, m, t = [float(x) for x in subprocess.check_output(q, text=True).split(",")]
        return {"util_pct": u, "mem_used_mib": m, "mem_total_mib": t}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}

def pct(x, q):
    x = sorted(x); i = (len(x) - 1) * q; lo = int(i); hi = min(lo + 1, len(x) - 1)
    return x[lo] + (x[hi] - x[lo]) * (i - lo)

if ARGS.repeat:
    g0 = gpu()
    waited = 0
    while g0.get("util_pct", 0) > 15 and waited < 120:  # chờ tối đa 120 s cho GPU rảnh
        time.sleep(10); waited += 10; g0 = gpu()
    order = [(r["id"], k + 1) for k in range(ARGS.repeat) for r in rows]
    random.Random(1).shuffle(order)
    qmap = {r["id"]: r["question"] for r in rows}
    per_call = []
    for qid, k in order:
        t, _ = run(c, [qmap[qid]])
        per_call.append({"question_id": qid, "pass": k, "seconds": t[0]})
    sec = [p["seconds"] for p in per_call]
    by_q = {}
    for p in per_call: by_q.setdefault(p["question_id"], []).append(p["seconds"])
    out = {"label": "mẫu nhỏ, một máy, chưa có CI", "doc": DOC, "seed": 1,
           "gpu_before": g0, "gpu_wait_seconds": waited, "gpu_after": gpu(),
           "gpu_note": "chờ tối đa 120 s nếu util > 15%; nếu vẫn cao thì đo tiếp và ghi rõ ở gpu_before",
           "gtts": "luôn stub; số gTTS thật ở vòng 1 là outlier mạng, không dùng làm ngưỡng",
           "upload": {"seconds": up, "chunk_count": upj["chunk_count"], "graph_triplets_added": upj["graph_triplets_added"],
                      "note": "GRAPH_MAX_CHUNKS=30 (đã giới hạn)"},
           "warmup": "1 lượt /chat bỏ đi",
           "overall": {"n": len(sec), "median": st.median(sec), "q1": pct(sec, .25), "q3": pct(sec, .75),
                       "iqr": pct(sec, .75) - pct(sec, .25), "mean": st.mean(sec), "sd": st.stdev(sec),
                       "p90": pct(sec, .9), "p95": pct(sec, .95) if len(sec) >= 20 else None, "max": max(sec), "min": min(sec)},
           "per_question_mean": {k: {"n": len(v), "mean": st.mean(v), "min": min(v), "max": max(v)} for k, v in sorted(by_q.items())},
           "per_call": per_call}
    (ROOT / "eval/p0/latency_v2.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "per_call"}, ensure_ascii=False, indent=2))
    sys.exit(0)

tot, ph = run(c, qs)
phases = {k: stats([p.get(k, 0.0) for p in ph]) for k in ("entities", "classify", "retrieval", "generation_and_other")}

tts = None
try:
    import urllib.request
    urllib.request.urlopen("https://translate.google.com", timeout=5)
    backend.gTTS = real_gtts
    tt, _ = run(c, qs[:5]); tts = stats(tt)
except Exception as e:
    tts = f"không đo được: {type(e).__name__}: {e}"

out = {"label": "mẫu nhỏ, một máy, chưa có CI", "doc": DOC,
       "upload": {"seconds": up, "chunk_count": upj["chunk_count"], "graph_triplets_added": upj["graph_triplets_added"],
                  "note": "GRAPH_MAX_CHUNKS=30: chỉ trích triplet từ 30 đoạn đầu (đã giới hạn)"},
       "warmup": "1 lượt /chat (câu đầu) bỏ đi",
       "chat_gtts_noop": {"condition": "gTTS thay bằng no-op (tách độ trễ mạng)", **stats(tot)},
       "chat_gtts_real": tts,
       "phases_gtts_noop": {"note": "generation_and_other = tổng - 3 pha bọc (gồm sinh câu trả lời và phần còn lại)", **phases},
       "per_question_seconds": tot}
(ROOT / "eval/p0/latency.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "per_question_seconds"}, ensure_ascii=False, indent=2))
