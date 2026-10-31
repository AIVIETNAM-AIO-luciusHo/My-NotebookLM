import OptionEditor from './OptionEditor';
import { useTheme } from '../../contexts/useTheme';

const QuestionEditor = ({ question, index, onChange, onRemove, canRemove }) => {
  const { isDarkMode, classes } = useTheme();

  // QuestionEditor cards sit inside QuizCreatorPage's card, so we need a
  // contrasting background — innerBg flips to the lighter of the two.
  const cardBg = isDarkMode ? 'bg-gray-700' : 'bg-gray-50';
  const inputBg = isDarkMode
    ? 'bg-gray-800 border-gray-600 text-white placeholder-gray-500'
    : 'bg-white border-gray-300 text-gray-800 placeholder-gray-400';

  const updateField = (field, value) => onChange({ ...question, [field]: value });

  const updateOption = (optIdx, updatedOption) => {
    const newOptions = question.options.map((o, i) => (i === optIdx ? updatedOption : o));
    onChange({ ...question, options: newOptions });
  };

  const addOption = () => {
    onChange({
      ...question,
      options: [...question.options, { text: '', isCorrect: false }],
    });
  };

  const removeOption = (optIdx) => {
    if (question.options.length <= 2) return;
    onChange({ ...question, options: question.options.filter((_, i) => i !== optIdx) });
  };

  // Single-choice radio behavior: marking one option correct must unmark the
  // rest. Lives at the parent level since OptionEditor only sees itself.
  const selectSingleCorrect = (optIdx) => {
    onChange({
      ...question,
      options: question.options.map((o, i) => ({ ...o, isCorrect: i === optIdx })),
    });
  };

  const setType = (type) => {
    if (type === question.type) return;
    let newOptions = question.options;
    // Switching multi → single keeps only the first marked-correct option to
    // avoid an "invalid" state where multiple options stay flagged.
    if (type === 'single') {
      let kept = false;
      newOptions = question.options.map((o) => {
        if (o.isCorrect && !kept) {
          kept = true;
          return o;
        }
        return { ...o, isCorrect: false };
      });
    }
    onChange({ ...question, type, options: newOptions });
  };

  const typeButton = (value, label) => {
    const active = question.type === value;
    return (
      <button
        type="button"
        onClick={() => setType(value)}
        className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
          active ? 'bg-indigo-600 text-white' : classes.secondaryBtn
        }`}
      >
        {label}
      </button>
    );
  };

  return (
    <div className={`${cardBg} rounded-xl p-5 space-y-4 animate-fadeInUp`}>
      <div className="flex items-start justify-between gap-3">
        <h3 className={`text-lg font-bold ${classes.textColor}`}>Câu hỏi {index + 1}</h3>
        {canRemove && (
          <button
            type="button"
            onClick={onRemove}
            className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
              isDarkMode
                ? 'bg-red-900/40 text-red-300 hover:bg-red-900/60'
                : 'bg-red-100 text-red-700 hover:bg-red-200'
            }`}
            title="Xoá câu hỏi"
          >
            Xoá
          </button>
        )}
      </div>

      <div>
        <label className={`block text-sm font-medium ${classes.mutedText} mb-1`}>
          Nội dung câu hỏi
        </label>
        <textarea
          value={question.question}
          onChange={(e) => updateField('question', e.target.value)}
          rows={2}
          className={`w-full px-3 py-2 border-2 ${inputBg} rounded-lg focus:outline-none focus:border-indigo-500 resize-y`}
          placeholder="Nhập câu hỏi…"
        />
      </div>

      <div>
        <label className={`block text-sm font-medium ${classes.mutedText} mb-2`}>Kiểu đáp án</label>
        <div className="flex flex-wrap gap-2">
          {typeButton('single', 'Một đáp án')}
          {typeButton('multi', 'Nhiều đáp án')}
        </div>
      </div>

      <div>
        <label className={`block text-sm font-medium ${classes.mutedText} mb-2`}>
          Các lựa chọn{' '}
          <span className="font-normal">
            ({question.type === 'single'
              ? 'chọn một đáp án đúng'
              : 'chọn tất cả đáp án đúng'})
          </span>
        </label>
        <div className="space-y-2">
          {question.options.map((option, optIdx) => (
            <OptionEditor
              key={optIdx}
              option={option}
              index={optIdx}
              questionIndex={index}
              type={question.type}
              onChange={(updated) => updateOption(optIdx, updated)}
              onRemove={() => removeOption(optIdx)}
              onSelectSingle={() => selectSingleCorrect(optIdx)}
              canRemove={question.options.length > 2}
            />
          ))}
        </div>
        <button
          type="button"
          onClick={addOption}
          className={`mt-3 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            isDarkMode
              ? 'bg-indigo-900/40 text-indigo-200 hover:bg-indigo-900/60'
              : 'bg-indigo-100 text-indigo-700 hover:bg-indigo-200'
          }`}
        >
          Thêm đáp án
        </button>
      </div>

      <div>
        <label className={`block text-sm font-medium ${classes.mutedText} mb-1`}>
          Giải thích <span className="font-normal">(tuỳ chọn)</span>
        </label>
        <textarea
          value={question.explanation}
          onChange={(e) => updateField('explanation', e.target.value)}
          rows={2}
          className={`w-full px-3 py-2 border-2 ${inputBg} rounded-lg focus:outline-none focus:border-indigo-500 resize-y`}
          placeholder="Hiện cho người làm sau khi trả lời…"
        />
      </div>

      <label className="flex items-center gap-2 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={question.noShuffleOptions}
          onChange={(e) => updateField('noShuffleOptions', e.target.checked)}
          className="w-4 h-4 accent-indigo-600"
        />
        <span className={`text-sm ${classes.mutedText}`}>
          Không xáo trộn lựa chọn của câu này (đặt <code>shuffle: 0</code>)
        </span>
      </label>
    </div>
  );
};

export default QuestionEditor;
