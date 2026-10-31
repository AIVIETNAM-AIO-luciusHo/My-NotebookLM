import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  pickUnfinished, shouldPoll, canResume, statusLabel, errorWarning, progressText, graphProgress, resumeErrorMessage, needsReupload, isWarmingUp,
} from '../../src/utils/jobs.js';

const J = (status, extra = {}) => ({ job_id: status, status, chunks_total: 10, chunks_done: 3, error: null, ...extra });

test('pickUnfinished chọn đúng 4 trạng thái chưa xong', () => {
  const all = ['queued', 'fast_running', 'fast_done', 'graph_running', 'done', 'failed', 'interrupted'].map((s) => J(s));
  assert.deepEqual(pickUnfinished(all).map((j) => j.status), ['queued', 'fast_running', 'fast_done', 'graph_running']);
  assert.deepEqual(pickUnfinished(null), []);
});

test('shouldPoll dừng khi hết job chưa xong', () => {
  assert.equal(shouldPoll([J('done'), J('graph_running')]), true);
  assert.equal(shouldPoll([J('done'), J('failed'), J('interrupted')]), false);
  assert.equal(shouldPoll([]), false);
});

test('canResume chỉ với failed/interrupted', () => {
  assert.equal(canResume(J('failed')), true);
  assert.equal(canResume(J('interrupted')), true);
  for (const s of ['queued', 'fast_running', 'fast_done', 'graph_running', 'done']) assert.equal(canResume(J(s)), false);
});

test('statusLabel tiếng Việt cho mọi trạng thái, có nhãn dự phòng', () => {
  assert.equal(statusLabel('graph_running'), 'Đang dựng đồ thị tri thức');
  assert.equal(statusLabel('done'), 'Hoàn tất');
  assert.equal(statusLabel('xyz'), 'Không rõ trạng thái');
});

test('errorWarning rút "k/n đoạn lỗi" từ thông điệp backend', () => {
  assert.equal(errorWarning(J('done', { error: 'Cảnh báo: 2/40 đoạn trích triplet lỗi (đã bỏ qua).' })), '2/40 đoạn lỗi');
  assert.match(errorWarning(J('failed', { error: 'Không kết nối được Ollama: 5/5 đoạn lỗi. Kiểm tra x.' })), /^Không kết nối được Ollama \(5\/5 đoạn lỗi\)/);
  assert.equal(errorWarning(J('failed', { error: 'Khác' })), 'Khác');
  assert.equal(errorWarning(J('done')), null);
});

test('progressText và graphProgress', () => {
  assert.equal(progressText(J('graph_running')), '3/10 đoạn');
  assert.equal(progressText({ status: 'queued', chunks_total: 0 }), '');
  assert.deepEqual(graphProgress([J('done'), J('graph_running')]), { done: 3, total: 10, text: '3/10 đoạn' });
  assert.equal(graphProgress([J('done')]), null);
});

test('resumeErrorMessage xử lý 409', () => {
  assert.match(resumeErrorMessage({ status: 409, message: 'Pha nhanh chưa hoàn tất' }), /^Không thể tiếp tục: hãy tải lại tệp/);
  assert.equal(resumeErrorMessage({ status: 500, message: 'x' }), 'x');
});

test('job failed ở pha nhanh (chunks_total=0): không resume, cần tải lại', () => {
  const fast = J('failed', { chunks_total: 0, error: 'PdfStreamError: Stream has ended' });
  assert.equal(canResume(fast), false);
  assert.equal(needsReupload(fast), true);
  assert.equal(errorWarning(fast), 'PDF không đọc được');
  assert.equal(needsReupload(J('failed')), false);
  assert.equal(needsReupload(J('done', { chunks_total: 0 })), false);
});

test('isWarmingUp chỉ khi graph_running và chưa xong đoạn nào', () => {
  assert.equal(isWarmingUp(J('graph_running', { chunks_done: 0 })), true);
  assert.equal(isWarmingUp(J('graph_running', { chunks_done: 1 })), false);
  assert.equal(isWarmingUp(J('queued', { chunks_done: 0 })), false);
});

test('resumeErrorMessage dịch 409 tiếng Anh/pha nhanh sang tiếng Việt', () => {
  assert.equal(resumeErrorMessage({ status: 409, detail: "Job is 'done', not resumable.", message: 'x' }), 'Không thể tiếp tục: tác vụ không ở trạng thái có thể tiếp tục.');
  assert.equal(resumeErrorMessage({ status: 409, detail: 'Pha nhanh chưa hoàn tất; hãy upload lại tệp.', message: 'x' }), 'Không thể tiếp tục: hãy tải lại tệp.');
});

test('T2: job.error lạ "Loại: thông điệp" hiện tiếng Việt; lỗi đã biết giữ nguyên', () => {
  assert.equal(errorWarning(J('failed', { error: 'RuntimeError: boom at /x/y.py' })), 'Dựng đồ thị gặp lỗi');
  assert.equal(errorWarning(J('failed', { error: 'ValueError: x' })), 'Dựng đồ thị gặp lỗi');
  assert.equal(errorWarning(J('failed', { error: 'Cảnh báo: 2/40 đoạn trích triplet lỗi' })), '2/40 đoạn lỗi');
  assert.equal(errorWarning(J('failed', { error: 'PDF không đọc được hoặc bị hỏng.', chunks_total: 0 })), 'PDF không đọc được');
});

import { canDelete, deleteErrorMessage } from '../../src/utils/jobs.js';

test('P1.7 canDelete chỉ với done|failed|interrupted; job còn chạy thì không', () => {
  for (const s of ['done', 'failed', 'interrupted']) assert.equal(canDelete(J(s)), true, s);
  for (const s of ['queued', 'fast_running', 'fast_done', 'graph_running']) assert.equal(canDelete(J(s)), false, s);
  assert.equal(canDelete(null), false);
});

test('P1.7 deleteErrorMessage tiếng Việt cho 409/404', () => {
  assert.match(deleteErrorMessage({ status: 409 }), /đang chạy/);
  assert.match(deleteErrorMessage({ status: 404 }), /không còn tồn tại/);
});

test('P1.7 errorWarning: job PDF có mật khẩu khác job PDF hỏng', () => {
  const enc = J('failed', { chunks_total: 0, error: 'PDF có mật khẩu, hãy gỡ mật khẩu rồi tải lại.' });
  const bad = J('failed', { chunks_total: 0, error: 'PDF không đọc được hoặc bị hỏng.' });
  assert.equal(errorWarning(enc), 'PDF có mật khẩu');
  assert.equal(errorWarning(bad), 'PDF không đọc được');
});

test('errorWarning (L4) nêu nguyên nhân Ollama của job failed', () => {
  const e = 'Không kết nối được Ollama: 5/5 đoạn lỗi. Kiểm tra `ollama serve` rồi POST /jobs/x/resume.';
  const w = errorWarning(J('failed', { error: e }));
  assert.match(w, /Không kết nối được Ollama \(5\/5 đoạn lỗi\)/);
  assert.match(w, /ollama serve/);
  assert.equal(errorWarning(J('failed', { error: 'Quá nhiều đoạn lỗi khi trích triplet: 4/6 đoạn lỗi. x' })), 'Quá nhiều đoạn lỗi khi trích triplet');
  assert.equal(errorWarning(J('done', { error: 'Cảnh báo: 1/6 đoạn trích triplet lỗi (đã bỏ qua).' })), '1/6 đoạn lỗi');
});
