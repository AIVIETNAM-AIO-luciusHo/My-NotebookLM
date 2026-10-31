// Ánh xạ ApiError -> nội dung trạng thái lỗi riêng (U5). Thuần, test được.
// ctx: 'upload' | 'chat' | 'other'
export const errorView = (err, ctx = 'other') => {
  if (err?.kind === 'offline') {
    return { type: 'offline', title: 'Backend đang tắt', message: 'Không kết nối được máy chủ. Hãy chạy backend rồi thử lại.' };
  }
  if (err?.kind === 'timeout') {
    return { type: 'timeout', title: 'Máy chủ phản hồi quá lâu', message: err.message };
  }
  if (err?.ollama) {
    if (err.ollamaKind === 'model') {
      return { type: 'ollama', title: 'Mô hình chưa được tải', message: 'Mô hình chưa được tải. Chạy `ollama pull llama3.2` rồi thử lại.' };
    }
    if (err.ollamaKind === 'timeout') {
      return { type: 'ollama', title: 'Ollama phản hồi quá lâu', message: 'Ollama phản hồi quá lâu. Mô hình có thể đang khởi động hoặc máy đang bận; hãy thử lại sau ít phút.' };
    }
    return { type: 'ollama', title: 'Ollama chưa sẵn sàng', message: 'Không kết nối được Ollama. Hãy chạy `ollama serve` rồi thử lại.' };
  }
  if (ctx === 'upload' && err?.uploadReason === 'notpdf') {
    return { type: 'notpdf', title: 'Không phải tệp PDF', message: 'Chỉ nhận tệp PDF. Hãy chọn một tệp có đuôi .pdf.' };
  }
  if (ctx === 'upload' && err?.uploadReason === 'encrypted') {
    return { type: 'encrypted', title: 'PDF có mật khẩu', message: 'PDF có mật khẩu, hãy gỡ mật khẩu rồi tải lại.' };
  }
  if (ctx === 'upload' && (err?.status === 500 || err?.status === 422 || err?.status === 400)) {
    return { type: 'badpdf', title: 'Không đọc được PDF này', message: 'Tệp có thể bị hỏng hoặc không có văn bản. Hãy thử tệp khác.' };
  }
  return { type: 'generic', title: 'Có lỗi xảy ra', message: err?.message || 'Lỗi không xác định.' };
};

// Lỗi hạ tầng (backend tắt, quá lâu, Ollama) -> khung riêng; lỗi khác -> null để giữ thông điệp thường.
export const infraErrorView = (err) =>
  err?.kind === 'offline' || err?.kind === 'timeout' || err?.ollama ? errorView(err) : null;

// Không biết danh sách tệp (backend lỗi/tắt) thì không được nói "chưa có tệp nào".
export const filesUnknownView = () => ({
  type: 'filesUnknown',
  title: 'Không tải được danh sách tệp',
  message: 'Chưa kết nối được backend nên chưa biết workspace có tệp nào. Hãy thử lại sau.',
});

export const emptyWorkspaceView = () => ({
  type: 'empty',
  title: 'Chưa có tệp nào',
  message: 'Hãy nạp một tệp PDF ở cột Nguồn để bắt đầu hỏi đáp.',
});
