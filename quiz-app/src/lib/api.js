// Lớp gọi API duy nhất tới backend FastAPI. Mọi lỗi được chuẩn hoá thành ApiError
// với thông điệp tiếng Việt; component chỉ cần hiển thị `err.message`.

const DEFAULT_BASE = 'http://127.0.0.1:8000';
// LLM cục bộ chậm (đo thật: /chat tới 51 s), nên các lệnh sinh nội dung có hạn dài.
export const T_FAST = 15000;
export const T_UPLOAD = 180000;
export const T_LLM = 300000;

export class ApiError extends Error {
  // kind: 'offline' | 'timeout' | 'client' | 'server' | 'parse'
  constructor(kind, message, { status = 0, detail = '' } = {}) {
    super(message);
    this.name = 'ApiError';
    this.kind = kind;
    this.status = status;
    this.detail = detail;
    // Backend trả 503 cho Ollama không kết nối được; regex hẹp chỉ là dự phòng cho bản backend cũ (500).
    this.ollama = status === 503 || status === 504 || /Không kết nối được Ollama|Cannot reach Ollama/i.test(detail);
    // Phân loại lỗi Ollama theo mã (504 = quá lâu) và câu chữ tiếng Việt của backend (503 = chưa tải mô hình / không kết nối).
    this.ollamaKind = !this.ollama ? '' : status === 504 ? 'timeout' : /ollama pull|chưa được tải/i.test(detail) ? 'model' : 'connect';
    // Lỗi upload 400 có chữ riêng của backend: tệp không phải PDF / PDF có mật khẩu.
    this.uploadReason = status === 400 ? (/Chỉ nhận tệp PDF|Only PDF/i.test(detail) ? 'notpdf' : /có mật khẩu/i.test(detail) ? 'encrypted' : '') : '';
  }
}

// Dịch các `detail` tiếng Anh đã biết của backend; chi tiết gốc vẫn giữ ở `err.detail`.
const VI_DETAILS = [
  [/No extractable text/i, 'Không tìm thấy văn bản trong PDF này.'],
  [/Workspace is empty/i, 'Chưa có tệp nào trong workspace. Hãy nạp PDF trước.'],
  [/Only PDF files/i, 'Chỉ nhận tệp PDF.'],
  [/Job not found/i, 'Không tìm thấy tác vụ.'],
  [/đang chạy, chưa xoá/i, 'Tác vụ đang chạy, chưa xoá được.'],
  [/not resumable/i, 'Tác vụ không ở trạng thái có thể tiếp tục.'],
  [/invalid JSON|missing valid|Question \d+/i, 'Mô hình trả về dữ liệu không hợp lệ. Hãy thử lại hoặc đổi chủ đề.'],
  [/Could not read the workspace store|indexing failed/i, 'Không đọc/ghi được kho dữ liệu của workspace.'],
];
export const viDetail = (d) => (VI_DETAILS.find(([re]) => re.test(d)) ?? [])[1] ?? d;

export const normalizeBase = (url) => String(url || DEFAULT_BASE).replace(/\/+$/, '');

// FastAPI trả `detail` là chuỗi, hoặc mảng lỗi kiểm tra (422).
const detailText = (body) => {
  const d = body && body.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) return d.map((x) => x && x.msg).filter(Boolean).join('; ');
  return '';
};

export const createApi = ({ baseUrl, fetchImpl, timeoutMs } = {}) => {
  const base = normalizeBase(baseUrl);
  const doFetch = fetchImpl || ((...a) => globalThis.fetch(...a));

  const request = async (path, { method = 'GET', json, body, timeout } = {}) => {
    const limit = timeout ?? timeoutMs ?? T_FAST;
    const ctrl = new AbortController();
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; ctrl.abort(); }, limit);
    const init = { method, signal: ctrl.signal };
    if (json !== undefined) {
      init.headers = { 'Content-Type': 'application/json' };
      init.body = JSON.stringify(json);
    } else if (body !== undefined) {
      init.body = body;
    }
    try {
      let res;
      try {
        res = await doFetch(`${base}${path}`, init);
      } catch (e) {
        if (timedOut) {
          throw new ApiError('timeout', `Máy chủ phản hồi quá lâu (quá ${Math.round(limit / 1000)} giây). Hãy thử lại.`);
        }
        if (e && e.name === 'AbortError') throw e;
        throw new ApiError('offline', 'Không kết nối được máy chủ. Hãy kiểm tra backend đã chạy rồi thử lại.');
      }
      let data = null;
      try { data = await res.json(); } catch { /* thân rỗng hoặc không phải JSON */ }
      if (!res.ok) {
        const detail = detailText(data);
        if (res.status >= 500) {
          throw new ApiError('server', `Máy chủ gặp lỗi (mã ${res.status})${detail ? `: ${viDetail(detail)}` : '.'}`, { status: res.status, detail });
        }
        throw new ApiError('client', (detail && viDetail(detail)) || `Yêu cầu không hợp lệ (mã ${res.status}).`, { status: res.status, detail });
      }
      if (data === null) throw new ApiError('parse', 'Máy chủ trả dữ liệu không đọc được.', { status: res.status });
      return data;
    } finally {
      clearTimeout(timer);
    }
  };

  return {
    base,
    health: () => request('/health'),
    files: () => request('/files'),
    upload: (file) => {
      const form = new FormData();
      form.append('file', file);
      return request('/upload', { method: 'POST', body: form, timeout: T_UPLOAD });
    },
    jobs: () => request('/jobs'),
    deleteJob: (id) => request(`/jobs/${encodeURIComponent(id)}`, { method: 'DELETE' }),
    resumeJob: (id) => request(`/jobs/${encodeURIComponent(id)}/resume`, { method: 'POST' }),
    chat: (query) => request('/chat', { method: 'POST', json: { query }, timeout: T_LLM }),
    generateQuiz: (payload) => request('/generate-quiz', { method: 'POST', json: payload, timeout: T_LLM }),
    generateMindmap: (topic) => request('/generate-mindmap', { method: 'POST', json: { topic }, timeout: T_LLM }),
  };
};

export const api = createApi({ baseUrl: import.meta.env?.VITE_BACKEND });
export const BACKEND = api.base;
