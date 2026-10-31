import { useTheme } from '../../contexts/useTheme';

// Trạng thái rỗng/lỗi dùng chung: tiêu đề, mô tả, nút thử lại tuỳ chọn.
const StatePanel = ({ view, onRetry, compact = false }) => {
  const { isDarkMode, classes } = useTheme();
  const tone = view.type === 'empty'
    ? (isDarkMode ? 'border-gray-700' : 'border-gray-200')
    : (isDarkMode ? 'border-red-800 bg-red-900/20' : 'border-red-200 bg-red-50');
  return (
    <div role={view.type === 'empty' ? 'status' : 'alert'} data-state={view.type}
      className={`rounded-xl border ${tone} ${compact ? 'p-3' : 'p-5'} text-center`}>
      <p className={`text-sm font-semibold ${classes.textColor}`}>{view.title}</p>
      <p className={`text-xs mt-1 ${classes.mutedText}`}>{view.message}</p>
      {onRetry && (
        <button onClick={onRetry}
          className="mt-3 text-xs font-medium px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700">
          Thử lại
        </button>
      )}
    </div>
  );
};

export default StatePanel;
