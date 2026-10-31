import { useEffect, useState } from 'react';
import { isMultiChoice, summarizeResults } from '../../utils/utils';
import { useTheme } from '../../contexts/useTheme';
import Modal from '../ui/Modal';
import Button from '../ui/Button';
import { IconEye, IconRetry, IconClose, IconChevronLeft } from '../ui/icons';

// Score change vs the previous attempt, e.g. +2.5 / -1.25, out of 10.
const formatDelta = (d) => `${d >= 0 ? '+' : ''}${parseFloat(d.toFixed(2))}`;

const ResultPage = ({
  quizData,
  answers,
  settings,
  isHistoryView,
  delta,
  onReviewAnswers,
  onRetrySameLayout,
  onRetryNewShuffle,
  onReturnBack,
  setAnswers,
  setCurrentQuestion,
  setView,
}) => {
  const { isDarkMode, classes } = useTheme();
  const [showRetryModal, setShowRetryModal] = useState(false);

  // Landing on the results should start at the top, not inherit the quiz
  // page's scroll position.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  const hasMultiChoice = quizData.questions.some(isMultiChoice);

  const { correctCount, partialCount, incorrectCount, totalQuestions, score: rawScore } =
    summarizeResults(quizData.questions, answers);
  const score = rawScore.toFixed(2);
  const showPercentage = settings.quizSizeMode === 'percentage' && settings.quizSize < 100;

  const handleRetry = () => {
    const hasShuffleActive = settings.shuffleQuestions || settings.shuffleOptions;
    if (hasShuffleActive) setShowRetryModal(true);
    else onRetrySameLayout();
  };

  // Live results "Finish" clears the run and returns to the dashboard. When
  // viewing a past attempt the same button returns to where history was opened
  // from (see onReturnBack).
  const handleFinish = () => {
    setAnswers({});
    setCurrentQuestion(0);
    setView('home');
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className={`${classes.cardBg} rounded-2xl shadow-2xl p-8 max-w-md w-full animate-fadeInUp`}>
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <div className="relative">
              <div className={`${isDarkMode ? 'bg-green-900' : 'bg-green-100'} w-24 h-24 rounded-full flex items-center justify-center`}>
                <span className={`text-4xl font-bold ${isDarkMode ? 'text-green-400' : 'text-green-600'}`}>{score}</span>
              </div>
              {delta != null && (
                <span
                  className={`absolute top-1 right-0 translate-x-1/3 -translate-y-1/4 px-2 py-0.5 rounded-full text-sm font-bold shadow ${
                    delta >= 0
                      ? isDarkMode ? 'bg-green-800 text-green-300' : 'bg-green-100 text-green-700'
                      : isDarkMode ? 'bg-red-800 text-red-300' : 'bg-red-100 text-red-700'
                  }`}
                  title="Thay đổi so với lần làm gần nhất có cùng số câu"
                >
                  {formatDelta(delta)}
                </span>
              )}
            </div>
          </div>
          <h2 className={`text-3xl font-bold ${classes.textColor} mb-2`}>
            {isHistoryView ? 'Lần làm trước' : 'Hoàn thành bài quiz!'}{showPercentage && ` (${settings.quizSize}%)`}
          </h2>
          <p className={classes.mutedText}>
            {isHistoryView ? 'Xem lại một lần làm đã lưu' : 'Đây là kết quả của bạn'}
          </p>
        </div>

        <div className="space-y-4 mb-8">
          <div className={`flex justify-between items-center p-4 ${isDarkMode ? 'bg-green-900' : 'bg-green-50'} rounded-lg`}>
            <span className={`font-medium ${classes.mutedText}`}>Câu đúng</span>
            <span className={`text-2xl font-bold ${isDarkMode ? 'text-green-400' : 'text-green-600'}`}>
              {correctCount} <span className={`text-lg font-normal ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>/{totalQuestions}</span>
            </span>
          </div>

          {hasMultiChoice && (
            <div className={`flex justify-between items-center p-4 ${isDarkMode ? 'bg-yellow-900' : 'bg-yellow-50'} rounded-lg`}>
              <span className={`font-medium ${classes.mutedText}`}>Câu đúng một phần</span>
              <span className={`text-2xl font-bold ${isDarkMode ? 'text-yellow-400' : 'text-yellow-600'}`}>
                {partialCount} <span className={`text-lg font-normal ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>/{totalQuestions}</span>
              </span>
            </div>
          )}

          <div className={`flex justify-between items-center p-4 ${isDarkMode ? 'bg-red-900' : 'bg-red-50'} rounded-lg`}>
            <span className={`font-medium ${classes.mutedText}`}>Câu sai</span>
            <span className={`text-2xl font-bold ${isDarkMode ? 'text-red-400' : 'text-red-600'}`}>
              {incorrectCount} <span className={`text-lg font-normal ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>/{totalQuestions}</span>
            </span>
          </div>

          <div className={`flex justify-between items-center p-4 ${isDarkMode ? 'bg-indigo-900' : 'bg-indigo-50'} rounded-lg`}>
            <span className={`font-medium ${classes.mutedText}`}>Điểm cuối (trên 10)</span>
            <span className={`text-2xl font-bold ${isDarkMode ? 'text-indigo-400' : 'text-indigo-600'}`}>{score}</span>
          </div>
        </div>

        <div className="space-y-3">
          <Button
            variant="blue"
            onClick={onReviewAnswers}
            className="w-full flex items-center justify-center"
            title="Xem lại đáp án"
          >
            <IconEye className="w-5 h-5 mr-2" />
            Xem lại đáp án
          </Button>
          <Button
            onClick={handleRetry}
            className="w-full flex items-center justify-center"
            title="Làm lại"
          >
            <IconRetry className="w-5 h-5 mr-2" />
            Làm lại
          </Button>
          {isHistoryView ? (
            <Button
              variant="neutral"
              onClick={onReturnBack}
              className="w-full flex items-center justify-center"
              title="Quay lại"
            >
              <IconChevronLeft className="w-5 h-5 mr-2" />
              Quay lại
            </Button>
          ) : (
            <Button
              variant="neutral"
              onClick={handleFinish}
              className="w-full flex items-center justify-center"
              title="Về trang tải lên"
            >
              <IconClose className="w-5 h-5 mr-2" />
              Kết thúc
            </Button>
          )}
        </div>
      </div>

      {showRetryModal && (
        <Modal title="Làm lại" description="Chọn cách làm lại bài quiz:">
          <Button
            onClick={() => { setShowRetryModal(false); onRetrySameLayout(); }}
            className="w-full"
            title="Làm lại bài trước"
          >
            Giữ nguyên thứ tự
            <span className="block text-sm text-indigo-200 mt-1">
              Giữ nguyên thứ tự câu hỏi và đáp án
            </span>
          </Button>
          <Button
            variant="purple"
            onClick={() => { setShowRetryModal(false); onRetryNewShuffle(); }}
            className="w-full"
            title="Làm bài mới"
          >
            Xáo trộn lại
            <span className="block text-sm text-purple-200 mt-1">
              Xáo trộn lại câu hỏi và đáp án
            </span>
          </Button>
          <Button variant="secondary" onClick={() => setShowRetryModal(false)} className="w-full" title="Đóng">
            Huỷ
          </Button>
        </Modal>
      )}
    </div>
  );
};

export default ResultPage;
