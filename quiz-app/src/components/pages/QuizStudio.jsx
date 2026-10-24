import { useState } from 'react';
import { useTheme } from '../../contexts/useTheme';
import { processQuizData } from '../../utils/utils.js';
import { useQuizLibrary } from '../../hooks/useQuizLibrary.js';
import ErrorBanner from '../ui/ErrorBanner';
import { BACKEND } from '../../lib/api';

const DIFFICULTY_PRESETS = ['Easy', 'Normal', 'Hard'];
const COUNT_PRESETS = ['3', '5', '7', '10'];

// ── Section label ─────────────────────────────────────────────────────────────

const Label = ({ children }) => {
  const { isDarkMode } = useTheme();
  return (
    <p className={`text-xs font-bold uppercase tracking-widest mb-2 ${isDarkMode ? 'text-violet-400' : 'text-violet-600'}`}>
      {children}
    </p>
  );
};

// ── Chip button ───────────────────────────────────────────────────────────────

const Chip = ({ label, active, onClick }) => {
  const { isDarkMode } = useTheme();
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-lg text-xs font-semibold border-2 transition-all ${
        active
          ? 'bg-violet-600 border-violet-600 text-white shadow-sm'
          : isDarkMode
            ? 'border-gray-600 text-gray-400 hover:border-violet-500 hover:text-violet-300'
            : 'border-gray-300 text-gray-600 hover:border-violet-400 hover:text-violet-600'
      }`}
    >
      {label}
    </button>
  );
};

// ── QuizStudio ────────────────────────────────────────────────────────────────

const QuizStudio = ({
  setView,
  setOriginalQuizData,
  setProcessedQuizData,
  setActiveSettings,
  setAnswers,
  setCurrentQuestion,
}) => {
  const { isDarkMode, classes } = useTheme();
  const { saveQuiz } = useQuizLibrary();

  const [topic, setTopic] = useState('');
  const [difficulty, setDifficulty] = useState('Normal');
  const [numQ, setNumQ] = useState('5');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleGenerate = async () => {
    const topicTrimmed = topic.trim();
    if (!topicTrimmed) { setError('Please enter a topic to focus on.'); return; }

    setLoading(true);
    setError('');

    try {
      const res = await fetch(`${BACKEND}/generate-quiz`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: topicTrimmed,
          num_questions: parseInt(numQ) || 5,
          difficulty: difficulty.trim() || 'Normal',
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? 'Quiz generation failed.');
      }
      const quizData = await res.json();
      if (!quizData.questions?.length) throw new Error('No questions returned. Try a different topic.');

      const name = quizData.title ?? topicTrimmed;
      saveQuiz(quizData, name);

      const launchSettings = {
        shuffleQuestions: false,
        shuffleOptions: false,
        quizSize: quizData.questions.length,
        quizSizeMode: 'count',
      };
      setOriginalQuizData(quizData);
      setActiveSettings(launchSettings);
      setAnswers({});
      setCurrentQuestion(0);
      setProcessedQuizData(processQuizData(quizData, launchSettings));
      setView('quiz');
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-lg mx-auto px-4 py-8 space-y-6">

        {/* Header */}
        <div className="text-center pb-2">
          <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4 ${
            isDarkMode ? 'bg-violet-900/60' : 'bg-violet-100'
          }`}>
            <svg className={`w-8 h-8 ${isDarkMode ? 'text-violet-400' : 'text-violet-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <h2 className={`text-xl font-bold ${classes.textColor}`}>Quiz Studio</h2>
          <p className={`text-sm ${classes.mutedText} mt-1`}>
            Generate a quiz directly from the active document
          </p>
        </div>

        {/* Topic */}
        <div>
          <Label>Topic / Focus Area</Label>
          <input
            type="text"
            value={topic}
            onChange={(e) => { setTopic(e.target.value); setError(''); }}
            onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
            placeholder="e.g. Photosynthesis, Newton's Laws, World War II…"
            className={`w-full px-4 py-3 border-2 rounded-xl text-sm focus:outline-none transition-colors ${
              isDarkMode
                ? 'bg-gray-700 border-gray-600 text-white placeholder-gray-500 focus:border-violet-500'
                : 'bg-gray-50 border-gray-300 text-gray-800 placeholder-gray-400 focus:border-violet-400'
            }`}
          />
        </div>

        {/* Difficulty */}
        <div>
          <Label>Difficulty / Focus Directive</Label>
          <div className="flex gap-2 mb-2 flex-wrap">
            {DIFFICULTY_PRESETS.map((d) => (
              <Chip key={d} label={d} active={difficulty === d} onClick={() => setDifficulty(d)} />
            ))}
          </div>
          <input
            type="text"
            value={difficulty}
            onChange={(e) => setDifficulty(e.target.value)}
            placeholder="Custom: e.g. Focus on formulas, Application questions…"
            className={`w-full px-4 py-2.5 border-2 rounded-xl text-sm focus:outline-none transition-colors ${
              isDarkMode
                ? 'bg-gray-700 border-gray-600 text-white placeholder-gray-500 focus:border-violet-500'
                : 'bg-gray-50 border-gray-300 text-gray-800 placeholder-gray-400 focus:border-violet-400'
            }`}
          />
          <p className={`text-xs ${classes.mutedText} mt-1.5`}>
            Pick a preset or type a custom focus directive
          </p>
        </div>

        {/* Question count */}
        <div>
          <Label>Number of Questions</Label>
          <div className="flex gap-2">
            {COUNT_PRESETS.map((n) => (
              <Chip key={n} label={n} active={numQ === n} onClick={() => setNumQ(n)} />
            ))}
            <input
              type="number"
              min="1"
              max="15"
              value={numQ}
              onChange={(e) => setNumQ(e.target.value)}
              className={`flex-1 py-1.5 px-2 rounded-lg text-xs font-semibold border-2 text-center focus:outline-none transition-colors ${
                !COUNT_PRESETS.includes(numQ)
                  ? 'bg-violet-600 border-violet-600 text-white'
                  : isDarkMode
                    ? 'bg-gray-700 border-gray-600 text-gray-300 focus:border-violet-500'
                    : 'bg-gray-50 border-gray-300 text-gray-600 focus:border-violet-400'
              }`}
              title="Custom number"
            />
          </div>
          <p className={`text-xs ${classes.mutedText} mt-1.5`}>Maximum 15 questions per generation</p>
        </div>

        {/* Error */}
        <ErrorBanner>{error}</ErrorBanner>

        {/* Generate button */}
        <button
          onClick={handleGenerate}
          disabled={loading || !topic.trim()}
          className={`w-full flex items-center justify-center gap-2.5 py-4 rounded-2xl text-sm font-bold transition-all duration-200 ${
            loading || !topic.trim()
              ? isDarkMode ? 'bg-gray-700 text-gray-500 cursor-not-allowed' : 'bg-gray-200 text-gray-400 cursor-not-allowed'
              : 'bg-violet-600 text-white hover:bg-violet-700 shadow-md hover:shadow-lg hover:-translate-y-0.5'
          }`}
        >
          {loading ? (
            <>
              <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
              Generating questions…
            </>
          ) : (
            <>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Generate & Play Quiz
            </>
          )}
        </button>

        {/* Hint */}
        {!loading && (
          <p className={`text-xs ${classes.mutedText} text-center`}>
            Quiz is saved to your library for later replay
          </p>
        )}
      </div>
    </div>
  );
};

export default QuizStudio;
