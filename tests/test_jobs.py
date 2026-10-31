"""Kho job SQLite + máy trạng thái + resume. Offline."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import jobs  # noqa: E402


@pytest.fixture(autouse=True)
def db(monkeypatch, tmp_path):
    monkeypatch.setenv("JOBS_DB_PATH", str(tmp_path / "j.sqlite"))


def test_state_machine_and_progress():
    j = jobs.create("a.pdf")
    assert jobs.get(j)["status"] == "queued"
    jobs.update(j, status="graph_running", chunks_total=4, chunks_done=1)
    v = jobs.get(j)
    assert v["status"] == "graph_running" and v["progress"] == 0.25 and v["error"] is None
    assert set(v) == {"job_id", "source", "status", "progress", "chunks_total", "chunks_done",
                      "triplets_added", "graph_status", "error", "created_at", "updated_at"}
    jobs.update(j, status="done")
    assert jobs.get(j)["progress"] == 1.0


def test_list_newest_first_and_unknown_none():
    a, b = jobs.create("a"), jobs.create("b")
    assert [x["job_id"] for x in jobs.list_jobs()] == [b, a]
    assert jobs.get("nope") is None


def test_restart_marks_running_jobs_interrupted():
    r, d, f = jobs.create("r"), jobs.create("d"), jobs.create("f")
    jobs.update(r, status="graph_running")
    jobs.update(d, status="done")
    jobs.update(f, status="fast_done")
    assert jobs.mark_interrupted() == 2
    assert jobs.get(r)["status"] == "interrupted" and jobs.get(f)["status"] == "interrupted"
    assert jobs.get(d)["status"] == "done"


def test_graph_pending_flag():
    assert not jobs.graph_pending()
    j = jobs.create("a")
    jobs.update(j, status="graph_running")
    assert jobs.graph_pending()
    jobs.update(j, status="done")
    assert not jobs.graph_pending()


def test_update_rejects_unknown_field():
    with pytest.raises(ValueError):
        jobs.update(jobs.create("a"), bogus=1)


def test_worker_runs_and_join():
    seen = []
    w = jobs.Worker(lambda jid, ctx: seen.append((jid, ctx)))
    w.submit("x", 1)
    w.submit("y", 2)
    assert w.join(5) and seen == [("x", 1), ("y", 2)]


def test_claim_is_compare_and_set():
    j = jobs.create("c")
    jobs.update(j, status="failed", error="x")
    assert jobs.claim(j, ("interrupted", "failed"), status="queued", error=None) is True
    assert jobs.claim(j, ("interrupted", "failed"), status="queued", error=None) is False
    assert jobs.get(j)["status"] == "queued" and jobs.get(j)["error"] is None
    assert jobs.get(j)["graph_status"] == "pending"
