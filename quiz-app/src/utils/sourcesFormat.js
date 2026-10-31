// Định dạng nguồn trích dẫn và cờ đồ thị của /chat (thuần, test được).
export const GRAPH_NOT_READY_NOTICE =
  'Đồ thị tri thức chưa dựng xong, câu trả lời chỉ dùng vector.';

// Chỉ khi backend nói rõ graph_ready === false (thiếu trường = không cảnh báo).
export const graphNotice = (graphReady) => (graphReady === false ? GRAPH_NOT_READY_NOTICE : null);

export const scoreTone = (score) => (score >= 0.85 ? 'high' : score >= 0.7 ? 'mid' : 'low');

export const formatSource = (src) => {
  const score = src?.cosine_score == null ? NaN : Number(src.cosine_score);
  const page = Number.isInteger(src?.page) && src.page > 0 ? src.page : null;
  return {
    file: src?.source || 'Không rõ tệp',
    pageLabel: page ? `trang ${page}` : '',
    scoreLabel: Number.isFinite(score) ? score.toFixed(3) : '—',
    tone: Number.isFinite(score) ? scoreTone(score) : 'low',
    text: src?.text ?? '',
  };
};

export const sourcesSummary = (sources) =>
  `${sources.length} nguồn trích dẫn`;
