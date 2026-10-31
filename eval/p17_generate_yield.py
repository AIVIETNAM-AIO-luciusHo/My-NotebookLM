"""Đo /generate-mindmap khi đồ thị đang dựng (A) so với rảnh (B). Quy tắc đặt trước: chỉ cài
cơ chế nhường nếu median(A)/median(B) > 1.5 (cùng ngưỡng D2 của /chat).

  EVAL_PDF_DIR=<thư mục chứa PDF> python -m eval.p17_generate_yield [--n-a 8] [--n-b 6]

Chroma/graph/jobs TẠM trong eval/_work/p17. Cần Ollama. Thứ tự B1 (rảnh thật: worker chưa chạy) ->
A (worker chạy) -> B2 (sau khi job xong); B báo gộp và riêng từng khối để thấy trôi. Mẫu nhỏ, một máy.
"""
import argparse
import json
import os
import shutil
import statistics as st
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "eval" / "_work" / "p17"
OUT = ROOT / "eval" / "p17" / "generate_yield.json"
PDF = "bao-cao-bien-doi-gradient.pdf"
TOPIC = "Gradient descent"  # cùng một chủ đề/prompt cho mọi mẫu


def p95(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))]


def summ(xs):
    return {"n": len(xs), "median": round(st.median(xs), 3), "p95": round(p95(xs), 3),
            "min": round(min(xs), 3), "max": round(max(xs), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-a", type=int, default=8)
    ap.add_argument("--n-b", type=int, default=6)  # mỗi khối B
    ap.add_argument("--max-a-tries", type=int, default=20)
    args = ap.parse_args()

    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    os.environ["CHROMA_PATH"] = str(WORK / "chroma_db")
    os.environ["GRAPH_PATH"] = str(WORK / "knowledge_graph.graphml")
    os.environ["JOBS_DB_PATH"] = str(WORK / "jobs.sqlite")
    sys.path[:0] = [str(ROOT), str(ROOT / "src")]
    import backend
    from fastapi.testclient import TestClient
    from eval.check_quotes import find_pdf

    client = TestClient(backend.app)
    backend._embeddings.embed_query("khởi động")

    # Nạp PDF nhưng giữ worker lại: B1 là rảnh thật.
    real_submit = backend._graph_worker.submit
    backend._graph_worker.submit = lambda *a, **k: None
    r = client.post("/upload", files={"file": (PDF, Path(find_pdf(PDF)).read_bytes(), "application/pdf")})
    assert r.status_code == 200, r.text
    jid, chunks = r.json()["job_id"], r.json()["chunk_count"]
    backend._graph_worker.submit = real_submit

    samples = []

    def one(cond):
        s0 = client.get(f"/jobs/{jid}").json()["status"]
        t0 = time.perf_counter()
        resp = client.post("/generate-mindmap", json={"topic": TOPIC})
        dt = time.perf_counter() - t0
        s1 = client.get(f"/jobs/{jid}").json()["status"]
        valid = resp.status_code == 200 and (s0 == s1 == "graph_running" if cond == "A" else s0 == s1 and s0 != "graph_running")
        samples.append({"cond": cond, "s": round(dt, 3), "status": resp.status_code, "job_before": s0, "job_after": s1, "valid": valid})
        print(samples[-1], flush=True)
        return valid

    one("warmup")  # khởi động nóng, bỏ
    samples.clear()
    ok = 0
    while ok < args.n_b:
        ok += one("B1")
    backend._graph_worker.submit(jid, backend._current_ctx())  # đồ thị bắt đầu dựng
    while client.get(f"/jobs/{jid}").json()["status"] != "graph_running":
        time.sleep(0.2)
    ok = tries = 0
    while ok < args.n_a and tries < args.max_a_tries:
        ok += one("A")
        tries += 1
    job_mid = client.get(f"/jobs/{jid}").json()
    backend.wait_for_jobs(3600)
    job_end = client.get(f"/jobs/{jid}").json()
    one("warmup2")  # làm nóng lại sau job, bỏ
    samples.pop()
    ok = 0
    while ok < args.n_b:
        ok += one("B2")

    A = [x["s"] for x in samples if x["cond"] == "A" and x["valid"]]
    B1 = [x["s"] for x in samples if x["cond"] == "B1" and x["valid"]]
    B2 = [x["s"] for x in samples if x["cond"] == "B2" and x["valid"]]
    B = B1 + B2
    ratio = round(st.median(A) / st.median(B), 3)
    res = {"label": "mẫu nhỏ, một máy", "pdf": PDF, "topic": TOPIC, "chunks": chunks, "threshold": 1.5,
           "A_graph_running": summ(A), "B_idle_pooled": summ(B), "B1_before": summ(B1), "B2_after": summ(B2),
           "ratio_median_A_over_B": ratio,
           "ratio_vs_B1": round(st.median(A) / st.median(B1), 3), "ratio_vs_B2": round(st.median(A) / st.median(B2), 3),
           "invalid_samples": sum(not x["valid"] for x in samples), "job_mid": job_mid, "job_end": job_end,
           "decision": "CÀI nhường" if ratio > 1.5 else "KHÔNG cài nhường (ratio <= 1.5)", "samples": samples}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "samples"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
