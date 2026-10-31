import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createApi, normalizeBase, ApiError, T_FAST, T_UPLOAD, T_LLM } from '../../src/lib/api.js';

const reply = (status, body) => async () => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => { if (body === undefined) throw new Error('no json'); return body; },
});

test('normalizeBase bỏ dấu / cuối và có mặc định', () => {
  assert.equal(normalizeBase('http://x:1///'), 'http://x:1');
  assert.equal(normalizeBase(undefined), 'http://127.0.0.1:8000');
});

test('gọi đúng URL, method và JSON body', async () => {
  let seen;
  const api = createApi({ baseUrl: 'http://h:9/', fetchImpl: async (u, i) => { seen = [u, i]; return { ok: true, status: 200, json: async () => ({ ok: 1 }) }; } });
  assert.deepEqual(await api.chat('xin chào'), { ok: 1 });
  assert.equal(seen[0], 'http://h:9/chat');
  assert.equal(seen[1].method, 'POST');
  assert.equal(seen[1].body, JSON.stringify({ query: 'xin chào' }));
  await api.resumeJob('a/b');
  assert.equal(seen[0], 'http://h:9/jobs/a%2Fb/resume');
});

test('backend tắt (TypeError) -> offline, tiếng Việt', async () => {
  const api = createApi({ fetchImpl: async () => { throw new TypeError('Failed to fetch'); } });
  await assert.rejects(api.health(), (e) => e instanceof ApiError && e.kind === 'offline' && /Không kết nối được máy chủ/.test(e.message));
});

test('4xx dùng detail của backend', async () => {
  const api = createApi({ fetchImpl: reply(400, { detail: 'Workspace is empty.' }) });
  await assert.rejects(api.chat('q'), (e) => e.kind === 'client' && e.status === 400 && e.message === 'Chưa có tệp nào trong workspace. Hãy nạp PDF trước.' && e.detail === 'Workspace is empty.');
});

test('4xx không có detail -> thông điệp chung; 422 mảng lỗi được nối', async () => {
  await assert.rejects(createApi({ fetchImpl: reply(404, {}) }).jobs(), (e) => /mã 404/.test(e.message));
  const api = createApi({ fetchImpl: reply(422, { detail: [{ msg: 'a' }, { msg: 'b' }] }) });
  await assert.rejects(api.jobs(), (e) => e.message === 'a; b');
});

test('5xx -> server, kèm detail; nhận diện Ollama', async () => {
  const api = createApi({ fetchImpl: reply(500, { detail: 'Không kết nối được Ollama' }) });
  await assert.rejects(api.chat('q'), (e) => e.kind === 'server' && e.ollama === true && /mã 500/.test(e.message));
  await assert.rejects(createApi({ fetchImpl: reply(500, { detail: 'ollama model llama3.2 not found' }) }).chat('q'), (e) => e.kind === 'server' && e.ollama === false);
});

test('timeout -> kind timeout, không treo', async () => {
  const hang = (u, { signal }) => new Promise((_, rej) => {
    signal.addEventListener('abort', () => rej(Object.assign(new Error('aborted'), { name: 'AbortError' })));
  });
  const api = createApi({ fetchImpl: hang, timeoutMs: 20 });
  await assert.rejects(api.health(), (e) => e.kind === 'timeout' && /quá lâu/.test(e.message));
});

test('thân 200 không phải JSON -> parse', async () => {
  await assert.rejects(createApi({ fetchImpl: reply(200) }).files(), (e) => e.kind === 'parse');
});

test('upload gửi FormData field "file"', async () => {
  let body;
  const api = createApi({ fetchImpl: async (u, i) => { body = i.body; return { ok: true, status: 200, json: async () => ({}) }; } });
  await api.upload(new Blob(['x'], { type: 'application/pdf' }));
  assert.ok(body instanceof FormData && body.has('file'));
});

test('khoá hằng timeout theo từng loại gọi', async () => {
  assert.deepEqual([T_FAST, T_UPLOAD, T_LLM], [15000, 180000, 300000]);
  const seen = [];
  const orig = globalThis.setTimeout;
  globalThis.setTimeout = (fn, ms) => { seen.push(ms); return orig(() => {}, 0); };
  try {
    const api = createApi({ fetchImpl: reply(200, {}) });
    for (const call of [() => api.health(), () => api.upload(new Blob(['x'])), () => api.chat('q'),
      () => api.generateQuiz({}), () => api.generateMindmap('t')]) await call();
  } finally { globalThis.setTimeout = orig; }
  assert.deepEqual(seen, [T_FAST, T_UPLOAD, T_LLM, T_LLM, T_LLM]);
});

test('detail tiếng Anh của backend được dịch, giữ detail gốc', async () => {
  const api = createApi({ fetchImpl: reply(409, { detail: "Job is 'done', not resumable." }) });
  await assert.rejects(api.resumeJob('x'), (e) => /trạng thái có thể tiếp tục/.test(e.message) && /not resumable/.test(e.detail));
  const api2 = createApi({ fetchImpl: reply(422, { detail: 'No extractable text found in PDF.' }) });
  await assert.rejects(api2.upload(new Blob(['x'])), (e) => /Không tìm thấy văn bản/.test(e.message));
});

