import { useRef, useState } from 'react';
import { processQuizData } from '../../utils/utils.js';
import { useQuizLibrary } from '../../hooks/useQuizLibrary.js';
import { useTheme } from '../../contexts/useTheme';
import Button from '../ui/Button';
import ErrorBanner from '../ui/ErrorBanner';
import { IconChevronLeft, IconUpload, IconDocument } from '../ui/icons';

import { BACKEND } from '../../lib/api';

const STAGE_LABELS = {
  uploading: 'Reading Document…',
  generating: 'AI is generating questions…',
};

const QuizGeneratorPage = ({
  setView,
  setOriginalQuizData,
  setProcessedQuizData,
  setActiveSettings,
  setAnswers,
  setCurrentQuestion,
}) => {
  const { isDarkMode, classes } = useTheme();
  const { saveQuiz } = useQuizLibrary();

  const [pdfFile, setPdfFile] = useState(null);
  const [topic, setTopic] = useState('');
  const [numQ, setNumQ] = useState('5');
  const [difficulty, setDifficulty] = useState('Normal');
  const [stage, setStage] = useState(''); // '' | 'uploading' | 'generating'
  const [error, setError] = useState('');

  const fileRef = useRef(null);

  const handleGenerate = async () => {
    if (!pdfFile) { setError('Please select a PDF file.'); return; }
    if (!topic.trim()) { setError('Please enter a topic.'); return; }

    setStage('uploading');
    setError('');
    try {
      // Step 1: Upload and index the PDF
      const form = new FormData();
      form.append('file', pdfFile);
      const uploadRes = await fetch(`${BACKEND}/upload`, { method: 'POST', body: form });
      if (!uploadRes.ok) {
        const err = await uploadRes.json();
        throw new Error(err.detail ?? 'PDF upload failed.');
      }

      // Step 2: Generate quiz via LLM
      setStage('generating');
      const quizRes = await fetch(`${BACKEND}/generate-quiz`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: topic.trim(), num_questions: parseInt(numQ) || 5, difficulty: difficulty.trim() || 'Normal' }),
      });
      if (!quizRes.ok) {
        const err = await quizRes.json();
        throw new Error(err.detail ?? 'Quiz generation failed.');
      }

      const quizData = await quizRes.json();
      if (!quizData.questions?.length) throw new Error('No questions generated. Try a different topic.');

      // Save to library so it appears in quiz history
      const name = quizData.title ?? topic.trim();
      saveQuiz(quizData, name);

      // Launch directly into the quiz using all generated questions
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
      setStage('');
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen p-4">
      <div className={`${classes.cardBg} rounded-2xl shadow-2xl p-8 max-w-md w-full animate-fadeInUp`}>

        {/* Back button */}
        <button
          onClick={() => setView('home')}
          className={`flex items-center gap-1.5 text-sm font-medium mb-6 transition-colors ${
            isDarkMode ? 'text-gray-400 hover:text-gray-200' : 'text-gray-500 hover:text-gray-800'
          }`}
        >
          <IconChevronLeft className="w-4 h-4" />
          Back to Home
        </button>

        {/* Header */}
        <div className="text-center mb-8">
          <div className={`w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4 ${
            isDarkMode ? 'bg-violet-900' : 'bg-violet-100'
          }`}>
            <svg className={`w-9 h-9 ${isDarkMode ? 'text-violet-400' : 'text-violet-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <p className={`text-xs font-bold uppercase tracking-widest mb-1 ${isDarkMode ? 'text-violet-400' : 'text-violet-600'}`}>
            Module B
          </p>
          <h1 className={`text-2xl font-bold ${classes.textColor} mb-1`}>Quiz Generator</h1>
          <p className={`text-sm ${classes.mutedText}`}>
            Upload a PDF, enter a topic, and we'll generate a quiz instantly.
          </p>
        </div>

        <div className="space-y-4">
          {/* Step 1: PDF */}
          <div>
            <p className={`text-xs font-semibold uppercase tracking-wide mb-2 ${isDarkMode ? 'text-violet-400' : 'text-violet-600'}`}>
              Step 1 — Choose your document
            </p>
            <label className={`flex items-center gap-3 px-4 py-3 border-2 border-dashed rounded-xl cursor-pointer transition-colors ${
              pdfFile
                ? isDarkMode ? 'border-violet-600 bg-violet-900/20' : 'border-violet-400 bg-violet-50'
                : isDarkMode ? 'border-gray-600 hover:border-violet-500' : 'border-gray-300 hover:border-violet-400'
            }`}>
              <div className={`flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center ${
                pdfFile
                  ? isDarkMode ? 'bg-violet-900' : 'bg-violet-100'
                  : isDarkMode ? 'bg-gray-700' : 'bg-gray-100'
              }`}>
                {pdfFile
                  ? <IconDocument className={`w-5 h-5 ${isDarkMode ? 'text-violet-400' : 'text-violet-600'}`} />
                  : <IconUpload className={`w-5 h-5 ${classes.mutedText}`} />
                }
              </div>
              <div className="flex-1 min-w-0 text-left">
                <p className={`text-sm font-medium truncate ${pdfFile ? classes.textColor : classes.mutedText}`}>
                  {pdfFile ? pdfFile.name : 'Click to select PDF'}
                </p>
                {pdfFile && (
                  <p className={`text-xs ${classes.mutedText}`}>{(pdfFile.size / 1024).toFixed(0)} KB</p>
                )}
              </div>
              <input
                ref={fileRef}
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={(e) => { setPdfFile(e.target.files[0] ?? null); setError(''); }}
              />
            </label>
          </div>

          {/* Step 2: Topic */}
          <div>
            <p className={`text-xs font-semibold uppercase tracking-wide mb-2 ${isDarkMode ? 'text-violet-400' : 'text-violet-600'}`}>
              Step 2 — Enter a topic
            </p>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
              placeholder="e.g. Photosynthesis, World War II, Newton's Laws…"
              className={`w-full px-4 py-3 border-2 rounded-xl text-sm focus:outline-none transition-colors ${
                isDarkMode
                  ? 'bg-gray-700 border-gray-600 text-white placeholder-gray-500 focus:border-violet-500'
                  : 'bg-gray-50 border-gray-300 text-gray-800 placeholder-gray-400 focus:border-violet-400'
              }`}
            />
          </div>

          {/* Step 3: Difficulty / Focus */}
          <div>
            <p className={`text-xs font-semibold uppercase tracking-wide mb-2 ${isDarkMode ? 'text-violet-400' : 'text-violet-600'}`}>
              Step 3 — Difficulty / Focus
            </p>
            <div className="flex gap-2 flex-wrap mb-2">
              {['Easy', 'Normal', 'Hard'].map((d) => (
                <button
                  key={d}
                  onClick={() => setDifficulty(d)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold border-2 transition-all ${
                    difficulty === d
                      ? 'bg-violet-600 border-violet-600 text-white'
                      : isDarkMode
                        ? 'border-gray-600 text-gray-300 hover:border-violet-500 hover:text-violet-300'
                        : 'border-gray-300 text-gray-600 hover:border-violet-400 hover:text-violet-600'
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
            <input
              type="text"
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value)}
              placeholder="e.g. Hard, Focus on formulas, Application questions…"
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

          {/* Step 4: Number of questions */}
          <div>
            <p className={`text-xs font-semibold uppercase tracking-wide mb-2 ${isDarkMode ? 'text-violet-400' : 'text-violet-600'}`}>
              Step 4 — Choose question count
            </p>
            <div className="flex items-center gap-3">
              {['3', '5', '7', '10'].map((n) => (
                <button
                  key={n}
                  onClick={() => setNumQ(n)}
                  className={`flex-1 py-2 rounded-xl text-sm font-semibold border-2 transition-all ${
                    numQ === n
                      ? 'bg-violet-600 border-violet-600 text-white'
                      : isDarkMode
                        ? 'border-gray-600 text-gray-300 hover:border-violet-500 hover:text-violet-300'
                        : 'border-gray-300 text-gray-600 hover:border-violet-400 hover:text-violet-600'
                  }`}
                >
                  {n}
                </button>
              ))}
              <div className="relative flex-1">
                <input
                  type="number"
                  min="1"
                  max="15"
                  value={numQ}
                  onChange={(e) => setNumQ(e.target.value)}
                  className={`w-full py-2 px-2 rounded-xl text-sm font-semibold border-2 text-center focus:outline-none transition-colors ${
                    !['3','5','7','10'].includes(numQ)
                      ? 'bg-violet-600 border-violet-600 text-white'
                      : isDarkMode
                        ? 'bg-gray-700 border-gray-600 text-gray-300 focus:border-violet-500'
                        : 'bg-gray-50 border-gray-300 text-gray-600 focus:border-violet-400'
                  }`}
                  title="Custom number of questions"
                />
              </div>
            </div>
            <p className={`text-xs ${classes.mutedText} mt-1.5`}>Maximum 15 questions per generation</p>
          </div>

          {/* Loading indicator */}
          {stage && (
            <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border-2 ${
              isDarkMode ? 'border-violet-600 bg-violet-900/20' : 'border-violet-300 bg-violet-50'
            }`}>
              <div className={`w-5 h-5 border-2 border-t-transparent rounded-full animate-spin flex-shrink-0 ${
                isDarkMode ? 'border-violet-400' : 'border-violet-600'
              }`} />
              <div>
                <p className={`text-sm font-semibold ${isDarkMode ? 'text-violet-300' : 'text-violet-700'}`}>
                  {STAGE_LABELS[stage]}
                </p>
                <p className={`text-xs ${classes.mutedText} mt-0.5`}>
                  {stage === 'uploading' ? 'Extracting and embedding text chunks…' : 'Generating questions via few-shot prompting…'}
                </p>
              </div>
            </div>
          )}

          <ErrorBanner>{error}</ErrorBanner>

          {/* CTA */}
          <Button
            variant="purple"
            onClick={handleGenerate}
            disabled={!!stage}
            className="w-full flex items-center justify-center gap-2 py-3.5"
            title="Generate quiz from PDF and play immediately"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            {stage === 'uploading'
              ? 'Reading Document…'
              : stage === 'generating'
                ? 'Generating Questions…'
                : 'Generate & Play Quiz'}
          </Button>
        </div>

        {/* Footer hint */}
        <p className={`text-xs ${classes.mutedText} text-center mt-5`}>
          Quiz is saved to your library for later replay
        </p>
      </div>
    </div>
  );
};

export default QuizGeneratorPage;
