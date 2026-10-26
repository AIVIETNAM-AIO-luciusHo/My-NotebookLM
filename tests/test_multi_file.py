"""
Unit tests for the persistent multi-file workspace pipeline in src/backend.py.

Strategy
--------
Heavy dependencies are neutralised so the suite runs offline in seconds:

  * `langchain_huggingface` is force-mocked BEFORE backend is imported, so the
    module-level HuggingFaceEmbeddings singleton never loads model weights.
  * `backend._embeddings` is replaced with a deterministic fake (md5-seeded
    8-dim vectors) — real cosine math, zero model inference.
  * `backend.Ollama` is replaced with a prompt-routing mock (triplets /
    entities / classifier / answer), so no Ollama server is needed.
  * `backend.PdfReader` is replaced with a fake that treats the uploaded
    bytes as UTF-8 text, so "PDFs" are plain-text payloads.
  * `backend.gTTS` is replaced with a no-op, so /chat never touches the network.

ChromaDB itself is REAL: each test gets a genuine `chromadb.PersistentClient`
rooted in pytest's tmp_path, exercising the actual persistence layer.

The tests assert:
  1. Two successive /upload calls append cumulatively (no overwrite) and every
     chunk carries `{"source": <filename>}` metadata.
  2. GET /files returns the unique sorted source list ([] on an empty store).
  3. The store survives a simulated server restart (new client, same path).
  4. /chat retrieves globally across all accumulated files and reports each
     hit's source; an empty workspace yields a clean 400.
  5. The knowledge graph accumulates across uploads with per-file source
     metadata on nodes and edges.
"""

from __future__ import annotations

import hashlib
import random
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import networkx as nx
import pytest
from fastapi.testclient import TestClient

# ─────────────────────────────────────────────────────────────────────────────
# Import backend with heavy dependencies neutralised
# ─────────────────────────────────────────────────────────────────────────────

# Must happen BEFORE `import backend`: the module instantiates
# HuggingFaceEmbeddings at import time, which would load model weights.
sys.modules["langchain_huggingface"] = MagicMock(name="langchain_huggingface")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import backend  # noqa: E402

DOC_A = ("doc_a.pdf", "Alpha is a fast rocket engine. Alpha was designed by the Vega team.")
DOC_B = ("doc_b.pdf", "Beta is a deep-sea submarine. Beta was built at the Nautilus shipyard.")


class FakeEmbeddings:
    """Deterministic stand-in for HuggingFaceEmbeddings — no model weights."""

    _DIM = 8

    def _vector(self, text: str) -> list[float]:
        seed = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16)
        rng = random.Random(seed)
        return [rng.uniform(-1.0, 1.0) for _ in range(self._DIM)]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


class FakePdfReader:
    """Reads the uploaded bytes back as UTF-8 text — one single 'page'."""

    def __init__(self, path: str) -> None:
        text = Path(path).read_text(encoding="utf-8")
        self.pages = [SimpleNamespace(extract_text=lambda: text)]


def _routing_ollama(triplet_reply: str = "NONE") -> MagicMock:
    """An Ollama class mock whose instances answer by prompt type."""

    def route(prompt: str) -> str:
        if "information-extraction engine" in prompt:
            return triplet_reply
        if "ENTITIES:" in prompt:
            return "NONE"  # forces the deterministic keyword fallback
        if "OUTPUT (1, 2, or 3):" in prompt:
            return "1"
        return "<thinking>ok</thinking>\n<answer>Grounded answer.</answer>"

    instance = MagicMock()
    instance.invoke.side_effect = route
    return MagicMock(return_value=instance)


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    """A TestClient wired to an isolated persistent store, graph, and mocks."""
    monkeypatch.setattr(backend, "CHROMA_PATH", tmp_path / "chroma_db")
    monkeypatch.setattr(backend, "_chroma_client", None)
    monkeypatch.setattr(backend, "_collection", None)
    monkeypatch.setattr(backend, "GRAPH_PATH", tmp_path / "knowledge_graph.graphml")
    monkeypatch.setattr(backend, "_knowledge_graph", nx.DiGraph())
    monkeypatch.setattr(backend, "_embeddings", FakeEmbeddings())
    monkeypatch.setattr(backend, "Ollama", _routing_ollama())
    monkeypatch.setattr(backend, "PdfReader", FakePdfReader)
    monkeypatch.setattr(backend, "gTTS", MagicMock(name="gTTS"))
    return TestClient(backend.app)


def _upload(client: TestClient, filename: str, text: str) -> dict:
    response = client.post(
        "/upload",
        files={"file": (filename, text.encode("utf-8"), "application/pdf")},
    )
    assert response.status_code == 200, response.text
    return response.json()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Cumulative ingestion with source metadata
