"""Nạp hai pha: /upload trả sau pha nhanh, pha chậm chạy nền. Offline (Ollama/embedding giả)."""
import hashlib
import random
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import networkx as nx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.modules.setdefault("langchain_huggingface", MagicMock())
import backend  # noqa: E402
import jobs  # noqa: E402


class FakeEmbeddings:
    def _v(self, t):
        return [random.Random(int(hashlib.md5(t.encode()).hexdigest(), 16)).uniform(-1, 1) for _ in range(8)]

    def embed_documents(self, texts):
        return [self._v(t) for t in texts]

    def embed_query(self, t):
        return self._v(t)


class Reader:
    def __init__(self, path):
        texts = Path(path).read_text(encoding="utf-8").split("\f")
        self.pages = [SimpleNamespace(extract_text=(lambda t=t: t)) for t in texts]


def _ollama(reply="NONE"):
    def route(prompt):
        if "information-extraction engine" in prompt:
            return reply
        if "ENTITIES:" in prompt:
            return "NONE"
        if "OUTPUT (1, 2, or 3):" in prompt:
            return "1"
        return "<answer>ok</answer>"
    inst = MagicMock()
    inst.invoke.side_effect = route
    return MagicMock(return_value=inst)


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("JOBS_DB_PATH", str(tmp_path / "j.sqlite"))
    monkeypatch.setattr(backend, "CHROMA_PATH", tmp_path / "chroma")
    monkeypatch.setattr(backend, "_chroma_client", None)
    monkeypatch.setattr(backend, "_collection", None)
    monkeypatch.setattr(backend, "GRAPH_PATH", tmp_path / "g.graphml")
    monkeypatch.setattr(backend, "_knowledge_graph", nx.DiGraph())
    monkeypatch.setattr(backend, "_embeddings", FakeEmbeddings())
    monkeypatch.setattr(backend, "Ollama", _ollama("(Alpha, is, thing)"))
    monkeypatch.setattr(backend, "PdfReader", Reader)
    monkeypatch.setattr(backend, "gTTS", MagicMock())
    monkeypatch.setattr(backend, "_GRAPH_MAX_CHUNKS", 0)
    monkeypatch.setattr(backend, "_YIELD_COOLDOWN", 0.0)  # test cooldown riêng dùng đồng hồ giả
    monkeypatch.setattr(backend, "_chat_last_end", float("-inf"))
    yield TestClient(backend.app)
    backend.wait_for_jobs(30)


PAGES = "\f".join(f"trang {i} alpha beta" for i in range(6))


def _up(client, name="a.pdf"):
    r = client.post("/upload", files={"file": (name, PAGES.encode(), "application/pdf")})
    assert r.status_code == 200, r.text
    return r.json()


def test_upload_returns_after_fast_phase_with_old_fields(client, monkeypatch):
    gate = threading.Event()
    monkeypatch.setattr(backend, "_extract_triplets_from_chunk", lambda c: (gate.wait(10), [])[1])
    body = _up(client)
    for k in ("message", "source", "chunk_count", "total_chunks", "files", "graph_triplets_added",
              "graph_nodes", "graph_edges", "graph_persisted"):
        assert k in body
    assert body["graph_status"] == "pending" and body["graph_triplets_added"] == 0 and body["job_id"]
    assert body["total_chunks"] == body["chunk_count"] > 0  # vector đã ghi xong khi trả về
    assert client.post("/chat", json={"query": "alpha"}).json()["sources"]  # hỏi đáp được khi đồ thị chưa xong
    assert jobs.get(body["job_id"])["status"] in ("fast_done", "graph_running")
    gate.set()
    backend.wait_for_jobs(30)
    j = client.get(f"/jobs/{body['job_id']}").json()
    assert j["status"] == "done" and j["chunks_done"] == j["chunks_total"] == body["chunk_count"]


def test_jobs_unknown_is_404(client):
    assert client.get("/jobs/xyz").status_code == 404
    assert client.post("/jobs/xyz/resume").status_code == 404


def test_jobs_list_newest_first(client):
    a, b = _up(client, "a.pdf")["job_id"], _up(client, "b.pdf")["job_id"]
    backend.wait_for_jobs(30)
    assert [j["job_id"] for j in client.get("/jobs").json()][:2] == [b, a]


def test_graph_ready_flips_false_then_true(client, monkeypatch):
    gate = threading.Event()
    monkeypatch.setattr(backend, "_extract_triplets_from_chunk", lambda c: (gate.wait(10), [])[1])
    _up(client)
    assert client.get("/health").json()["graph_ready"] is False
    r = client.post("/chat", json={"query": "alpha"})
    assert r.status_code == 200 and r.json()["graph_ready"] is False
    gate.set()
    backend.wait_for_jobs(30)
    assert client.get("/health").json()["graph_ready"] is True
    assert client.post("/chat", json={"query": "alpha"}).json()["graph_ready"] is True


