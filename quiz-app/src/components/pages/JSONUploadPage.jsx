import { useEffect, useRef, useState } from 'react';
import { BACKEND } from '../../lib/api';
import { processQuizData, readQuizFile, stripQuizExtension } from '../../utils/utils.js';
import { sortLibrary, hashQuiz } from '../../utils/storage.js';
import { loadHistory } from '../../utils/history.js';
import { sampleQuizEntry } from '../../utils/sampleQuiz.js';
import { useQuizLibrary } from '../../hooks/useQuizLibrary';
import { useTheme } from '../../contexts/useTheme';
import QuizLibraryPane from '../ui/QuizLibraryPane';
import ShareQuizDialog from '../ui/ShareQuizDialog';
import ConfigChips from '../ui/ConfigChips';
import IconButton from '../ui/IconButton';
import Button from '../ui/Button';
import ErrorBanner from '../ui/ErrorBanner';
import { SettingToggle } from '../ui/ToggleSwitch';
import {
  IconUpload,
  IconChevronRight,
  IconPencil,
  IconClose,
  IconDocument,
  IconArrowRight,
  IconShare,
} from '../ui/icons';

const JSONUploadPage = ({
  setView,
  setOriginalQuizData,
  setProcessedQuizData,
  setActiveSettings,
  setAnswers,
  setCurrentQuestion,
  uploadedFileInfo,
  setUploadedFileInfo,
  setEditingQuiz,
  onOpenHistory,
  initialSettings,
  onShareConsumed,
}) => {
  const { isDarkMode, classes } = useTheme();
  const [error, setError] = useState('');

  // ── AI Quiz Generator state ──────────────────────────────────────────────
  const [aiPdf, setAiPdf] = useState(null);
  const [aiTopic, setAiTopic] = useState('');
  const [aiNumQ, setAiNumQ] = useState('5');
  // '' = idle, 'uploading' = indexing PDF, 'generating' = LLM running
  const [aiStage, setAiStage] = useState('');
  const [aiError, setAiError] = useState('');
  const aiFileRef = useRef(null);
  // Shuffle/size controls seed from `initialSettings` when the page was reached
  // via a share link (so the friend lands on a pre-configured card); otherwise
  // they use the normal defaults. Lazy initializers run once, so clearing the
  // prop afterward (onShareConsumed) doesn't reset what the user then changes.
  const [shuffleQuestions, setShuffleQuestions] = useState(() => initialSettings?.shuffleQuestions ?? false);
  const [shuffleOptions, setShuffleOptions] = useState(() => initialSettings?.shuffleOptions ?? false);
  const [quizSizeMode, setQuizSizeMode] = useState(() => initialSettings?.quizSizeMode ?? 'percentage');
  // Each mode keeps its own value so toggling never carries a count into the
  // percentage field (or vice versa) — a count of 7 is meaningless as "7%".
  // Percentage defaults to 100; count is seeded with the loaded quiz's full
  // question count (refreshed whenever a quiz is loaded). The active field
  // reads/writes whichever one matches the current mode.
  const [percentSize, setPercentSize] = useState(() =>
    initialSettings?.quizSizeMode === 'percentage' && initialSettings.quizSize != null
      ? String(initialSettings.quizSize)
      : '100',
  );
  const [countSize, setCountSize] = useState(() =>
    initialSettings?.quizSizeMode === 'count' && initialSettings.quizSize != null
      ? String(initialSettings.quizSize)
      : uploadedFileInfo?.questionCount
        ? String(uploadedFileInfo.questionCount)
        : '',
  );
  const quizSize = quizSizeMode === 'percentage' ? percentSize : countSize;
  const setActiveSize = quizSizeMode === 'percentage' ? setPercentSize : setCountSize;
  // Saved-quiz library (localStorage), owned by the hook. The page remounts on
  // each return to upload, so it always reflects fresh storage.
  const { library, saveQuiz, removeFromLibrary, toggleBookmark } = useQuizLibrary();
  const [showLibrary, setShowLibrary] = useState(false);
  // The quiz being shared ({ rawData, name }), or null. Set from either the
  // loaded green card or a saved-quiz row in the library pane.
  const [shareTarget, setShareTarget] = useState(null);
  // Results history per quiz id, read once on mount (the page remounts on each
  // return to upload, so it reflects attempts recorded during the session).
  const [historyMap] = useState(() => loadHistory());

  // Returning to upload should start at the top, not inherit the previous
  // page's scroll position. Also, once a share link's settings have seeded the
  // controls above, tell App to clear them so a later remount uses plain
  // defaults (guarded by a ref so it fires exactly once).
  const shareConsumedRef = useRef(false);
  useEffect(() => {
    window.scrollTo(0, 0);
    if (initialSettings && !shareConsumedRef.current && onShareConsumed) {
      shareConsumedRef.current = true;
      onShareConsumed();
    }
  }, [initialSettings, onShareConsumed]);

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const { data, error: parseError } = await readQuizFile(file);
    if (parseError) {
      setError(parseError);
      setUploadedFileInfo(null);
      return;
    }
    if (data.questions.length < 2) {
      setError('Quiz must contain at least 2 questions');
      setUploadedFileInfo(null);
      return;
    }

    // Drop the .json/.txt extension from the display/library name so a later
    // download (e.g. from the share dialog) doesn't pile extensions up.
    const name = stripQuizExtension(file.name);
    setUploadedFileInfo({
      file: file,
      name,
      questionCount: data.questions.length,
      rawData: data,
    });
    setOriginalQuizData(data);
    setError('');
    // Seed the count field with this quiz's full size (the percentage value is
    // left as the user set it).
    setCountSize(String(data.questions.length));

    // Persist to the library (dedupes identical content by bumping time).
    saveQuiz(data, name);
  };

  const handleRemoveFile = () => {
    setUploadedFileInfo(null);
    setOriginalQuizData(null);
    setError('');
    const fileInput = document.querySelector('input[type="file"]');
    if (fileInput) fileInput.value = '';
  };

  // Load a saved quiz into the normal flow: it populates uploadedFileInfo so the
  // existing settings card + Start button work unchanged (no File object needed).
  const selectFromLibrary = (entry) => {
    setUploadedFileInfo({
      name: entry.name,
      questionCount: entry.questionCount,
      rawData: entry.rawData,
    });
    setOriginalQuizData(entry.rawData);
    setError('');
    // Seed the count field with this quiz's full size.
    setCountSize(String(entry.questionCount));
    setShowLibrary(false);
  };

  // Open the loaded quiz in the creator for editing (reuses view === 'create').
  const editCurrentQuiz = () => {
    const id = hashQuiz(uploadedFileInfo.rawData);
    const entry = library.find((e) => e.id === id);
    setEditingQuiz({
      id,
      name: uploadedFileInfo.name,
      bookmarked: entry?.bookmarked ?? false,
      rawData: uploadedFileInfo.rawData,
    });
    setView('create');
  };

  const handleQuizSizeChange = (e) => {
    const value = e.target.value;
    if (value === '') {
      setActiveSize('');
      return;
    }
    if (!/^\d+$/.test(value)) return;

    const numValue = parseInt(value);
    if (quizSizeMode === 'percentage' && numValue > 100) {
      setPercentSize('100');
      return;
    }
    setActiveSize(value);
  };

  const handleAIGenerate = async () => {
    if (!aiPdf) { setAiError('Please select a PDF file.'); return; }
    if (!aiTopic.trim()) { setAiError('Please enter a topic.'); return; }

    setAiStage('uploading');
    setAiError('');
    try {
      // Step 1: Upload and index the PDF into ChromaDB
      const formData = new FormData();
      formData.append('file', aiPdf);
      const uploadRes = await fetch(`${BACKEND}/upload`, { method: 'POST', body: formData });
      if (!uploadRes.ok) {
        const err = await uploadRes.json();
        throw new Error(err.detail ?? 'PDF upload failed.');
      }

      // Step 2: Ask the LLM to generate quiz JSON from indexed content
      setAiStage('generating');
      const quizRes = await fetch(`${BACKEND}/generate-quiz`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: aiTopic.trim(), num_questions: parseInt(aiNumQ) || 5 }),
      });
      if (!quizRes.ok) {
        const err = await quizRes.json();
        throw new Error(err.detail ?? 'Quiz generation failed.');
      }

      const quizData = await quizRes.json();
      if (!quizData.questions?.length) throw new Error('No questions generated. Try a different topic.');

      // Save to the library so the quiz appears in the user's history
      const name = quizData.title ?? aiTopic.trim();
      saveQuiz(quizData, name);

      // Launch directly into the quiz — respect the user's current shuffle
      // toggles but always play all generated questions (quizSizeMode: 'count').
      const launchSettings = {
        shuffleQuestions,
        shuffleOptions,
        quizSize: quizData.questions.length,
        quizSizeMode: 'count',
      };
      setOriginalQuizData(quizData);
      setActiveSettings(launchSettings);
      setAnswers({});
      setCurrentQuestion(0);
      setProcessedQuizData(processQuizData(quizData, launchSettings));
      setView('quiz');

      // Clean up so the section is ready for the next generation
      setAiPdf(null);
      setAiTopic('');
      if (aiFileRef.current) aiFileRef.current.value = '';
    } catch (e) {
      setAiError(e.message);
    } finally {
      setAiStage('');
    }
  };

  const startQuiz = () => {
    const sizeValue = quizSize.trim();

    if (sizeValue === '') {
      setError('Please enter a quiz size value');
      return;
    }

    const parsedSize = parseInt(sizeValue);
    if (isNaN(parsedSize)) {
      setError('Quiz size must be a valid number');
      return;
    }

    if (quizSizeMode === 'percentage') {
      if (parsedSize < 10 || parsedSize > 100) {
        setError('Quiz Size must be between 10% and 100%');
        return;
      }
    } else {
      if (parsedSize < 2) {
        setError('Quiz must have at least 2 questions');
        return;
      }
      if (parsedSize > uploadedFileInfo.questionCount) {
        setError(`Question count cannot exceed ${uploadedFileInfo.questionCount}`);
        return;
      }
    }

    const currentSettings = { shuffleQuestions, shuffleOptions, quizSize: parsedSize, quizSizeMode };

    setActiveSettings(currentSettings);
    setAnswers({});
    setCurrentQuestion(0);
    setError('');

    const processedData = processQuizData(uploadedFileInfo.rawData, currentSettings);
    setProcessedQuizData(processedData);
    setView('quiz');
  };

  return (
    <div className="flex items-center justify-center min-h-screen p-4">
      <div className={`${classes.cardBg} rounded-2xl shadow-2xl p-8 max-w-md w-full transition-colors duration-300 animate-fadeInUp`}>
        <div className="text-center mb-8">
          <div className={`${isDarkMode ? 'bg-indigo-900' : 'bg-indigo-100'} w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-4`}>
            <IconUpload className={`w-10 h-10 ${isDarkMode ? 'text-indigo-400' : 'text-indigo-600'}`} />
          </div>
          <h1 className={`text-3xl font-bold ${classes.textColor} mb-2`}>Quiz Application</h1>
          <p className={classes.mutedText}>Upload a JSON or TXT file to start your quiz</p>
        </div>

        <div className="space-y-4">
          {!uploadedFileInfo ? (
            <label className="block">
              <div className={`border-2 border-dashed ${isDarkMode ? 'border-indigo-500' : 'border-indigo-300'} rounded-lg p-6 min-h-[192px] flex flex-col items-center justify-center text-center hover:border-indigo-500 transition-colors cursor-pointer`}>
                <input type="file" accept=".json,.txt" onChange={handleFileUpload} className="hidden" />
                <IconUpload className={`w-12 h-12 ${isDarkMode ? 'text-indigo-400' : 'text-indigo-400'} mx-auto mb-2`} />
                <p className={`${classes.textColor} font-medium`}>Click to upload JSON or TXT file</p>
                <p className={`${classes.mutedText} text-sm mt-1`}>or drag and drop</p>
                <p className={`${classes.mutedText} text-xs mt-2`}>Supported formats: .json, .txt</p>
              </div>
            </label>
          ) : (
            <div className={`relative border-2 ${isDarkMode ? 'border-green-600 bg-green-900' : 'border-green-300 bg-green-50'} rounded-lg p-6 min-h-[192px] flex flex-col justify-between`}>
              <div className="absolute top-2 right-2 flex items-center gap-1">
                <IconButton
                  tone="emerald"
                  onClick={() => setShareTarget({ rawData: uploadedFileInfo.rawData, name: uploadedFileInfo.name })}
                  aria-label="Share quiz"
                  title="Share via link"
                >
                  <IconShare className="w-5 h-5" />
                </IconButton>
                <IconButton tone="indigo" onClick={editCurrentQuiz} aria-label="Edit quiz" title="Edit questions">
                  <IconPencil className="w-5 h-5" />
                </IconButton>
                <IconButton tone="red" onClick={handleRemoveFile} aria-label="Remove file" title="Remove file">
                  <IconClose className="w-5 h-5" />
                </IconButton>
              </div>

              <div className="flex items-start gap-4 pr-28">
                <div className={`${isDarkMode ? 'bg-green-800' : 'bg-green-100'} p-3 rounded-lg flex-shrink-0`}>
                  <IconDocument className={`w-8 h-8 ${isDarkMode ? 'text-green-400' : 'text-green-600'}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className={`font-semibold ${classes.textColor} mb-1 truncate`} title={uploadedFileInfo.name}>{uploadedFileInfo.name}</p>
                  <p className={`${classes.mutedText} text-sm`}>{uploadedFileInfo.questionCount} questions loaded</p>
                  <ConfigChips
                    settings={{ shuffleQuestions, shuffleOptions, quizSize: parseInt(quizSize, 10), quizSizeMode }}
                    className="mt-2"
                  />
                </div>
              </div>

              <Button
                onClick={startQuiz}
                className="w-full flex items-center justify-center gap-2"
                title="Start Quiz"
              >
                Start Quiz
                <IconArrowRight className="w-5 h-5" />
              </Button>
            </div>
          )}

          <ErrorBanner>{error}</ErrorBanner>

          {library.length > 0 ? (
            <button
              type="button"
              onClick={() => setShowLibrary(true)}
              className={`w-full flex items-center justify-between px-4 py-3 ${classes.inputBgPlain} border-2 rounded-lg hover:border-indigo-500 transition-colors`}
              title="Choose a previously uploaded quiz"
            >
              <span className={`font-medium ${classes.textColor}`}>
                Choose a Saved Quiz
                <span className={`ml-2 text-sm ${classes.mutedText}`}>({library.length})</span>
              </span>
              <IconChevronRight className={`w-5 h-5 ${classes.mutedText}`} />
            </button>
          ) : (
            // No saved quizzes yet: offer the built-in sample in the same slot so
            // a first-time visitor can load it straight into the card below.
            <button
              type="button"
              onClick={() => selectFromLibrary(sampleQuizEntry)}
              className={`w-full flex items-center justify-between px-4 py-3 ${classes.inputBgPlain} border-2 rounded-lg hover:border-indigo-500 transition-colors`}
              title="Load the built-in sample quiz to try the app"
            >
              <span className={`font-medium ${classes.textColor}`}>
                Load a sample quiz
                <span className={`ml-2 text-sm ${classes.mutedText}`}>({sampleQuizEntry.questionCount} questions)</span>
              </span>
              <IconChevronRight className={`w-5 h-5 ${classes.mutedText}`} />
            </button>
          )}

          <div className={`p-4 ${classes.inputBgPlain} rounded-lg space-y-3`}>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div className="flex-1 min-w-0">
                <label htmlFor="quizSize" className={`font-medium ${classes.textColor} block`}>Quiz Size</label>
                <p className={`text-sm ${classes.mutedText} break-words`}>
                  {quizSizeMode === 'percentage' ? 'Take a percentage of questions' : 'Specify exact number of questions'}
                </p>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <button
                  onClick={() => setQuizSizeMode('percentage')}
                  className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                    quizSizeMode === 'percentage'
                      ? 'bg-indigo-600 text-white'
                      : `${isDarkMode ? 'bg-gray-600 text-gray-300' : 'bg-gray-300 text-gray-700'}`
                  }`}
                  title="Percentage (%)"
                >
                  %
                </button>
                <button
                  onClick={() => setQuizSizeMode('count')}
                  className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                    quizSizeMode === 'count'
                      ? 'bg-indigo-600 text-white'
                      : `${isDarkMode ? 'bg-gray-600 text-gray-300' : 'bg-gray-300 text-gray-700'}`
                  }`}
                  title="Number (#)"
                >
                  #
                </button>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <input
                id="quizSize"
                type="text"
                inputMode="numeric"
                value={quizSize}
                onChange={handleQuizSizeChange}
                placeholder={quizSizeMode === 'percentage' ? '100' : '10'}
                className={`flex-1 min-w-0 px-4 py-2 border-2 ${
                  isDarkMode ? 'bg-gray-600 border-gray-500 text-white' : 'bg-white border-gray-300 text-gray-800'
                } rounded-lg font-semibold focus:outline-none focus:border-indigo-500`}
              />
              <span className={`${classes.mutedText} font-medium whitespace-nowrap flex-shrink-0`}>
                {quizSizeMode === 'percentage' ? '%' : 'questions'}
              </span>
            </div>
          </div>

          <div className="space-y-3">
            <SettingToggle
              label="Shuffle Questions"
              description="Randomize question order"
              checked={shuffleQuestions}
              onChange={() => setShuffleQuestions(!shuffleQuestions)}
            />
            <SettingToggle
              label="Shuffle Options"
              description="Randomize answer choices"
              checked={shuffleOptions}
              onChange={() => setShuffleOptions(!shuffleOptions)}
            />
          </div>
        </div>

        <div className={`mt-6 p-4 ${classes.inputBgPlain} rounded-lg`}>
          <p className={`text-sm ${classes.mutedText} font-medium mb-2`}>Expected JSON format:</p>
          <pre className={`text-xs ${isDarkMode ? 'bg-gray-900 text-gray-300' : 'bg-white text-gray-800'} p-2 rounded border overflow-x-auto`}>
{`{
  "questions": [
    {
      "question": "Question text?",
      "options": ["A", "B", "C", "D"],
      "correctAnswer": 0,
      "explanation": "Why A is correct",
      "shuffle": 0
    }
  ]
}
`}
          </pre>
          <div className={`text-sm ${classes.mutedText} font-medium mt-2 space-y-1`}>
            <p>Note:</p>
            <p>Both .json and .txt are accepted; the file must contain valid quiz JSON.</p>
            <p>"explanation" and "shuffle" are optional.</p>
            <p>"shuffle": 0 prevents option shuffling for that specific question.</p>
            <p>"correctAnswer" can be a number (single choice) or an array of indices (multiple choice).</p>
          </div>
        </div>

        <div className={`mt-6 p-4 ${classes.inputBgPlain} rounded-lg`}>
          <p className={`text-sm ${classes.mutedText} mb-3 text-center`}>Don't have a quiz file yet?</p>
          <Button
            variant="purple"
            onClick={() => {
              setEditingQuiz(null);
              setView('create');
            }}
            className="w-full"
            title="Create your own quiz"
          >
            Create Your Own Quiz
          </Button>
        </div>

        {/* ── NotebookLM Auto-Quiz ──────────────────────────────────────── */}
        <div className={`mt-6 p-4 rounded-lg space-y-3 border-2 ${
          isDarkMode ? 'border-violet-600 bg-violet-900/20' : 'border-violet-300 bg-violet-50'
        }`}>
          <div className="flex items-center gap-2">
            <svg className={`w-4 h-4 flex-shrink-0 ${isDarkMode ? 'text-violet-400' : 'text-violet-600'}`} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
            <p className={`text-sm font-semibold ${isDarkMode ? 'text-violet-300' : 'text-violet-700'}`}>
              NotebookLM Auto-Quiz
            </p>
          </div>
          <p className={`text-xs ${classes.mutedText}`}>
            Upload a PDF, type a topic, and jump straight into the quiz — no file editing needed.
          </p>

          <label className={`flex items-center gap-2 px-3 py-2 border-2 border-dashed ${
            isDarkMode ? 'border-violet-500 text-violet-300' : 'border-violet-300 text-violet-700'
          } rounded-lg cursor-pointer hover:border-violet-500 transition-colors`}>
            <span className="text-sm font-medium truncate">
              {aiPdf ? aiPdf.name : 'Click to select PDF'}
            </span>
            <input
              ref={aiFileRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => { setAiPdf(e.target.files[0] ?? null); setAiError(''); }}
            />
          </label>

          <input
            type="text"
            value={aiTopic}
            onChange={(e) => setAiTopic(e.target.value)}
            placeholder="Topic (e.g. Photosynthesis)"
            className={`w-full px-3 py-2 border-2 rounded-lg text-sm focus:outline-none focus:border-violet-500 ${
              isDarkMode ? 'bg-gray-600 border-gray-500 text-white' : 'bg-white border-gray-300 text-gray-800'
            }`}
          />

          <div className="flex items-center gap-2">
            <label className={`text-sm ${classes.mutedText} whitespace-nowrap`}>Questions:</label>
            <input
              type="number"
              min="1"
              max="15"
              value={aiNumQ}
              onChange={(e) => setAiNumQ(e.target.value)}
              className={`w-20 px-3 py-2 border-2 rounded-lg text-sm focus:outline-none focus:border-violet-500 ${
                isDarkMode ? 'bg-gray-600 border-gray-500 text-white' : 'bg-white border-gray-300 text-gray-800'
              }`}
            />
          </div>

          {aiStage && (
            <div className="flex items-center gap-2 py-1">
              <div className={`w-4 h-4 border-2 border-t-transparent rounded-full animate-spin flex-shrink-0 ${
                isDarkMode ? 'border-violet-400' : 'border-violet-600'
              }`} />
              <p className={`text-sm font-medium ${isDarkMode ? 'text-violet-300' : 'text-violet-600'}`}>
                {aiStage === 'uploading' ? 'Reading Document…' : 'AI is generating questions…'}
              </p>
            </div>
          )}

          <ErrorBanner>{aiError}</ErrorBanner>

          <Button
            variant="purple"
            onClick={handleAIGenerate}
            disabled={!!aiStage}
            className="w-full"
            title="Generate quiz from PDF and start playing immediately"
          >
            {aiStage === 'uploading'
              ? 'Reading Document…'
              : aiStage === 'generating'
                ? 'Generating Questions…'
                : 'Generate & Play Quiz'}
          </Button>
        </div>

        <div className="mt-6 text-center">
          <a
            href="https://github.com/ThSonDev/quiz-app"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-indigo-600 hover:text-indigo-800 underline"
          >
            View on GitHub
          </a>
        </div>
      </div>

      {showLibrary && (
        <QuizLibraryPane
          entries={[...sortLibrary(library), sampleQuizEntry]}
          historyMap={historyMap}
          onSelect={selectFromLibrary}
          onToggleBookmark={toggleBookmark}
          onRemove={removeFromLibrary}
          onOpenHistory={onOpenHistory}
          onShare={(entry) => setShareTarget({ rawData: entry.rawData, name: entry.name })}
          onClose={() => setShowLibrary(false)}
        />
      )}

      {shareTarget && (
        <ShareQuizDialog
          rawData={shareTarget.rawData}
          name={shareTarget.name}
          settings={{
            shuffleQuestions,
            shuffleOptions,
            quizSize: parseInt(quizSize, 10) || 100,
            quizSizeMode,
          }}
          onClose={() => setShareTarget(null)}
        />
      )}
    </div>
  );
};

export default JSONUploadPage;
