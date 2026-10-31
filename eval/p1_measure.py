"""Đo P1 (nạp hai pha) trên Chroma/graph/jobs TẠM (eval/_work/p1/). Cần Ollama + EVAL_PDF_DIR.

  python -m eval.p1_measure --t-ready | --latency-paired [--phases|--v2] | --latency-think | --triplet-parity
  --phases: như --latency-paired nhưng ghi eval/p1/latency_phases.json (chạy với GRAPH_YIELD_COOLDOWN_SECONDS=0 = chẩn đoán trước khi sửa)
  --v2: ghi eval/p1/latency_paired_v2.json (nguội mặc định)
Số đo: mẫu nhỏ, một máy. gTTS được thay bằng giả để cô lập tranh chấp LLM/GPU (cả hai điều kiện như nhau).
"""
import argparse
import json
import os
import random
import shutil
import statistics as st
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "eval" / "_work" / "p1"
OUT = ROOT / "eval" / "p1"
PDF = "bao-cao-bien-doi-gradient.pdf"


def setup():
    boot = WORK / "boot"
    shutil.rmtree(boot, ignore_errors=True)
    boot.mkdir(parents=True)
    os.environ["CHROMA_PATH"] = str(boot / "chroma_db")
    os.environ["GRAPH_PATH"] = str(boot / "knowledge_graph.graphml")
    os.environ["JOBS_DB_PATH"] = str(boot / "jobs.sqlite")
    sys.path[:0] = [str(ROOT), str(ROOT / "src")]
    global backend, nx, TestClient, find_pdf, load_golden
    import backend
    import networkx as nx
    from fastapi.testclient import TestClient
    from eval.check_quotes import find_pdf, load_golden
    backend.gTTS = MagicMock(name="gTTS")
    instrument()
    backend._embeddings.embed_query("khởi động")  # làm nóng embedding


PH = {"ent": 0.0, "cls": 0.0}  # giây tích luỹ trong một lượt /chat (các lượt chạy tuần tự)
TRIP_CALLS = [0]  # số lần worker gọi trích triplet


def instrument():
    """Bọc hàm tại điểm patch để đo thời gian từng pha; không đổi hành vi."""
    def timed(name, key):
        orig = getattr(backend, name)

        def w(*a, **k):
            t0 = time.perf_counter()
            try:
                return orig(*a, **k)
            finally:
                PH[key] += time.perf_counter() - t0
        setattr(backend, name, w)
    timed("_extract_query_entities", "ent")
    timed("_classify_query", "cls")
    orig = backend._extract_triplets_from_chunk

    def trip(c):
        TRIP_CALLS[0] += 1
        return orig(c)
    backend._extract_triplets_from_chunk = trip


def fresh(tag, max_chunks):
    d = WORK / tag
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    os.environ["JOBS_DB_PATH"] = str(d / "jobs.sqlite")
    backend.CHROMA_PATH, backend._chroma_client, backend._collection = d / "chroma_db", None, None
    backend.GRAPH_PATH, backend._knowledge_graph = d / "g.graphml", nx.DiGraph()
    backend._GRAPH_MAX_CHUNKS = max_chunks


def post_upload(client):
    data = Path(find_pdf(PDF)).read_bytes()
    t0 = time.perf_counter()
    r = client.post("/upload", files={"file": (PDF, data, "application/pdf")})
    dt = time.perf_counter() - t0
    assert r.status_code == 200, r.text
    return r.json(), dt


def summ(xs):
    return {"mean": round(st.mean(xs), 3), "sd": round(st.stdev(xs), 3) if len(xs) > 1 else 0.0,
            "min": round(min(xs), 3), "max": round(max(xs), 3)}


def t_ready(n=5):
    client = TestClient(backend.app)
    runs = []
    for i in range(n):
        fresh(f"t{i}", 30)
        body, dt = post_upload(client)
        chat = client.post("/chat", json={"query": "gradient là gì?"})
        ok = chat.status_code == 200 and len(chat.json()["sources"]) > 0
        backend.wait_for_jobs(900)
        runs.append({"run": i + 1, "t_ready_s": round(dt, 3), "chunks": body["chunk_count"],
                     "chat_ok_with_sources": ok, "job": client.get(f"/jobs/{body['job_id']}").json()["status"]})
        print(runs[-1])
    res = {"label": "mẫu nhỏ, một máy", "GRAPH_MAX_CHUNKS": 30, "pdf": PDF, "runs": runs,
           **summ([r["t_ready_s"] for r in runs]), "threshold_mean_le_s": 10}
    res["pass"] = res["mean"] <= 10 and all(r["chat_ok_with_sources"] for r in runs)
    (OUT / "t_ready.json").write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "runs"}, ensure_ascii=False))
    return 0 if res["pass"] else 1


