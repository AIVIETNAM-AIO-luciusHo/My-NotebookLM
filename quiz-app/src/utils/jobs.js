// Logic thuần cho danh sách job nạp tài liệu (không phụ thuộc React/DOM).
const UNFINISHED = ['queued', 'fast_running', 'fast_done', 'graph_running'];
const RESUMABLE = ['failed', 'interrupted'];
const TERMINAL = ['done', 'failed', 'interrupted'];

const LABELS = {
  queued: 'Đang xếp hàng',
  fast_running: 'Đang đọc và lập chỉ mục',
  fast_done: 'Đã lập chỉ mục, chờ dựng đồ thị',
  graph_running: 'Đang dựng đồ thị tri thức',
  done: 'Hoàn tất',
  failed: 'Thất bại',
  interrupted: 'Bị gián đoạn',
};

export const statusLabel = (status) => LABELS[status] ?? 'Không rõ trạng thái';

export const isUnfinished = (job) => UNFINISHED.includes(job?.status);

export const pickUnfinished = (jobs) => (Array.isArray(jobs) ? jobs.filter(isUnfinished) : []);

// Chỉ poll khi còn job chưa ở done|failed|interrupted.
export const shouldPoll = (jobs) => pickUnfinished(jobs).length > 0;

// Nút "Xoá" chỉ với job ở trạng thái cuối (khớp DELETE /jobs/{id}: 409 nếu còn chạy).
export const canDelete = (job) => TERMINAL.includes(job?.status);

// Nút "Tiếp tục" chỉ với failed|interrupted (khớp POST /jobs/{id}/resume).
export const canResume = (job) => RESUMABLE.includes(job?.status) && (job?.chunks_total ?? 0) > 0;

// chunks_total chỉ được ghi sau pha nhanh (cùng lúc lưu chunk_ids). Job failed/interrupted
// mà chunks_total=0 nghĩa là pha nhanh chưa xong: backend luôn trả 409 cho resume.
export const needsReupload = (job) => RESUMABLE.includes(job?.status) && !((job?.chunks_total ?? 0) > 0);

// Job đang chạy đồ thị nhưng chưa xong đoạn nào: lượt LLM đầu thường rất chậm.
export const isWarmingUp = (job) => job?.status === 'graph_running' && (job?.chunks_done ?? 0) === 0;

export const progressText = (job) => {
  const total = job?.chunks_total ?? 0;
  return total > 0 ? `${job.chunks_done ?? 0}/${total} đoạn` : '';
};

// Cảnh báo "k/n đoạn lỗi" nếu `error` của backend mang nội dung đó; ngược lại trả
// nguyên văn `error` (lỗi khác) hoặc null.
export const errorWarning = (job) => {
  const err = job?.error;
  if (!err) return null;
  if (needsReupload(job)) return /mật khẩu/i.test(err) ? 'PDF có mật khẩu' : 'PDF không đọc được';
  // Nguyên nhân do Ollama (backend ghi "Không kết nối được Ollama: k/n đoạn lỗi", "Quá nhiều đoạn lỗi ...").
  if (/Không kết nối được Ollama/i.test(err)) {
    const k = /(\d+\/\d+)\s*đoạn/.exec(err);
    return `Không kết nối được Ollama${k ? ` (${k[1]} đoạn lỗi)` : ''}. Hãy chạy ollama serve rồi bấm Tiếp tục`;
  }
  if (/Quá nhiều đoạn lỗi/i.test(err)) return 'Quá nhiều đoạn lỗi khi trích triplet';
  const m = /(\d+)\/(\d+)\s*đoạn[^.]*lỗi/.exec(err);
  if (m) return `${m[1]}/${m[2]} đoạn lỗi`;
  // Lỗi lạ dạng "TênLoại: thông điệp" (tiếng Anh, từ _fast_phase/worker): ẩn chi tiết, UI giữ bản gốc ở title.
  return /^[A-Za-z_][\w.]*: /.test(err) ? 'Dựng đồ thị gặp lỗi' : err;
};

// Tiến độ đồ thị cho thanh trên: job chưa xong đang dựng, hoặc null.
export const graphProgress = (jobs) => {
  const j = pickUnfinished(jobs).find((x) => (x.chunks_total ?? 0) > 0) ?? pickUnfinished(jobs)[0];
  return j ? { done: j.chunks_done ?? 0, total: j.chunks_total ?? 0, text: progressText(j) } : null;
};

// Thông báo tiếng Việt cho lỗi 409 của resume.
export const resumeErrorMessage = (err) => {
  if (err?.status !== 409) return err?.message ?? 'Không thể tiếp tục tác vụ.';
  const d = err.detail ?? err.message ?? '';
  if (/Pha nhanh/i.test(d)) return 'Không thể tiếp tục: hãy tải lại tệp.';
  return `Không thể tiếp tục: ${/not resumable/i.test(d) ? 'tác vụ không ở trạng thái có thể tiếp tục.' : err.message}`;
};

// Thông báo tiếng Việt cho lỗi của DELETE /jobs/{id}.
export const deleteErrorMessage = (err) => {
  if (err?.status === 409) return 'Không xoá được: tác vụ đang chạy.';
  if (err?.status === 404) return 'Tác vụ không còn tồn tại.';
  return err?.message ?? 'Không xoá được tác vụ.';
};