@pytest.mark.parametrize("st", ["interrupted", "failed"])
def test_graph_ready_false_for_interrupted_and_failed(client, st):
    jid = _up(client)["job_id"]
    backend.wait_for_jobs(30)
    assert client.get("/health").json()["graph_ready"] is True
    jobs.update(jid, status=st)
    assert client.get("/health").json()["graph_ready"] is False
    assert client.post("/chat", json={"query": "alpha"}).json()["graph_ready"] is False


def test_graph_ready_true_after_delete_of_unfinished_job(client):
    jid = _up(client)["job_id"]
    backend.wait_for_jobs(30)
    jobs.update(jid, status="interrupted")
    assert client.get("/health").json()["graph_ready"] is False
    assert client.delete(f"/jobs/{jid}").status_code == 200
    assert client.get("/health").json()["graph_ready"] is True


def test_resume_after_restart_is_idempotent(client, monkeypatch):
    body = _up(client)
    backend.wait_for_jobs(30)
    jid = body["job_id"]
    g = backend._knowledge_graph
    edges_before = sorted(g.edges(data="relation"))
    # mô phỏng kill giữa chừng: job dở dang ở đoạn 2
    jobs.update(jid, status="graph_running", chunks_done=2)
    assert jobs.mark_interrupted() == 1 and jobs.get(jid)["status"] == "interrupted"
    r = client.post(f"/jobs/{jid}/resume")
    assert r.status_code == 200
    backend.wait_for_jobs(30)
    assert jobs.get(jid)["status"] == "done"
    assert sorted(g.edges(data="relation")) == edges_before  # không nhân đôi quan hệ
    assert client.post(f"/jobs/{jid}/resume").status_code == 409  # đã done


def test_worker_yields_to_active_chat(client, monkeypatch):
    calls = []
    monkeypatch.setattr(backend, "_extract_triplets_from_chunk", lambda c: calls.append(1) or [])
    with backend._chat_gate():
        _up(client)
        time.sleep(0.5)
        assert calls == []  # đang có /chat -> worker chưa gọi LLM
    backend.wait_for_jobs(30)
    assert len(calls) > 0


def test_yield_wait_is_bounded(monkeypatch):
    monkeypatch.setattr(backend, "_YIELD_MAX_WAIT", 0.2)
    t0 = time.perf_counter()
    with backend._chat_gate():
        backend._wait_chat_idle()
    assert 0.15 < time.perf_counter() - t0 < 2


def test_parallel_chat_while_worker_writes_graph(client, monkeypatch):
    def slow(c):
        time.sleep(0.05)
        return [("Alpha", "is", c[:8]), ("Beta", "uses", c[:8])]
    monkeypatch.setattr(backend, "_extract_triplets_from_chunk", slow)
    monkeypatch.setattr(backend, "_YIELD_MAX_WAIT", 0.01)  # không để nhường làm chậm test
    big = "\f".join(f"đoạn {i} alpha beta " * 5 for i in range(30))
    r = client.post("/upload", files={"file": ("big.pdf", big.encode(), "application/pdf")})
    assert r.status_code == 200
    seen, errors = set(), []
    deadline = time.time() + 30
    while time.time() < deadline:
        c = client.post("/chat", json={"query": "alpha beta"})
        if c.status_code != 200:
            errors.append(c.status_code)
        seen.add(c.json()["graph_ready"])
        if client.get(f"/jobs/{r.json()['job_id']}").json()["status"] == "done":
            break
    assert backend.wait_for_jobs(30)
    seen.add(client.post("/chat", json={"query": "alpha"}).json()["graph_ready"])
    assert errors == [] and seen == {False, True}
    assert backend._knowledge_graph.number_of_edges() > 0


class FakeClock:
    def __init__(self):
        self.t = 100.0
        self.waits = []

    def __call__(self):
        return self.t

    def wait(self, timeout):  # thay _idle_wait: đồng hồ nhảy đúng bằng thời gian chờ
        self.waits.append(timeout)
        self.t += timeout


@pytest.fixture()
def clock(monkeypatch):
    c = FakeClock()
    monkeypatch.setattr(backend, "_clock", c)
    monkeypatch.setattr(backend, "_idle_wait", c.wait)
    monkeypatch.setattr(backend, "_YIELD_COOLDOWN", 3.0)
    monkeypatch.setattr(backend, "_YIELD_MAX_WAIT", 60.0)
    monkeypatch.setattr(backend, "_chat_last_end", float("-inf"))
    return c