def latency_paired(rounds=3, out="latency_paired.json", phases=False, gap=0.0):
    gpu = subprocess.run(["nvidia-smi"], capture_output=True, text=True).stdout
    qs = [g for g in load_golden() if g["doc"] == PDF][:10]
    client = TestClient(backend.app)
    fresh("lat", 0)
    body, _ = post_upload(client)  # nạp toàn bộ đoạn; pha chậm bắt đầu nền
    jid = body["job_id"]
    rng = random.Random(1)
    bg, calls = [], []

    def one(q):
        s0 = client.get(f"/jobs/{jid}").json()["status"]
        PH["ent"] = PH["cls"] = 0.0
        t0 = time.perf_counter()
        r = client.post("/chat", json={"query": q["question"]})
        dt = time.perf_counter() - t0
        s1 = client.get(f"/jobs/{jid}").json()["status"]
        assert r.status_code == 200, r.text
        one.ph = {"ent_s": round(PH["ent"], 3), "cls_s": round(PH["cls"], 3), "gen_rest_s": round(dt - PH["ent"] - PH["cls"], 3)}
        return dt, s0, s1

    trip0 = TRIP_CALLS[0]
    for rd in range(rounds):  # (ii) nền đang chạy
        order = qs[:]
        rng.shuffle(order)
        for q in order:
            dt, s0, s1 = one(q)
            valid = s0 == "graph_running" and s1 == "graph_running"
            calls.append({"cond": "background", "id": q["id"], "round": rd, "s": round(dt, 3), "valid": valid, **one.ph})
            time.sleep(gap)
    job_end = client.get(f"/jobs/{jid}").json()
    trip_bg = TRIP_CALLS[0] - trip0
    backend.wait_for_jobs(1800)
    one(qs[0])  # làm nóng sau khi nền xong
    rng = random.Random(1)
    for rd in range(rounds):  # (i) rảnh
        order = qs[:]
        rng.shuffle(order)
        for q in order:
            dt, s0, s1 = one(q)
            calls.append({"cond": "idle", "id": q["id"], "round": rd, "s": round(dt, 3), "valid": s0 == s1 == "done", **one.ph})
    ratios = {}
    for q in qs:
        b = [c["s"] for c in calls if c["cond"] == "background" and c["valid"] and c["id"] == q["id"]]
        i = [c["s"] for c in calls if c["cond"] == "idle" and c["valid"] and c["id"] == q["id"]]
        if b and i:
            ratios[q["id"]] = round(st.median(b) / st.median(i), 3)
    med = round(st.median(ratios.values()), 3) if ratios else None
    res = {"label": "mẫu nhỏ, một máy; gTTS giả", "pdf": PDF, "seed": 1, "rounds": rounds,
           "valid_background_calls": sum(c["cond"] == "background" and c["valid"] for c in calls),
           "total_background_calls": sum(c["cond"] == "background" for c in calls),
           "valid_idle_calls": sum(c["cond"] == "idle" and c["valid"] for c in calls),
           "ratio_per_question": ratios, "median_ratio": med, "threshold": 1.5,
           "yield_cooldown_s": backend._YIELD_COOLDOWN, "gap_s": gap,
           "iqr_of_ratios": [round(x, 3) for x in st.quantiles(ratios.values(), n=4)[::2]] if len(ratios) > 1 else None, "triplet_calls_during_background": trip_bg,
           "job_state_after_background_phase": job_end, "nvidia_smi_before": gpu, "calls": calls}
    res["phase_medians_s"] = {c: {k: round(st.median([x[k] for x in calls if x["cond"] == c and x["valid"]]), 3)
                                  for k in ("s", "ent_s", "cls_s", "gen_rest_s")} for c in ("idle", "background")}
    res["pass"] = med is not None and med <= 1.5
    (OUT / out).write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k not in ("calls", "nvidia_smi_before")}, ensure_ascii=False))
    return 0 if res["pass"] else 1