# ─────────────────────────────────────────────────────────────────────────────


class TestCumulativeIngestion:
    def test_two_uploads_append_without_overwrite(self, client: TestClient) -> None:
        first = _upload(client, *DOC_A)
        assert first["chunk_count"] >= 1
        assert first["total_chunks"] == first["chunk_count"]
        assert first["files"] == ["doc_a.pdf"]

        second = _upload(client, *DOC_B)
        assert second["total_chunks"] == first["chunk_count"] + second["chunk_count"]
        assert second["files"] == ["doc_a.pdf", "doc_b.pdf"]

    def test_every_chunk_carries_source_metadata(self, client: TestClient) -> None:
        _upload(client, *DOC_A)
        _upload(client, *DOC_B)

        records = backend._get_collection().get(include=["documents", "metadatas"])
        assert len(records["documents"]) >= 2
        for text, meta in zip(records["documents"], records["metadatas"]):
            assert set(meta) == {"source", "page"}
            if "Alpha" in text:
                assert meta["source"] == "doc_a.pdf"
            else:
                assert meta["source"] == "doc_b.pdf"

    def test_upload_rejects_non_pdf(self, client: TestClient) -> None:
        response = client.post(
            "/upload", files={"file": ("notes.txt", b"plain", "text/plain")}
        )
        assert response.status_code == 400

    def test_store_survives_simulated_restart(self, client: TestClient) -> None:
        _upload(client, *DOC_A)
        _upload(client, *DOC_B)

        # A restart drops the module-level singletons but not the on-disk store.
        backend._collection = None
        backend._chroma_client = None

        assert backend._get_collection().count() >= 2
        assert client.get("/files").json() == ["doc_a.pdf", "doc_b.pdf"]


# ─────────────────────────────────────────────────────────────────────────────
# 2. GET /files — workspace source listing
# ─────────────────────────────────────────────────────────────────────────────


class TestFilesEndpoint:
    def test_empty_workspace_returns_empty_list(self, client: TestClient) -> None:
        response = client.get("/files")
        assert response.status_code == 200
        assert response.json() == []

    def test_lists_unique_sorted_sources(self, client: TestClient) -> None:
        _upload(client, *DOC_B)
        _upload(client, *DOC_A)
        _upload(client, *DOC_A)  # re-upload must not duplicate the listing

        assert client.get("/files").json() == ["doc_a.pdf", "doc_b.pdf"]

    def test_health_reflects_workspace_state(self, client: TestClient) -> None:
        assert client.get("/health").json()["document_loaded"] is False
        _upload(client, *DOC_A)
        payload = client.get("/health").json()
        assert payload["document_loaded"] is True
        assert payload["files"] == ["doc_a.pdf"]


# ─────────────────────────────────────────────────────────────────────────────
# 3. /chat — global retrieval across all accumulated files
# ─────────────────────────────────────────────────────────────────────────────


class TestGlobalChatRetrieval:
    def test_chat_fuses_context_from_all_sources(self, client: TestClient) -> None:
        _upload(client, *DOC_A)
        _upload(client, *DOC_B)

        response = client.post("/chat", json={"query": "rocket and submarine"})
        assert response.status_code == 200, response.text
        payload = response.json()

        assert payload["answer"] == "Grounded answer."
        retrieved_sources = {s["source"] for s in payload["sources"]}
        assert retrieved_sources == {"doc_a.pdf", "doc_b.pdf"}
        for src in payload["sources"]:
            assert -1.0 <= src["cosine_score"] <= 1.0

    def test_chat_on_empty_workspace_returns_400(self, client: TestClient) -> None:
        response = client.post("/chat", json={"query": "anything"})
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Knowledge graph — cumulative, source-tagged ingestion
# ─────────────────────────────────────────────────────────────────────────────


class TestGraphAccumulation:
    def test_graph_accumulates_across_uploads_with_sources(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(backend, "Ollama", _routing_ollama("(Alpha, is, rocket)"))
        _upload(client, *DOC_A)
        monkeypatch.setattr(backend, "Ollama", _routing_ollama("(Beta, is, submarine)"))
        _upload(client, *DOC_B)

        graph = backend._knowledge_graph
        assert graph.has_edge("alpha", "rocket")
        assert graph.has_edge("beta", "submarine")
        assert graph["alpha"]["rocket"]["source"] == "doc_a.pdf"
        assert graph["beta"]["submarine"]["source"] == "doc_b.pdf"
        assert graph.nodes["alpha"]["source"] == "doc_a.pdf"
        assert graph.nodes["beta"]["source"] == "doc_b.pdf"
