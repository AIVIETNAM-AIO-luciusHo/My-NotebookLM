import { useEffect, useState } from 'react';
import { BACKEND } from '../../lib/api';
import {
  calculateQuestionScore,
  isCorrectOption,
  isOptionChosen,
  optionLabel,
} from '../../utils/utils';
import { useTheme } from '../../contexts/useTheme';
import Explanation from '../ui/Explanation';
import RichText from '../ui/RichText';
import { IconHistory } from '../ui/icons';

const ReviewPage = ({ quizData, answers, setView, onOpenHistory }) => {
  const { isDarkMode, classes } = useTheme();
  const maxPointPerQuestion = 10 / quizData.questions.length;

  // ── AI Tutor state (keyed by question index) ─────────────────────────────
  const [tutorState, setTutorState] = useState({});
  const setTutor = (idx, patch) =>
    setTutorState((prev) => ({ ...prev, [idx]: { ...prev[idx], ...patch } }));

  const askTutor = async (idx, questionText) => {
    setTutor(idx, { loading: true, answer: '', sources: [], error: '' });
    try {
      const res = await fetch(`${BACKEND}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: questionText }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? 'AI Tutor request failed.');
      }
      const data = await res.json();
      setTutor(idx, { loading: false, answer: data.answer, sources: data.sources ?? [], error: '' });
      if (data.audio_base64) {
        new Audio(data.audio_base64).play().catch(() => {});
      }
    } catch (e) {
      setTutor(idx, { loading: false, answer: '', sources: [], error: e.message });
    }
  };

  // Open the review at the top, not at the results page's scroll position.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  const badgeFor = (rawScore) => {
    let cls = 'px-3 py-1 rounded-full text-sm font-bold ml-2 ';
    if (rawScore === 1) cls += isDarkMode ? 'bg-green-900 text-green-300' : 'bg-green-100 text-green-800';
    else if (rawScore === 0) cls += isDarkMode ? 'bg-red-900 text-red-300' : 'bg-red-100 text-red-800';
    else cls += isDarkMode ? 'bg-yellow-900 text-yellow-300' : 'bg-yellow-100 text-yellow-800';
    return cls;
  };

  return (
    <div className="min-h-screen p-4">
      <div className="max-w-4xl mx-auto py-8 animate-fadeInUp">
        <div className="sticky top-4 z-10 mb-6">
          <button
            onClick={() => setView('results')}
            className="w-full px-6 py-3 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-all shadow-lg"
          >
            ← Back to Results
          </button>
        </div>

        <div className={`${classes.cardBg} rounded-xl shadow-lg p-6 mb-6`}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className={`text-2xl font-bold ${classes.textColor} mb-2`}>Review All Answers</h2>
              <p className={classes.mutedText}>See all questions, correct answers, and explanations</p>
            </div>
            {onOpenHistory && (
              <button
                type="button"
                onClick={onOpenHistory}
                className={`flex-shrink-0 inline-flex items-center gap-1.5 text-sm font-medium ${
                  isDarkMode ? 'text-indigo-400 hover:text-indigo-300' : 'text-indigo-600 hover:text-indigo-800'
                } hover:underline`}
                title="See past attempts of this quiz"
              >
                <IconHistory className="w-4 h-4" />
                Results history
              </button>
            )}
          </div>
        </div>

        <div className="space-y-6">
          {quizData.questions.map((question, idx) => {
            const userAnswer = answers[idx];
            const rawScore = calculateQuestionScore(question, userAnswer);
            const displayedScore = (rawScore * maxPointPerQuestion).toFixed(3);

            return (
              <div key={idx} className={`${classes.cardBg} rounded-xl shadow-lg p-6`}>
                <div className="flex items-start justify-between mb-4 gap-3">
                  <h3 className={`text-xl font-bold ${classes.textColor} flex-1`}>
                    {idx + 1}. <RichText>{question.question}</RichText>
                  </h3>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className={badgeFor(rawScore)}>{parseFloat(displayedScore)}</span>
                    <button
                      type="button"
                      onClick={() => askTutor(idx, question.question)}
                      disabled={tutorState[idx]?.loading}
                      className={`px-3 py-1 rounded-full text-xs font-semibold transition-colors ${
                        isDarkMode
                          ? 'bg-purple-900 text-purple-300 hover:bg-purple-800 disabled:opacity-50'
                          : 'bg-purple-100 text-purple-700 hover:bg-purple-200 disabled:opacity-50'
                      }`}
                      title="Ask the AI Tutor about this question"
                    >
                      {tutorState[idx]?.loading ? '⏳ Asking…' : '🎓 Ask AI Tutor'}
                    </button>
                  </div>
                </div>

                <div className="space-y-2 mb-4">
                  {question.options.map((option, optIdx) => {
                    const correct = isCorrectOption(question, optIdx);
                    const selectedByUser = isOptionChosen(userAnswer, optIdx);
                    // A correct option the user missed is shown like the quiz
                    // runner: a green dashed box (still the right answer) with a
                    // red "Unchosen" X. The green "✓ Correct" tick only appears
                    // when the user actually picked the correct option.
                    const missedCorrect = correct && !selectedByUser;

                    let optionClass = 'p-3 rounded-lg border-2 flex items-center justify-between ';
                    if (missedCorrect) {
                      optionClass += isDarkMode
                        ? 'bg-green-900/30 border-green-500 border-dashed'
                        : 'bg-green-50 border-green-500 border-dashed';
                    } else if (correct) {
                      optionClass += isDarkMode ? 'bg-green-900 border-green-600' : 'bg-green-50 border-green-500';
                    } else if (selectedByUser && !correct) {
                      optionClass += isDarkMode ? 'bg-red-900 border-red-600' : 'bg-red-50 border-red-500';
                    } else {
                      optionClass += isDarkMode ? 'bg-gray-700 border-gray-600' : 'bg-gray-50 border-gray-200';
                    }

                    return (
                      <div key={optIdx} className={optionClass}>
                        <div className="flex items-center">
                          <span className="font-bold mr-2">{optionLabel(optIdx)}.</span>
                          <RichText>{option}</RichText>
                        </div>
                        <div className="flex items-center">
                          {missedCorrect && (
                            <span className={`ml-2 font-medium text-sm flex items-center ${
                              isDarkMode ? 'text-red-400' : 'text-red-700'
                            }`}>
                              ✗ Unchosen
                            </span>
                          )}
                          {correct && !missedCorrect && (
                            <span className={`ml-2 font-medium text-sm flex items-center ${
                              isDarkMode ? 'text-green-400' : 'text-green-700'
                            }`}>
                              ✓ Correct
                            </span>
                          )}
                          {selectedByUser && !correct && (
                            <span className={`ml-2 font-medium text-sm flex items-center ${
                              isDarkMode ? 'text-red-400' : 'text-red-700'
                            }`}>
                              ✗ Your answer
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {question.explanation && <Explanation>{question.explanation}</Explanation>}

                {/* ── AI Tutor Panel ────────────────────────────────────── */}
                {tutorState[idx] && (tutorState[idx].answer || tutorState[idx].error) && (
                  <div className={`mt-4 rounded-lg border p-4 space-y-3 ${
                    isDarkMode ? 'bg-purple-900/30 border-purple-700' : 'bg-purple-50 border-purple-200'
                  }`}>
                    <p className={`text-sm font-semibold ${isDarkMode ? 'text-purple-300' : 'text-purple-800'}`}>
                      🎓 AI Tutor
                    </p>

                    {tutorState[idx].error && (
                      <p className={`text-sm ${isDarkMode ? 'text-red-400' : 'text-red-700'}`}>
                        {tutorState[idx].error}
                      </p>
                    )}

                    {tutorState[idx].answer && (
                      <p className={`text-sm ${isDarkMode ? 'text-purple-100' : 'text-purple-900'}`}>
                        {tutorState[idx].answer}
                      </p>
                    )}

                    {tutorState[idx].sources?.length > 0 && (
                      <div className="space-y-2">
                        <p className={`text-xs font-semibold uppercase tracking-wide ${isDarkMode ? 'text-purple-400' : 'text-purple-600'}`}>
                          Sources
                        </p>
                        {tutorState[idx].sources.map((src, sIdx) => (
                          <div key={sIdx} className={`rounded p-2 text-xs ${
                            isDarkMode ? 'bg-purple-900 text-purple-200' : 'bg-purple-100 text-purple-800'
                          }`}>
                            <span className={`inline-block mr-2 font-bold ${
                              isDarkMode ? 'text-purple-300' : 'text-purple-700'
                            }`}>
                              [{src.cosine_score.toFixed(3)}]
                            </span>
                            {src.text}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default ReviewPage;