test('errorView nhận lỗi ApiError thật: nhánh ollama và badpdf (khi backend trả JSON)', async () => {
  const { errorView } = await import('../../src/utils/errorView.js');
  const o = await createApi({ fetchImpl: reply(500, { detail: 'Cannot reach Ollama at 11434' }) }).chat('q').catch((e) => e);
  assert.equal(errorView(o, 'chat').type, 'ollama');
  const b = await createApi({ fetchImpl: reply(422, { detail: 'No extractable text found in PDF.' }) }).upload(new Blob(['x'])).catch((e) => e);
  assert.equal(errorView(b, 'upload').type, 'badpdf');
});

test('errorView với JSON thật từ backend sau sửa L1 (503 Ollama, 400 PDF hỏng)', async () => {
  const { errorView } = await import('../../src/utils/errorView.js');
  const o = await createApi({ fetchImpl: reply(503, { detail: 'Không kết nối được Ollama. Hãy chạy `ollama serve`.' }) }).chat('q').catch((e) => e);
  assert.equal(errorView(o, 'chat').type, 'ollama');
  const b = await createApi({ fetchImpl: reply(400, { detail: 'PDF không đọc được hoặc bị hỏng.' }) }).upload(new Blob(['x'])).catch((e) => e);
  assert.equal(errorView(b, 'upload').type, 'badpdf');
});

test('T7: 503 -> Ollama; 500 có chữ ollama ngẫu nhiên không bị nhầm; 400 PDF không phải Ollama', async () => {
  const e503 = await createApi({ fetchImpl: reply(503, { detail: 'Không kết nối được Ollama. Hãy chạy `ollama serve`.' }) }).chat('q').catch((e) => e);
  assert.equal(e503.ollama, true);
  assert.equal((await createApi({ fetchImpl: reply(503) }).chat('q').catch((e) => e)).ollama, true);
  const e500 = await createApi({ fetchImpl: reply(500, { detail: 'Lỗi máy chủ nội bộ. (log ollama.py)' }) }).chat('q').catch((e) => e);
  assert.equal(e500.ollama, false);
  const e400 = await createApi({ fetchImpl: reply(400, { detail: 'PDF không đọc được hoặc bị hỏng.' }) }).upload(new Blob(['x'])).catch((e) => e);
  assert.equal(e400.ollama, false);
});

test('P1.7 deleteJob gọi DELETE /jobs/{id}; 409 là lỗi client tiếng Việt', async () => {
  let seen;
  const ok = createApi({ baseUrl: 'http://h:9', fetchImpl: async (u, i) => { seen = [u, i.method]; return { ok: true, status: 200, json: async () => ({ deleted: 'a' }) }; } });
  await ok.deleteJob('a b');
  assert.deepEqual(seen, ['http://h:9/jobs/a%20b', 'DELETE']);
  const e = await createApi({ fetchImpl: reply(409, { detail: 'Tác vụ đang chạy, chưa xoá được.' }) }).deleteJob('x').catch((x) => x);
  assert.equal(e.status, 409);
  assert.match(e.message, /đang chạy/);
});

test('P1.7 errorView: PDF có mật khẩu, không phải PDF, tệp hỏng là ba trường hợp khác nhau', async () => {
  const { errorView } = await import('../../src/utils/errorView.js');
  const up = (status, detail) => createApi({ fetchImpl: reply(status, { detail }) }).upload(new Blob(['x'])).catch((e) => e);
  assert.equal(errorView(await up(400, 'PDF có mật khẩu, hãy gỡ mật khẩu rồi tải lại.'), 'upload').type, 'encrypted');
  assert.equal(errorView(await up(400, 'Chỉ nhận tệp PDF.'), 'upload').type, 'notpdf');
  assert.equal(errorView(await up(400, 'PDF không đọc được hoặc bị hỏng.'), 'upload').type, 'badpdf');
});

test('P1.7 errorView: Ollama chưa tải mô hình (503), quá lâu (504), không kết nối (503)', async () => {
  const { errorView } = await import('../../src/utils/errorView.js');
  const chat = (status, detail) => createApi({ fetchImpl: reply(status, { detail }) }).chat('q').catch((e) => e);
  const m = errorView(await chat(503, 'Mô hình chưa được tải. Chạy `ollama pull llama3.2`.'), 'chat');
  assert.equal(m.title, 'Mô hình chưa được tải');
  assert.match(m.message, /ollama pull llama3\.2/);
  const t = errorView(await chat(504, 'Ollama phản hồi quá lâu.'), 'chat');
  assert.equal(t.title, 'Ollama phản hồi quá lâu');
  const c = errorView(await chat(503, 'Không kết nối được Ollama. Hãy chạy `ollama serve`.'), 'chat');
  assert.equal(c.title, 'Ollama chưa sẵn sàng');
});
