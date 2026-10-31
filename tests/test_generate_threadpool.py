"""M1: /generate-* chạy trong threadpool; /health vẫn trả lời khi LLM đang bị giữ."""
from __future__ import annotations

import threading

import pytest

import backend
from tests.test_error_responses import client  # noqa: F401  (fixture)


class BlockingLLM:
    entered = threading.Event()
    release = threading.Event()

    def __init__(self, *a, **k): ...

    def invoke(self, prompt):
        BlockingLLM.entered.set()
        assert BlockingLLM.release.wait(10)
        return self.out


class QuizLLM(BlockingLLM):
    out = '{"questions":[{"question":"q","options":["a","b"],"correctAnswer":0}]}'


class MapLLM(BlockingLLM):
    out = "graph TD\n A-->B"


@pytest.mark.parametrize("path,llm", [("/generate-quiz", QuizLLM), ("/generate-mindmap", MapLLM)])
def test_health_responds_while_generate_blocked(client, monkeypatch, path, llm):  # noqa: F811
    llm.entered.clear(); llm.release.clear()
    monkeypatch.setattr(backend, "Ollama", llm)
    res = {}
    t = threading.Thread(target=lambda: res.update(r=client.post(path, json={"topic": "alpha"})))
    t.start()
    try:
        assert llm.entered.wait(10), "handler chưa gọi LLM"
        h = client.get("/health")  # nếu handler chặn event loop, lệnh này kẹt tới khi release
        assert h.status_code == 200
        assert t.is_alive()  # generate vẫn đang bị giữ lúc /health trả lời
    finally:
        llm.release.set()
        t.join(10)
    assert res["r"].status_code == 200
