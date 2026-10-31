"""Test _chunk_pages với tokenizer GIẢ (không cần transformers)."""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.modules.setdefault("langchain_huggingface", MagicMock())
os.environ.setdefault("CHROMA_PATH", str(Path(__file__).parent / "_unused_chroma"))
import backend  # noqa: E402


class FakeTok:
    """1 từ (tách theo khoảng trắng) = 1 token."""

    def encode(self, text, add_special_tokens=True):
        return text.split()


TEXT = " ".join(f"w{i}" for i in range(300))  # 300 từ, ~1190 ký tự


def test_default_is_char(monkeypatch):
    monkeypatch.delenv("CHUNKING", raising=False)
    chunks, pages = backend._chunk_pages([TEXT])
    # 600/75 ký tự trên chuỗi này: hằng số tính tay
    assert len(chunks) == 3 and pages == [1, 1, 1]
    assert all(len(c) <= 600 for c in chunks)
    assert backend._chunk_pages([TEXT], "char") == (chunks, pages)


def test_env_selects_token(monkeypatch):
    monkeypatch.setenv("CHUNKING", "token")
    monkeypatch.setattr(backend, "_load_tokenizer", lambda: FakeTok())
    chunks, _ = backend._chunk_pages([TEXT])
    assert len(chunks) == 2 and max(len(c.split()) for c in chunks) <= 210  # 300 từ -> 2 đoạn


def test_token_respects_limit(monkeypatch):
    monkeypatch.setattr(backend, "_load_tokenizer", lambda: FakeTok())
    chunks, _ = backend._chunk_pages([TEXT * 3], "token")
    assert len(chunks) >= 4
    assert all(len(c.split()) <= backend.TOKEN_CHUNK_SIZE for c in chunks)


def test_token_missing_tokenizer_raises(monkeypatch):
    monkeypatch.setattr(backend, "_tokenizer", None)
    monkeypatch.setitem(sys.modules, "transformers", None)  # import -> ImportError
    with pytest.raises(RuntimeError, match="transformers"):
        backend._chunk_pages([TEXT], "token")


def test_invalid_mode_raises():
    with pytest.raises(ValueError):
        backend._chunk_pages([TEXT], "word")


@pytest.mark.parametrize("mode", ["char", "token"])
def test_no_crossing_pages_and_empty_dropped(monkeypatch, mode):
    monkeypatch.setattr(backend, "_load_tokenizer", lambda: FakeTok())
    pages_in = ["alpha " * 50, "   \n", "", "beta " * 50]
    chunks, pages = backend._chunk_pages(pages_in, mode)
    assert set(pages) == {1, 4}
    for c, p in zip(chunks, pages):
        assert ("alpha" in c) == (p == 1) and ("beta" in c) == (p == 4)
