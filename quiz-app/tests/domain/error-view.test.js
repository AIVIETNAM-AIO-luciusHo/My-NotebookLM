import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ApiError, createApi } from '../../src/lib/api.js';
import { errorView, infraErrorView } from '../../src/utils/errorView.js';

test('L5: tệp không-PDF phía client dùng cùng khung "Không phải tệp PDF"', () => {
  const v = errorView({ kind: 'client', uploadReason: 'notpdf', message: 'Chỉ nhận tệp PDF.' }, 'upload');
  assert.equal(v.type, 'notpdf');
  assert.match(v.message, /Chỉ nhận tệp PDF/);
});

test('L6: thông điệp mất kết nối không ghi cứng số cổng', async () => {
  assert.doesNotMatch(errorView({ kind: 'offline' }).message, /\d{4}/);
  const api = createApi({ baseUrl: 'http://x:9', fetchImpl: async () => { throw new TypeError('fail'); } });
  await assert.rejects(api.health(), (e) => e.kind === 'offline' && !/\d{4}/.test(e.message));
});

test('L7: infraErrorView dùng khung riêng cho 503/offline/timeout, null cho lỗi thường', () => {
  const o = new ApiError('server', 'Máy chủ gặp lỗi (mã 503)', { status: 503, detail: 'Không kết nối được Ollama. Hãy chạy `ollama serve`.' });
  assert.equal(infraErrorView(o).type, 'ollama');
  assert.equal(infraErrorView(new ApiError('offline', 'x')).type, 'offline');
  assert.equal(infraErrorView(new ApiError('timeout', 'x')).type, 'timeout');
  assert.equal(infraErrorView(new ApiError('client', 'x', { status: 400 })), null);
  assert.equal(infraErrorView(new Error('Không có câu hỏi')), null);
});