def latency_think(gap=10.0):
    """10 câu cách nhau `gap` s (nền đang chạy), rồi 10 câu rảnh; tỉ số theo câu + số đoạn worker xử lý."""
    gpu = subprocess.run(["nvidia-smi"], capture_output=True, text=True).stdout
    qs = [g for g in load_golden() if g["doc"] == PDF][:10]
    client = TestClient(backend.app)
    fresh("think", 0)
    body, _ = post_upload(client)
    jid = body["job_id"]
    trip0 = TRIP_CALLS[0]
    bg = []
    for q in qs:
        s0 = client.get(f"/jobs/{jid}").json()["status"]
        t0 = time.perf_counter()
        r = client.post("/chat", json={"query": q["question"]})
        dt = time.perf_counter() - t0
        assert r.status_code == 200, r.text
        bg.append({"id": q["id"], "s": round(dt, 3), "status_before": s0})
        time.sleep(gap)
    chunks_bg = TRIP_CALLS[0] - trip0
    job_end = client.get(f"/jobs/{jid}").json()
    backend.wait_for_jobs(1800)
    client.post("/chat", json={"query": qs[0]["question"]})  # làm nóng
    idle = []
    for q in qs:
        t0 = time.perf_counter()
        client.post("/chat", json={"query": q["question"]})
        idle.append({"id": q["id"], "s": round(time.perf_counter() - t0, 3)})
    ratios = {b["id"]: round(b["s"] / i["s"], 3) for b, i in zip(bg, idle)}
    med = round(st.median(ratios.values()), 3)
    res = {"label": "mẫu nhỏ, một máy; gTTS giả; 1 lượt/câu", "gap_s": gap, "yield_cooldown_s": backend._YIELD_COOLDOWN,
           "chunks_processed_by_worker_during_background": chunks_bg, "ratio_per_question": ratios, "median_ratio": med,
           "background_calls": bg, "idle_calls": idle, "job_state_after_background_phase": job_end, "nvidia_smi_before": gpu,
           "pass": chunks_bg > 0}
    (OUT / "latency_think.json").write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k not in ("nvidia_smi_before",)}, ensure_ascii=False))
    return 0 if res["pass"] else 1


def triplet_parity(n=40):
    from pypdf import PdfReader
    client = TestClient(backend.app)
    fresh("par_bg", n)
    body, _ = post_upload(client)
    backend.wait_for_jobs(900)
    job = client.get(f"/jobs/{body['job_id']}").json()
    bg = job["triplets_added"]
    bg_edges = backend._knowledge_graph.number_of_edges()
    pages = [p.extract_text() or "" for p in PdfReader(find_pdf(PDF)).pages]
    chunks, cp = backend._chunk_pages(pages)
    g = nx.DiGraph()
    backend._GRAPH_MAX_CHUNKS = n
    sync = backend._ingest_chunks_into_graph(g, chunks, PDF, cp)
    diff = abs(bg - sync) / sync if sync else None
    res = {"label": "mẫu nhỏ, một máy", "chunks": n, "background_triplets": bg, "background_edges": bg_edges,
           "sync_triplets": sync, "sync_edges": g.number_of_edges(), "rel_diff": round(diff, 4) if diff is not None else None,
           "threshold": 0.10, "pass": diff is not None and diff <= 0.10, "job": job}
    (OUT / "triplet_parity.json").write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res["pass"] else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--t-ready", action="store_true")
    g.add_argument("--latency-paired", action="store_true")
    g.add_argument("--triplet-parity", action="store_true")
    g.add_argument("--latency-think", action="store_true")
    ap.add_argument("--phases", action="store_true")
    ap.add_argument("--v2", action="store_true")
    ap.add_argument("--think-v2", action="store_true", help="P1-2 theo nhịp người dùng: 10 câu x 3 lượt cách nhau 10 s")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    setup()
    if a.latency_paired and a.think_v2:
        sys.exit(latency_paired(out="latency_think_v2.json", gap=10.0))
    if a.latency_paired:
        out = "latency_phases.json" if a.phases else "latency_paired_v2.json" if a.v2 else "latency_paired.json"
        sys.exit(latency_paired(out=out))
    sys.exit(t_ready() if a.t_ready else latency_think() if a.latency_think else triplet_parity())
