"""Hồi quy: _query_workspace trả 4-tuple (có page) không được làm vỡ /generate-quiz, /generate-mindmap."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import networkx as nx
import pytest
from fastapi.testclient import TestClient

sys.modules.setdefault("langchain_huggingface", MagicMock(name="langchain_huggingface"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import backend  # noqa: E402
from tests.test_multi_file import FakeEmbeddings, _routing_ollama  # noqa: E402

QUIZ = {"title": "Q", "questions": [{"question": "a?", "options": ["x", "y"], "correctAnswer": 0, "explanation": "e"}]}


def _ollama(reply: str) -> MagicMock:
    inst = MagicMock()
    inst.invoke.return_value = reply
    return MagicMock(return_value=inst)


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(backend, "CHROMA_PATH", tmp_path / "chroma_db")
    monkeypatch.setattr(backend, "_chroma_client", None)
    monkeypatch.setattr(backend, "_collection", None)
    monkeypatch.setattr(backend, "GRAPH_PATH", tmp_path / "g.graphml")
    monkeypatch.setattr(backend, "_knowledge_graph", nx.DiGraph())
    monkeypatch.setattr(backend, "_embeddings", FakeEmbeddings())
    monkeypatch.setattr(backend, "gTTS", MagicMock(name="gTTS"))
    col = backend._get_collection()
    texts = ["alpha một", "beta hai", "gamma ba"]
    col.add(ids=["1", "2", "3"], documents=texts, embeddings=FakeEmbeddings().embed_documents(texts),
            metadatas=[{"source": "a.pdf", "page": i} for i in (1, 2, 3)])
    return TestClient(backend.app)


def test_generate_quiz_ok_with_page_metadata(client, monkeypatch):
    monkeypatch.setattr(backend, "Ollama", _ollama(json.dumps(QUIZ)))
    r = client.post("/generate-quiz", json={"topic": "alpha", "num_questions": 1})
    assert r.status_code == 200, r.text
    assert r.json()["questions"][0]["correctAnswer"] == 0


def test_generate_mindmap_ok_with_page_metadata(client, monkeypatch):
    monkeypatch.setattr(backend, "Ollama", _ollama('graph TD\n    A["x"] --> B["y"]'))
    r = client.post("/generate-mindmap", json={"topic": "alpha"})
    assert r.status_code == 200, r.text


def test_chat_still_returns_page(client, monkeypatch):
    monkeypatch.setattr(backend, "Ollama", _routing_ollama())
    s = client.post("/chat", json={"query": "beta hai"}).json()["sources"]
    assert all(isinstance(x["page"], int) for x in s)
