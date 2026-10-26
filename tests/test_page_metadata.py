"""Trang (page) trong metadata chunk, /chat sources và cạnh đồ thị. Offline, Chroma thật trong tmp_path."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import networkx as nx
import pytest
from fastapi.testclient import TestClient

sys.modules.setdefault("langchain_huggingface", MagicMock(name="langchain_huggingface"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import backend  # noqa: E402
from tests.test_multi_file import FakeEmbeddings, _routing_ollama  # noqa: E402


class PagedReader:
    """Mỗi trang cách nhau bởi '\\f' trong nội dung tải lên."""

    def __init__(self, path: str) -> None:
        texts = Path(path).read_text(encoding="utf-8").split("\f")
        self.pages = [SimpleNamespace(extract_text=(lambda t=t: t)) for t in texts]


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setattr(backend, "CHROMA_PATH", tmp_path / "chroma_db")
    monkeypatch.setattr(backend, "_chroma_client", None)
    monkeypatch.setattr(backend, "_collection", None)
    monkeypatch.setattr(backend, "GRAPH_PATH", tmp_path / "g.graphml")
    monkeypatch.setattr(backend, "_knowledge_graph", nx.DiGraph())
    monkeypatch.setattr(backend, "_embeddings", FakeEmbeddings())
    monkeypatch.setattr(backend, "Ollama", _routing_ollama())
    monkeypatch.setattr(backend, "PdfReader", PagedReader)
    monkeypatch.setattr(backend, "gTTS", MagicMock(name="gTTS"))
    return TestClient(backend.app)


def _up(client: TestClient, name: str, pages: list[str]) -> None:
    r = client.post("/upload", files={"file": (name, "\f".join(pages).encode(), "application/pdf")})
    assert r.status_code == 200, r.text


def _metas() -> list[dict]:
    rec = backend._get_collection().get(include=["documents", "metadatas"])
    return list(zip(rec["documents"], rec["metadatas"]))


def test_every_chunk_has_page_ge_1(client):
    _up(client, "a.pdf", ["alpha một", "beta hai", "gamma ba"])
    assert all(m["page"] >= 1 and m["source"] == "a.pdf" for _, m in _metas())


def test_chunk_page_is_the_page_it_came_from(client):
    _up(client, "a.pdf", ["alpha một", "beta hai", "gamma ba"])
    expect = {"alpha": 1, "beta": 2, "gamma": 3}
    for text, meta in _metas():
        assert meta["page"] == expect[text.split()[0]]


def test_long_page_splits_but_never_crosses_page(client):
    long_p1 = "alpha " * 300  # > 600 ký tự -> nhiều chunk, đều thuộc trang 1
    _up(client, "a.pdf", [long_p1, "beta hai"])
    p1 = [t for t, m in _metas() if m["page"] == 1]
    assert len(p1) > 1 and all("beta" not in t for t in p1)


def test_multiple_files_keep_own_pages(client):
    _up(client, "a.pdf", ["alpha một", "alpha hai"])
    _up(client, "b.pdf", ["beta một"])
    got = {(m["source"], m["page"]) for _, m in _metas()}
    assert got == {("a.pdf", 1), ("a.pdf", 2), ("b.pdf", 1)}


def test_chat_returns_page_in_sources(client):
    _up(client, "a.pdf", ["alpha một", "beta hai"])
    body = client.post("/chat", json={"query": "beta hai"}).json()
    assert all(isinstance(s["page"], int) and s["page"] >= 1 for s in body["sources"])
    top = body["sources"][0]  # embedding giả tất định: query trùng chunk -> hạng 1
    assert (top["source"], top["page"]) == ("a.pdf", 2)


def test_old_metadata_without_page_is_backward_compatible(client):
    col = backend._get_collection()
    col.add(ids=["x"], documents=["cũ"], embeddings=FakeEmbeddings().embed_documents(["cũ"]),
            metadatas=[{"source": "old.pdf"}])
    body = client.post("/chat", json={"query": "cũ"}).json()
    assert body["sources"][0]["page"] is None and body["sources"][0]["source"] == "old.pdf"


def test_graph_edges_get_page_only_when_pages_given(monkeypatch):
    monkeypatch.setattr(backend, "_extract_triplets_from_chunk", lambda c: [("A", "rel", c)])
    g = nx.DiGraph()
    backend._ingest_chunks_into_graph(g, ["x", "y"], "d.pdf", pages=[3, 7])
    assert g["a"]["x"]["page"] == 3 and g["a"]["y"]["page"] == 7
    g2 = nx.DiGraph()
    backend._ingest_chunks_into_graph(g2, ["x"], "d.pdf")
    assert "page" not in g2["a"]["x"]