def test_cooldown_blocks_until_quiet_then_proceeds(clock):
    with backend._chat_gate():
        pass  # /chat vừa xong tại t=100
    clock.t = 101.0  # mới nguội 1 s
    backend._wait_chat_idle()
    assert clock.waits == [2.0] and clock.t == 103.0  # chờ đúng phần nguội còn lại


def test_no_wait_when_cooled_or_never_chatted(clock):
    backend._wait_chat_idle()
    with backend._chat_gate():
        pass
    clock.t += 3.5
    backend._wait_chat_idle()
    assert clock.waits == []


def test_cooldown_wait_capped_at_max(clock, monkeypatch):
    monkeypatch.setattr(backend, "_YIELD_COOLDOWN", 1000.0)
    with backend._chat_gate():
        pass
    t0 = clock.t
    backend._wait_chat_idle()
    assert clock.t - t0 == 60.0


def _flaky_ollama(fail):
    """Ollama giả: lời gọi trích triplet ném ConnectionError khi fail(n) (n = số lần gọi, từ 1)."""
    n = [0]
    ok = _ollama("(Alpha, is, thing)").return_value

    def route(prompt):
        if "information-extraction engine" in prompt:
            n[0] += 1
            if fail(n[0]):
                raise ConnectionError("Connection refused")
        return ok.invoke.side_effect(prompt)
    inst = MagicMock()
    inst.invoke.side_effect = route
    return MagicMock(return_value=inst)


def test_ollama_down_marks_job_failed_then_resume_succeeds(client, monkeypatch):
    monkeypatch.setattr(backend, "Ollama", _flaky_ollama(lambda n: True))
    body = _up(client)
    backend.wait_for_jobs(30)
    j = client.get(f"/jobs/{body['job_id']}").json()
    assert j["status"] == "failed" and j["graph_status"] == "failed"
    assert "Không kết nối được Ollama" in j["error"]
    assert client.get("/health").json()["graph_ready"] is False  # failed: đồ thị thiếu
    monkeypatch.setattr(backend, "Ollama", _ollama("(Alpha, is, thing)"))  # Ollama hoạt động lại
    assert client.post(f"/jobs/{body['job_id']}/resume").status_code == 200
    backend.wait_for_jobs(30)
    j = client.get(f"/jobs/{body['job_id']}").json()
    assert j["status"] == "done" and j["triplets_added"] > 0 and j["error"] is None
    assert client.get("/health").json()["graph_ready"] is True


def test_sporadic_failures_done_with_warning(client, monkeypatch):
    monkeypatch.setattr(backend, "Ollama", _flaky_ollama(lambda n: n == 3))
    body = _up(client)
    backend.wait_for_jobs(30)
    j = client.get(f"/jobs/{body['job_id']}").json()
    assert j["status"] == "done" and "1/6" in j["error"]


def test_save_failure_does_not_advance_progress(client, monkeypatch):
    monkeypatch.setattr(backend, "_save_graph", lambda *a, **k: False)
    body = _up(client)
    backend.wait_for_jobs(30)
    j = client.get(f"/jobs/{body['job_id']}").json()
    assert j["chunks_done"] == 0 and j["error"] and "đồ thị" in j["error"]
    assert j["status"] == "failed"


def test_resume_without_chunk_ids_is_409(client):
    jid = jobs.create("x.pdf")
    jobs.update(jid, status="interrupted")
    r = client.post(f"/jobs/{jid}/resume")
    assert r.status_code == 409 and "upload lại" in r.json()["detail"]
    assert jobs.get(jid)["status"] == "interrupted"


def test_resume_with_ids_missing_in_chroma_is_409(client):
    _up(client)  # tạo collection có dữ liệu
    backend.wait_for_jobs(30)
    jid = jobs.create("x.pdf")
    jobs.update(jid, status="interrupted", chunk_ids=["khong-ton-tai"], chunks_total=1)
    r = client.post(f"/jobs/{jid}/resume")
    assert r.status_code == 409 and "upload lại" in r.json()["detail"]


def test_concurrent_resume_only_one_wins(client, monkeypatch):
    body = _up(client)
    backend.wait_for_jobs(30)
    jid = body["job_id"]
    jobs.update(jid, status="interrupted", chunks_done=0)
    barrier, codes = threading.Barrier(2), []

    def go():
        barrier.wait()
        codes.append(client.post(f"/jobs/{jid}/resume").status_code)
    ts = [threading.Thread(target=go) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(codes) == [200, 409]
    backend.wait_for_jobs(30)
    assert jobs.get(jid)["status"] == "done"
