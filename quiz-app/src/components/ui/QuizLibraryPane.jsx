import { useState } from 'react';
import { useTheme } from '../../contexts/useTheme';
import { useBodyScrollLock } from '../../hooks/useBodyScrollLock';
import { getAttempts } from '../../utils/history';
import { formatTimestamp } from '../../utils/utils';
import IconButton from './IconButton';
import { IconClose, IconStar, IconTrash, IconHistory, IconShare } from './icons';

// Slide-over panel listing the user's saved quizzes. Presentational: the parent
// owns the entries and persistence, this only fires callbacks. Entries arrive
// pre-sorted (bookmarked first, newest first). `historyMap` lets each entry
// surface a "Results history" link when that quiz has past attempts; selecting
// it calls onOpenHistory without closing this pane (the history pane stacks on top).
const QuizLibraryPane = ({ entries, historyMap = {}, onSelect, onToggleBookmark, onRemove, onOpenHistory, onShare, onClose }) => {
  const { isDarkMode, classes } = useTheme();
  // Two-step delete so a stray tap can't wipe a saved quiz.
  const [confirmRemoveId, setConfirmRemoveId] = useState(null);
  // Play the exit animation, then run the real action (select/close) which
  // unmounts the pane. Duration matches the slideOutRight/fadeOut timings.
  const [closing, setClosing] = useState(false);
  const close = (action) => {
    if (closing) return;
    setClosing(true);
    setTimeout(action, 250);
  };

  // Lock background scroll while the pane is open (reference-counted so it
  // composes with a history pane stacked on top).
  useBodyScrollLock();

  return (
    <div className="fixed inset-0 z-50 flex">
      <div
        className={`flex-1 bg-black/40 ${closing ? 'animate-fadeOut' : 'animate-fadeIn'}`}
        onClick={() => close(onClose)}
        aria-hidden="true"
      />
      <div className={`${classes.cardBg} w-full max-w-md h-full overflow-y-auto shadow-2xl p-6 ${closing ? 'animate-slideOutRight' : 'animate-slideInRight'}`}>
        <div className="flex items-center justify-between mb-2">
          <h2 className={`text-2xl font-bold ${classes.textColor}`}>Quiz đã lưu của bạn</h2>
          <button
            type="button"
            onClick={() => close(onClose)}
            className={`p-1.5 rounded-full transition-all ${classes.secondaryBtn}`}
            aria-label="Đóng"
            title="Đóng"
          >
            <IconClose className="w-5 h-5" />
          </button>
        </div>
        <p className={`text-sm ${classes.mutedText} mb-5`}>
          Chọn một bài quiz để nạp, rồi cấu hình và bắt đầu ở trang tải lên.
        </p>

        {entries.length === 0 ? (
          <p className={classes.mutedText}>Chưa có quiz nào được lưu.</p>
        ) : (
          <ul className="space-y-3">
            {entries.map((e, idx) => {
              const attemptCount = getAttempts(historyMap, e.id).length;
              return (
              <li key={e.isSample ? `sample-${e.id}` : `${e.id}-${idx}`} className={`${classes.innerBg} rounded-xl p-4`}>
                <div className="flex items-start gap-3">
                  <button
                    type="button"
                    onClick={() => close(() => onSelect(e))}
                    className="flex-1 text-left min-w-0"
                    title="Nạp bài quiz này"
                  >
                    <p className={`font-semibold ${classes.textColor} break-words`}>{e.name}</p>
                    <p className={`text-sm ${classes.mutedText}`}>{e.questionCount} câu hỏi</p>
                    <p className={`text-xs ${classes.mutedText} mt-1`}>
                      {e.isSample ? 'Quiz mẫu có sẵn, luôn dùng thử được' : formatTimestamp(e.uploadedAt)}
                    </p>
                  </button>

                  <div className="flex items-center gap-1 flex-shrink-0">
                    {e.isSample ? (
                      // The sample is always present and not stored, so it can't
                      // be bookmarked or removed.
                      <span className={`text-xs px-2 py-1 rounded-full ${isDarkMode ? 'bg-indigo-900 text-indigo-300' : 'bg-indigo-100 text-indigo-700'}`}>
                        Mẫu
                      </span>
                    ) : (
                      <>
                        {onShare && (
                          <IconButton tone="emerald" onClick={() => onShare(e)} aria-label="Chia sẻ" title="Chia sẻ bằng liên kết">
                            <IconShare className="w-5 h-5" />
                          </IconButton>
                        )}
                        <button
                          type="button"
                          onClick={() => onToggleBookmark(e.id)}
                          className={`p-1.5 rounded-full transition-colors ${
                            e.bookmarked
                              ? 'text-yellow-400'
                              : `${classes.mutedText} hover:text-yellow-400`
                          }`}
                          aria-label={e.bookmarked ? 'Bỏ đánh dấu' : 'Đánh dấu'}
                          title={e.bookmarked ? 'Bỏ đánh dấu' : 'Đánh dấu lên đầu'}
                        >
                          <IconStar className="w-5 h-5" fill={e.bookmarked ? 'currentColor' : 'none'} />
                        </button>
                        <IconButton tone="red" onClick={() => setConfirmRemoveId(e.id)} aria-label="Xoá" title="Xoá khỏi thư viện">
                          <IconTrash className="w-5 h-5" />
                        </IconButton>
                      </>
                    )}
                  </div>
                </div>

                {attemptCount > 0 && onOpenHistory && (
                  <button
                    type="button"
                    onClick={() => onOpenHistory(e)}
                    className={`mt-2 inline-flex items-center gap-1.5 text-sm font-medium ${
                      isDarkMode ? 'text-indigo-400 hover:text-indigo-300' : 'text-indigo-600 hover:text-indigo-800'
                    } hover:underline`}
                    title="Xem các lần làm trước của bài quiz này"
                  >
                    <IconHistory className="w-4 h-4" />
                    Lịch sử kết quả
                    <span className={classes.mutedText}>({attemptCount})</span>
                  </button>
                )}

                {confirmRemoveId === e.id && (
                  <div className="mt-3 flex items-center gap-2">
                    <span className={`text-sm ${classes.mutedText}`}>Xoá bài quiz này?</span>
                    <button
                      type="button"
                      onClick={() => {
                        onRemove(e.id);
                        setConfirmRemoveId(null);
                      }}
                      className="px-3 py-1 rounded-md text-sm font-medium bg-red-600 text-white hover:bg-red-700 transition-colors"
                    >
                      Xoá
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmRemoveId(null)}
                      className={`px-3 py-1 rounded-md text-sm font-medium ${classes.secondaryBtn} transition-colors`}
                    >
                      Huỷ
                    </button>
                  </div>
                )}
              </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
};

export default QuizLibraryPane;
