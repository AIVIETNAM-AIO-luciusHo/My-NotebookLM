"""L1: lỗi chưa bắt phải ra JSON kèm header CORS (không phải 500 văn bản thuần)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import networkx as nx
import pytest
from fastapi.testclient import TestClient

sys.modules.setdefault("langchain_huggingface", MagicMock(name="langchain_huggingface"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import backend  # noqa: E402
from tests.test_multi_file import FakeEmbeddings  # noqa: E402

ORIGIN = {"Origin": "http://localhost:5173"}


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(backend, "CHROMA_PATH", tmp_path / "chroma_db")
    monkeypatch.setattr(backend, "_chroma_client", None)
    monkeypatch.setattr(backend, "_collection", None)
    monkeypatch.setattr(backend, "GRAPH_PATH", tmp_path / "g.graphml")
    monkeypatch.setattr(backend, "_knowledge_graph", nx.DiGraph())
    monkeypatch.setattr(backend, "_embeddings", FakeEmbeddings())
    col = backend._get_collection()
    col.add(ids=["1"], documents=["alpha"], embeddings=FakeEmbeddings().embed_documents(["alpha"]),
            metadatas=[{"source": "a.pdf", "page": 1}])
    return TestClient(backend.app, raise_server_exceptions=False)


def _boom(exc):
    return MagicMock(side_effect=exc)


def test_junk_pdf_400_json_cors(client):
    r = client.post("/upload", files={"file": ("junk.pdf", b"rac rac", "application/pdf")}, headers=ORIGIN)
    assert r.status_code == 400
    assert r.json() == {"detail": "PDF không đọc được hoặc bị hỏng."}
    assert r.headers["access-control-allow-origin"] == ORIGIN["Origin"]


def test_ollama_connect_error_503(client, monkeypatch):
    monkeypatch.setattr(backend, "Ollama", _boom(httpx.ConnectError("refused")))
    r = client.post("/chat", json={"query": "alpha"}, headers=ORIGIN)
    assert r.status_code == 503
    assert "Ollama" in r.json()["detail"]
    assert r.headers["access-control-allow-origin"] == ORIGIN["Origin"]


def test_unknown_error_500_no_leak(client, monkeypatch):
    monkeypatch.setattr(backend, "Ollama", _boom(RuntimeError("secret /etc/passwd")))
    r = client.post("/chat", json={"query": "alpha"}, headers=ORIGIN)
    assert r.status_code == 500
    assert r.json() == {"detail": "Lỗi máy chủ nội bộ."}
    assert "secret" not in r.text
    assert r.headers["access-control-allow-origin"] == ORIGIN["Origin"]


def test_http_exception_unchanged(client):
    r = client.post("/upload", files={"file": ("a.txt", b"x", "text/plain")}, headers=ORIGIN)
    assert r.status_code == 400
    assert r.json() == {"detail": "Chỉ nhận tệp PDF."}
    assert r.headers["access-control-allow-origin"] == ORIGIN["Origin"]
    assert client.get("/jobs/nope").json() == {"detail": "Job not found."}


def test_no_cors_header_for_foreign_origin(client, monkeypatch):
    monkeypatch.setattr(backend, "Ollama", _boom(RuntimeError("x")))
    r = client.post("/chat", json={"query": "alpha"}, headers={"Origin": "http://evil.example"})
    assert r.status_code == 500 and "access-control-allow-origin" not in r.headers


def test_fast_phase_bad_pdf_job_error_vietnamese(client):
    """Khoá job.error tiếng Việt ngay ở _fast_phase (không phụ thuộc exception handler)."""
    client.post("/upload", files={"file": ("junk.pdf", b"rac rac", "application/pdf")})
    jobs = client.get("/jobs").json()
    assert jobs[0]["status"] == "failed"
    assert jobs[0]["error"] == "PDF không đọc được hoặc bị hỏng."


def test_handler_pypdf_branch_direct():
    """Nhánh PyPdfError của handler không với tới qua /upload (đã bọc 400); gọi trực tiếp để khoá."""
    import asyncio
    from pypdf.errors import PyPdfError
    from starlette.requests import Request

    req = Request({"type": "http", "method": "POST", "path": "/x", "headers": [], "query_string": b""})
    r = asyncio.run(backend._unhandled_error(req, PyPdfError("bad")))
    assert r.status_code == 400 and b"PDF" in r.body


# ── P1.7 ────────────────────────────────────────────────────────────────────
def _encrypted_pdf() -> bytes:
    import io
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(100, 100)
    w.encrypt("pw")
    b = io.BytesIO()
    w.write(b)
    return b.getvalue()


def test_encrypted_pdf_400_password_message(client):
    r = client.post("/upload", files={"file": ("enc.pdf", _encrypted_pdf(), "application/pdf")}, headers=ORIGIN)
    assert r.status_code == 400
    assert r.json() == {"detail": "PDF có mật khẩu, hãy gỡ mật khẩu rồi tải lại."}
    assert r.headers["access-control-allow-origin"] == ORIGIN["Origin"]


def test_encrypted_pdf_job_error_distinct_from_corrupt(client):
    client.post("/upload", files={"file": ("enc.pdf", _encrypted_pdf(), "application/pdf")})
    client.post("/upload", files={"file": ("junk.pdf", b"rac rac", "application/pdf")})
    errs = {j["source"]: j["error"] for j in client.get("/jobs").json()}
    assert errs["enc.pdf"] == "PDF có mật khẩu, hãy gỡ mật khẩu rồi tải lại."
    assert errs["junk.pdf"] == "PDF không đọc được hoặc bị hỏng."


def test_handler_encrypted_branch_direct():
    import asyncio
    from pypdf.errors import FileNotDecryptedError
    from starlette.requests import Request

    req = Request({"type": "http", "method": "POST", "path": "/x", "headers": [], "query_string": b""})
    r = asyncio.run(backend._unhandled_error(req, FileNotDecryptedError("File has not been decrypted")))
    assert r.status_code == 400 and "mật khẩu".encode() in r.body


def test_non_pdf_upload_vietnamese_message(client):
    r = client.post("/upload", files={"file": ("a.txt", b"x", "text/plain")})
    assert r.status_code == 400 and r.json() == {"detail": "Chỉ nhận tệp PDF."}


def test_ollama_model_missing_503(client, monkeypatch):
    from ollama import ResponseError  # kiểu thật của thư viện: ResponseError(error, status_code)
    monkeypatch.setattr(backend, "Ollama", _boom(ResponseError("model 'llama3.2' not found", 404)))
    r = client.post("/chat", json={"query": "alpha"}, headers=ORIGIN)
    assert r.status_code == 503
    assert r.json() == {"detail": "Mô hình chưa được tải. Chạy `ollama pull llama3.2`."}


def test_ollama_other_response_error_stays_500(client, monkeypatch):
    from ollama import ResponseError
    monkeypatch.setattr(backend, "Ollama", _boom(ResponseError("boom", 500)))
    assert client.post("/chat", json={"query": "alpha"}).status_code == 500


def test_ollama_read_timeout_504(client, monkeypatch):
    monkeypatch.setattr(backend, "Ollama", _boom(httpx.ReadTimeout("slow")))
    r = client.post("/chat", json={"query": "alpha"}, headers=ORIGIN)
    assert r.status_code == 504 and r.json() == {"detail": "Ollama phản hồi quá lâu."}
    assert r.headers["access-control-allow-origin"] == ORIGIN["Origin"]


def test_connect_timeout_still_503(client, monkeypatch):
    monkeypatch.setattr(backend, "Ollama", _boom(httpx.ConnectTimeout("x")))
    assert client.post("/chat", json={"query": "alpha"}).status_code == 503


def test_delete_job_404_409_and_success(client):
    import jobs
    assert client.delete("/jobs/nope").status_code == 404
    running = jobs.create("r.pdf")
    for st in ("queued", "fast_running", "fast_done", "graph_running"):
        jobs.update(running, status=st)
        assert client.delete(f"/jobs/{running}").status_code == 409
    assert jobs.get(running) is not None
    for st in ("done", "failed", "interrupted"):
        j = jobs.create(f"{st}.pdf")
        jobs.update(j, status=st)
        assert client.delete(f"/jobs/{j}").json() == {"deleted": j}
        assert jobs.get(j) is None
    ids = [x["job_id"] for x in client.get("/jobs").json()]
    assert running in ids and j not in ids


def test_delete_job_keeps_chroma_and_graph(client):
    import jobs
    n = backend._get_collection().count()
    j = jobs.create("d.pdf")
    jobs.update(j, status="done")
    client.delete(f"/jobs/{j}")
    assert backend._get_collection().count() == n


# ── P1.8 v3: lỗi Ollama khi nhúng lúc /upload ──────────────────────────────
from types import SimpleNamespace  # noqa: E402

from ollama import ResponseError  # noqa: E402


def _upload_with_embed_error(client, monkeypatch, exc, embedding="bge-m3"):
    emb = SimpleNamespace(model="bge-m3", embed_documents=_boom(exc))
    monkeypatch.setattr(backend, "_embeddings", emb)
    monkeypatch.setattr(backend, "EMBEDDING", embedding)
    monkeypatch.setattr(backend, "PdfReader",
                        lambda path: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: "xin chao the gioi")]))
    r = client.post("/upload", files={"file": ("a.pdf", b"x", "application/pdf")}, headers=ORIGIN)
    return r, backend.jobs.list_jobs()[0]


def test_upload_embed_model_missing_503_vi(client, monkeypatch):
    r, job = _upload_with_embed_error(client, monkeypatch, ResponseError("model not found", 404))
    assert r.status_code == 503
    assert r.json() == {"detail": "Mô hình chưa được tải. Chạy `ollama pull bge-m3`."}
    assert r.headers["access-control-allow-origin"] == ORIGIN["Origin"]
    assert job["status"] == "failed" and "ollama pull bge-m3" in job["error"]


def test_upload_embed_connect_503_and_timeout_504(client, monkeypatch):
    r, _ = _upload_with_embed_error(client, monkeypatch, httpx.ConnectError("refused"))
    assert r.status_code == 503 and "ollama serve" in r.json()["detail"]
    r, _ = _upload_with_embed_error(client, monkeypatch, httpx.ReadTimeout("slow"))
    assert r.status_code == 504


def test_upload_embed_other_error_keeps_old_message(client, monkeypatch):
    r, _ = _upload_with_embed_error(client, monkeypatch, RuntimeError("boom"))
    assert r.status_code == 500 and r.json() == {"detail": "Vector indexing failed."}
    r, _ = _upload_with_embed_error(client, monkeypatch, ResponseError("x", 404), embedding="sbert")
    assert r.status_code == 500  # đường mặc định (sbert) không đổi
