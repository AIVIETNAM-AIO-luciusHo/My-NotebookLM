/* global process, console */
// Backend giả cho smoke test: cùng hợp đồng với src/backend.py (chỉ các đường dẫn UI dùng).
// Điều khiển: POST /__reset, POST /__config {graphMs, graphReady}. Không đụng dữ liệu thật.
import http from 'node:http';
import { Buffer } from 'node:buffer';

const PORT = Number(process.env.FAKE_BACKEND_PORT || 8765);
const state = { files: [], jobs: [], graphMs: 2500 };
const TOTAL = 10;

const view = (j) => {
  const age = Date.now() - j.t0;
  const running = age < state.graphMs;
  const done = running ? Math.floor((age / state.graphMs) * TOTAL) : TOTAL;
  return {
    job_id: j.id, source: j.source, status: running ? 'graph_running' : 'done',
    progress: running ? done / TOTAL : 1, chunks_total: TOTAL, chunks_done: done, triplets_added: done,
    graph_status: running ? 'pending' : 'done', error: null,
  };
};
const graphReady = () => !state.jobs.some((j) => view(j).status !== 'done');

const send = (res, code, body) => {
  res.writeHead(code, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS',
  });
  res.end(JSON.stringify(body));
};
const readBody = (req) => new Promise((ok) => {
  const parts = [];
  req.on('data', (c) => parts.push(c));
  req.on('end', () => ok(Buffer.concat(parts)));
});

http.createServer(async (req, res) => {
  const { pathname } = new URL(req.url, 'http://x');
  if (req.method === 'OPTIONS') return send(res, 204, {});
  if (pathname === '/__reset') { state.files = []; state.jobs = []; state.graphMs = 2500; return send(res, 200, {}); }
  if (pathname === '/__config') { Object.assign(state, JSON.parse((await readBody(req)).toString() || '{}')); return send(res, 200, {}); }
  if (pathname === '/health') {
    return send(res, 200, { status: 'ok', document_loaded: state.files.length > 0, files: state.files,
      chunk_count: state.files.length * TOTAL, graph_ready: graphReady() });
  }
  if (pathname === '/files') return send(res, 200, state.files);
  if (pathname === '/jobs') return send(res, 200, [...state.jobs].reverse().map(view));
  const del = /^\/jobs\/([^/]+)$/.exec(pathname);
  if (del && req.method === 'DELETE') {
    const job = state.jobs.find((j) => j.id === del[1]);
    if (!job) return send(res, 404, { detail: 'Job not found.' });
    if (view(job).status !== 'done') return send(res, 409, { detail: 'Tác vụ đang chạy, chưa xoá được.' });
    state.jobs = state.jobs.filter((j) => j !== job);
    return send(res, 200, { deleted: job.id });
  }
  if (pathname === '/upload' && req.method === 'POST') {
    const raw = (await readBody(req)).toString('latin1');
    const name = /filename="([^"]+)"/.exec(raw)?.[1] ?? 'unknown.pdf';
    if (!state.files.includes(name)) state.files.push(name);
    const job = { id: `job-${state.jobs.length + 1}`, source: name, t0: Date.now() };
    state.jobs.push(job);
    return send(res, 200, { source: name, files: state.files, job_id: job.id, graph_status: 'pending' });
  }
  if (pathname === '/chat' && req.method === 'POST') {
    if (!state.files.length) return send(res, 400, { detail: 'Workspace is empty. POST to /upload first.' });
    return send(res, 200, {
      answer: 'Gradient descent cập nhật tham số theo hướng ngược gradient.\n| Tham số | Ý nghĩa |\n| --- | --- |\n| lr | tốc độ học |',
      audio_base64: 'data:audio/mp3;base64,AAAA', graph_facts: [], graph_ready: graphReady(),
      sources: [{ text: 'Đoạn mô tả gradient descent.', cosine_score: 0.8123, source: state.files[0], page: 3 }],
    });
  }
  return send(res, 404, { detail: 'Not found' });
}).listen(PORT, '127.0.0.1', () => console.log(`fake backend on ${PORT}`));
