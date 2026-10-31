import { test } from 'node:test';
import assert from 'node:assert/strict';
import { formatSource, graphNotice, scoreTone, sourcesSummary, GRAPH_NOT_READY_NOTICE } from '../../src/utils/sourcesFormat.js';
import { errorView } from '../../src/utils/errorView.js';

test('formatSource: tên tệp, trang (1-based) và điểm cosine', () => {
  const s = formatSource({ text: 't', cosine_score: 0.8951, source: 'a.pdf', page: 3 });
  assert.deepEqual([s.file, s.pageLabel, s.scoreLabel, s.tone], ['a.pdf', 'trang 3', '0.895', 'high']);
});

test('formatSource: thiếu trang/điểm không vỡ', () => {
  const s = formatSource({ text: 't', source: 'a.pdf' });
  assert.equal(s.pageLabel, '');
  assert.equal(s.scoreLabel, '—');
  assert.equal(formatSource({}).file, 'Không rõ tệp');
});

test('scoreTone theo ngưỡng 0.85 / 0.70', () => {
  assert.deepEqual([0.9, 0.85, 0.7, 0.69].map(scoreTone), ['high', 'high', 'mid', 'low']);
});

test('graphNotice chỉ khi graph_ready === false', () => {
  assert.equal(graphNotice(false), GRAPH_NOT_READY_NOTICE);
  assert.match(GRAPH_NOT_READY_NOTICE, /chưa dựng xong/);
  assert.equal(graphNotice(true), null);
  assert.equal(graphNotice(undefined), null);
});

test('sourcesSummary đếm nguồn', () => assert.equal(sourcesSummary([1, 2]), '2 nguồn trích dẫn'));

test('errorView phân biệt backend tắt, Ollama, PDF hỏng, chung', () => {
  assert.equal(errorView({ kind: 'offline' }).type, 'offline');
  assert.equal(errorView({ kind: 'server', ollama: true, status: 500 }, 'chat').type, 'ollama');
  assert.equal(errorView({ kind: 'server', status: 500 }, 'upload').type, 'badpdf');
  assert.equal(errorView({ kind: 'client', status: 422 }, 'upload').type, 'badpdf');
  assert.equal(errorView({ kind: 'server', status: 500, message: 'm' }, 'chat').type, 'generic');
});

test('T5: filesUnknownView không nói "Chưa có tệp nào"', async () => {
  const { filesUnknownView } = await import('../../src/utils/errorView.js');
  const v = filesUnknownView();
  assert.equal(v.title, 'Không tải được danh sách tệp');
  assert.doesNotMatch(JSON.stringify(v), /Chưa có tệp/);
});

test('formatSource: cosine_score null hiển thị — chứ không phải 0.000', () => {
  const f = formatSource({ source: 'a.pdf', cosine_score: null, text: 'x' });
  assert.equal(f.scoreLabel, '—');
});
