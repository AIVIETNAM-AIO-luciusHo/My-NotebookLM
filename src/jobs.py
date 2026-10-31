"""Kho job (SQLite, stdlib) và worker một luồng cho pha chậm của /upload.

Đường dẫn DB đọc từ env JOBS_DB_PATH tại mỗi lần gọi (mặc định jobs.sqlite ở gốc repo).
Trạng thái: queued -> fast_running -> fast_done -> graph_running -> done | failed | interrupted.
"""
import json
import os
import queue
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_ROOT = Path(__file__).resolve().parent.parent
# Job còn dang dở đồ thị: /chat báo graph_ready=False.
# graph_ready=false khi còn job chưa kết thúc tốt (kể cả failed/interrupted: đồ thị thiếu).
GRAPH_PENDING = ("queued", "fast_running", "fast_done", "graph_running", "interrupted", "failed")
# fast_done cũng tính: job đang xếp hàng chờ worker mà tiến trình chết sẽ không bao giờ chạy lại
_RUNNING = ("queued", "fast_running", "fast_done", "graph_running")
_lock = threading.Lock()
_SCHEMA = """CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY, source TEXT, status TEXT, chunks_total INTEGER DEFAULT 0,
    chunks_done INTEGER DEFAULT 0, triplets_added INTEGER DEFAULT 0, error TEXT,
    chunk_ids TEXT DEFAULT '[]', created_at TEXT, updated_at TEXT)"""
_GRAPH_STATUS = {"done": "done", "failed": "failed", "interrupted": "interrupted"}
_FIELDS = ("status", "chunks_total", "chunks_done", "triplets_added", "error", "chunk_ids")


def db_path() -> Path:
    return Path(os.getenv("JOBS_DB_PATH") or _ROOT / "jobs.sqlite")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _run(sql: str, args: tuple = (), fetch: bool = False) -> list[sqlite3.Row]:
    with _lock:
        con = sqlite3.connect(db_path(), timeout=30)
        try:
            con.row_factory = sqlite3.Row
            con.execute(_SCHEMA)
            rows = con.execute(sql, args).fetchall() if fetch else con.execute(sql, args) and []
            con.commit()
            return rows
        finally:
            con.close()


def _view(r: sqlite3.Row, full: bool = False) -> dict[str, Any]:
    total, done = r["chunks_total"] or 0, r["chunks_done"] or 0
    d = {
        "job_id": r["job_id"], "source": r["source"], "status": r["status"],
        "progress": 1.0 if r["status"] == "done" else (round(done / total, 4) if total else 0.0),
        "chunks_total": total, "chunks_done": done, "triplets_added": r["triplets_added"] or 0,
        "graph_status": _GRAPH_STATUS.get(r["status"], "pending"),
        "graph_status": _GRAPH_STATUS.get(r["status"], "pending"), "error": r["error"], "created_at": r["created_at"], "updated_at": r["updated_at"],
    }
    if full:
        d["chunk_ids"] = json.loads(r["chunk_ids"] or "[]")
    return d


def create(source: str) -> str:
    job_id, now = uuid.uuid4().hex, _now()
    _run("INSERT INTO jobs (job_id, source, status, created_at, updated_at) VALUES (?,?,?,?,?)",
         (job_id, source, "queued", now, now))
    return job_id


def update(job_id: str, **fields: Any) -> None:
    bad = set(fields) - set(_FIELDS)
    if bad:
        raise ValueError(f"Trường job không hợp lệ: {sorted(bad)}")
    if "chunk_ids" in fields:
        fields["chunk_ids"] = json.dumps(fields["chunk_ids"])
    cols = ", ".join(f"{k}=?" for k in fields)
    _run(f"UPDATE jobs SET {cols}, updated_at=? WHERE job_id=?", (*fields.values(), _now(), job_id))


def claim(job_id: str, from_statuses: tuple, **fields: Any) -> bool:
    """Compare-and-set nguyên tử: đổi trường nếu status hiện tại thuộc from_statuses; True nếu đổi được."""
    bad = set(fields) - set(_FIELDS)
    if bad:
        raise ValueError(f"Trường job không hợp lệ: {sorted(bad)}")
    cols = ", ".join(f"{k}=?" for k in fields)
    q = ",".join("?" * len(from_statuses))
    with _lock:
        con = sqlite3.connect(db_path(), timeout=30)
        try:
            con.execute(_SCHEMA)
            n = con.execute(f"UPDATE jobs SET {cols}, updated_at=? WHERE job_id=? AND status IN ({q})",
                            (*fields.values(), _now(), job_id, *from_statuses)).rowcount
            con.commit()
            return n == 1
        finally:
            con.close()


def get(job_id: str, full: bool = False) -> dict[str, Any] | None:
    rows = _run("SELECT * FROM jobs WHERE job_id=?", (job_id,), fetch=True)
    return _view(rows[0], full) if rows else None


def list_jobs() -> list[dict[str, Any]]:
    return [_view(r) for r in _run("SELECT * FROM jobs ORDER BY created_at DESC, rowid DESC", fetch=True)]


def delete_finished(job_id: str) -> bool:
    """Xoá bản ghi nếu ở trạng thái cuối (done|failed|interrupted); False nếu không có hoặc còn chạy."""
    with _lock:
        con = sqlite3.connect(db_path(), timeout=30)
        try:
            con.execute(_SCHEMA)
            n = con.execute("DELETE FROM jobs WHERE job_id=? AND status IN ('done','failed','interrupted')",
                            (job_id,)).rowcount
            con.commit()
            return n == 1
        finally:
            con.close()


def graph_pending() -> bool:
    q = ",".join("?" * len(GRAPH_PENDING))
    return bool(_run(f"SELECT 1 FROM jobs WHERE status IN ({q}) LIMIT 1", GRAPH_PENDING, fetch=True))


def mark_interrupted() -> int:
    """Gọi lúc khởi động: job đang chạy dở của tiến trình trước -> interrupted."""
    q = ",".join("?" * len(_RUNNING))
    rows = _run(f"SELECT job_id FROM jobs WHERE status IN ({q})", _RUNNING, fetch=True)
    for r in rows:
        update(r["job_id"], status="interrupted")
    return len(rows)


class Worker:
    """Một luồng nền xử lý lần lượt fn(job_id, ctx); khởi động lười."""

    def __init__(self, fn: Callable[[str, Any], None]) -> None:
        self._fn, self._q = fn, queue.Queue()
        self._thread: threading.Thread | None = None
        self._cv = threading.Condition()
        self._pending = 0

    def submit(self, job_id: str, ctx: Any = None) -> None:
        with self._cv:
            self._pending += 1
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._loop, name="graph-worker", daemon=True)
                self._thread.start()
        self._q.put((job_id, ctx))

    def _loop(self) -> None:
        while True:
            job_id, ctx = self._q.get()
            try:
                self._fn(job_id, ctx)
            except Exception:  # fn tự ghi failed; vòng lặp không được chết
                pass
            with self._cv:
                self._pending -= 1
                self._cv.notify_all()

    def join(self, timeout: float | None = None) -> bool:
        """Chờ hết việc; True nếu xong trước hạn."""
        with self._cv:
            return self._cv.wait_for(lambda: self._pending == 0, timeout)
