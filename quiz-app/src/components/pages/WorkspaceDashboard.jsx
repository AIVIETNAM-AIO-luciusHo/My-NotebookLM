import { useRef, useState } from 'react';
import { useTheme } from '../../contexts/useTheme';
import NotebookChat from './NotebookChat';
import QuizStudio from './QuizStudio';
import MindmapVisualizer from './MindmapVisualizer';
import ErrorBanner from '../ui/ErrorBanner';
import ThemeToggle from '../ui/ThemeToggle';
import { IconDocument, IconUpload, IconChevronLeft } from '../ui/icons';
import { BACKEND } from '../../lib/api';

// ── Tab definitions ───────────────────────────────────────────────────────────

const TABS = [
  {
    id: 'chat',
    label: 'Notebook Chat',
    shortLabel: 'Chat',
    color: 'indigo',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    ),
  },
  {
    id: 'quiz',
    label: 'Quiz Studio',
    shortLabel: 'Quiz',
    color: 'violet',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  {
    id: 'mindmap',
    label: 'Mindmap Visualizer',
    shortLabel: 'Mindmap',
    color: 'emerald',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
      </svg>
    ),
  },
];

const TAB_ACTIVE = {
  indigo: 'text-indigo-600 border-indigo-600',
  violet: 'text-violet-600 border-violet-600',
  emerald: 'text-emerald-600 border-emerald-600',
};
const TAB_ACTIVE_DARK = {
  indigo: 'text-indigo-400 border-indigo-400',
  violet: 'text-violet-400 border-violet-400',
  emerald: 'text-emerald-400 border-emerald-400',
};

// ── Upload zone (shown when no document is active) ────────────────────────────

const UploadZone = ({ onUploadSuccess, setView }) => {
  const { isDarkMode, classes } = useTheme();
  const [pdfFile, setPdfFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);
  const fileRef = useRef(null);

  const setFile = (file) => {
    if (file && file.name.toLowerCase().endsWith('.pdf')) {
      setPdfFile(file);
      setUploadError('');
    } else if (file) {
      setUploadError('Only PDF files are accepted.');
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    setFile(e.dataTransfer.files[0] ?? null);
  };

  const handleUpload = async () => {
    if (!pdfFile) { setUploadError('Please select a PDF file.'); return; }
    setUploading(true);
    setUploadError('');
    try {
      const form = new FormData();
      form.append('file', pdfFile);
      const res = await fetch(`${BACKEND}/upload`, { method: 'POST', body: form });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? 'Upload failed.');
      }
      onUploadSuccess(pdfFile.name);
    } catch (e) {
      setUploadError(e.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Slim top nav */}
      <div className={`flex-shrink-0 flex items-center justify-between px-5 py-3 border-b ${
        isDarkMode ? 'border-gray-800 bg-gray-900' : 'border-gray-200 bg-white'
      }`}>
        <button
          onClick={() => setView('home')}
          className={`flex items-center gap-1.5 text-sm font-medium transition-colors ${
            isDarkMode ? 'text-gray-400 hover:text-gray-200' : 'text-gray-500 hover:text-gray-800'
          }`}
        >
          <IconChevronLeft className="w-4 h-4" />
          Home
        </button>
        <div className={`flex items-center gap-2 text-sm font-semibold ${isDarkMode ? 'text-gray-200' : 'text-gray-700'}`}>
          <svg className={`w-5 h-5 ${isDarkMode ? 'text-indigo-400' : 'text-indigo-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          AI Study Studio
        </div>
        <div className="flex items-center justify-end w-20">
          <ThemeToggle compact />
        </div>
      </div>

      {/* Upload hero */}
      <div className="flex-1 flex flex-col items-center justify-center p-6">
        <div className="w-full max-w-xl animate-fadeInUp">
          <div className="text-center mb-8">
            <h1 className={`text-3xl font-bold ${classes.textColor} mb-2`}>Add a source document</h1>
            <p className={`${classes.mutedText} text-sm`}>
              Upload a PDF to unlock Notebook Chat, Quiz Studio, and Mindmap Visualizer
            </p>
          </div>

          {/* Drag-and-drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileRef.current?.click()}
            className={`relative cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition-all duration-200 ${
              isDragOver
                ? isDarkMode ? 'border-indigo-400 bg-indigo-900/20 scale-[1.01]' : 'border-indigo-400 bg-indigo-50 scale-[1.01]'
                : pdfFile
                  ? isDarkMode ? 'border-green-600 bg-green-900/20' : 'border-green-400 bg-green-50'
                  : isDarkMode ? 'border-gray-700 hover:border-indigo-600 hover:bg-indigo-900/10' : 'border-gray-300 hover:border-indigo-400 hover:bg-indigo-50/50'
            }`}
          >
            <input
              ref={fileRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => setFile(e.target.files[0] ?? null)}
            />

            {pdfFile ? (
              <>
                <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4 ${isDarkMode ? 'bg-green-900' : 'bg-green-100'}`}>
                  <IconDocument className={`w-8 h-8 ${isDarkMode ? 'text-green-400' : 'text-green-600'}`} />
                </div>
                <p className={`font-semibold ${classes.textColor} truncate max-w-xs mx-auto`}>{pdfFile.name}</p>
                <p className={`text-xs ${classes.mutedText} mt-1`}>{(pdfFile.size / 1024).toFixed(0)} KB · click to change</p>
              </>
            ) : (
              <>
                <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4 ${
                  isDragOver
                    ? isDarkMode ? 'bg-indigo-800' : 'bg-indigo-100'
                    : isDarkMode ? 'bg-gray-800' : 'bg-gray-100'
                }`}>
                  <IconUpload className={`w-8 h-8 ${isDragOver ? isDarkMode ? 'text-indigo-400' : 'text-indigo-600' : classes.mutedText}`} />
                </div>
                <p className={`font-semibold ${classes.textColor} mb-1`}>
                  {isDragOver ? 'Drop your PDF here' : 'Drag & drop a PDF, or click to browse'}
                </p>
                <p className={`text-xs ${classes.mutedText}`}>Supports text-based PDFs up to any size</p>
              </>
            )}
          </div>

          {/* Upload feedback */}
          {uploading && (
            <div className="flex items-center gap-2.5 mt-4 py-1">
              <div className={`w-4 h-4 border-2 border-t-transparent rounded-full animate-spin flex-shrink-0 ${isDarkMode ? 'border-indigo-400' : 'border-indigo-600'}`} />
              <p className={`text-sm font-medium ${isDarkMode ? 'text-indigo-300' : 'text-indigo-600'}`}>
                Reading and indexing document chunks…
              </p>
            </div>
          )}

          <div className="mt-3">
            <ErrorBanner>{uploadError}</ErrorBanner>
          </div>

          <button
            onClick={handleUpload}
            disabled={uploading || !pdfFile}
            className={`mt-4 w-full flex items-center justify-center gap-2.5 py-3.5 rounded-2xl text-sm font-bold transition-all duration-200 ${
              uploading || !pdfFile
                ? isDarkMode ? 'bg-gray-700 text-gray-500 cursor-not-allowed' : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                : 'bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white shadow-md hover:shadow-lg hover:-translate-y-0.5'
            }`}
          >
            {uploading ? (
              <>
                <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                Indexing document…
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Analyse Document & Unlock Workspace
              </>
            )}
          </button>

          {/* Feature preview chips */}
          <div className="mt-8 flex flex-wrap justify-center gap-2">
            {[
              { color: 'indigo', label: 'Notebook Chat' },
              { color: 'violet', label: 'Quiz Studio' },
              { color: 'emerald', label: 'Mindmap Visualizer' },
            ].map(({ color, label }) => (
              <span key={label} className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border ${
                isDarkMode ? `border-gray-700 text-gray-500` : `border-gray-200 text-gray-400`
              }`}>
                <span className={`w-1.5 h-1.5 rounded-full bg-${color}-400 opacity-50`} />
                {label}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

// ── Workspace (shown once a document is active) ───────────────────────────────

const ActiveWorkspace = ({
  documentName,
  onClearDocument,
  setView,
  activeTab,
  onTabChange,
  mindmapMounted,
  quizProps,
}) => {
  const { isDarkMode, classes } = useTheme();

  return (
    <div className="flex flex-col h-screen">
      {/* Top document bar */}
      <div className={`flex-shrink-0 flex items-center gap-3 px-4 py-2.5 border-b ${
        isDarkMode ? 'border-gray-700/80 bg-gray-900' : 'border-gray-200 bg-white'
      } shadow-sm`}>
        <button
          onClick={() => setView('home')}
          className={`p-1.5 rounded-lg transition-colors flex-shrink-0 ${
            isDarkMode ? 'text-gray-500 hover:text-gray-300 hover:bg-gray-800' : 'text-gray-400 hover:text-gray-700 hover:bg-gray-100'
          }`}
          title="Back to Home"
        >
          <IconChevronLeft className="w-4 h-4" />
        </button>

        <div className={`w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 ${isDarkMode ? 'bg-indigo-900' : 'bg-indigo-100'}`}>
          <IconDocument className={`w-3.5 h-3.5 ${isDarkMode ? 'text-indigo-400' : 'text-indigo-600'}`} />
        </div>

        <div className="flex items-center gap-1.5 min-w-0 flex-1">
          <p className={`text-sm font-semibold ${classes.textColor} truncate`}>{documentName}</p>
          <span className={`flex-shrink-0 inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full font-medium ${
            isDarkMode ? 'bg-green-900/60 text-green-400' : 'bg-green-100 text-green-700'
          }`}>
            <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
            Indexed
          </span>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={onClearDocument}
            className={`text-xs font-medium px-2.5 py-1.5 rounded-lg border transition-colors ${
              isDarkMode
                ? 'border-gray-700 text-gray-500 hover:text-gray-300 hover:border-gray-600'
                : 'border-gray-300 text-gray-400 hover:text-gray-600 hover:border-gray-400'
            }`}
          >
            Change document
          </button>
          <ThemeToggle compact />
        </div>
      </div>

      {/* Tab bar */}
      <div className={`flex-shrink-0 flex border-b ${isDarkMode ? 'border-gray-700/80 bg-gray-900' : 'border-gray-200 bg-white'}`}>
        {TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          const activeClass = isDarkMode ? TAB_ACTIVE_DARK[tab.color] : TAB_ACTIVE[tab.color];
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`flex items-center gap-2 px-4 sm:px-6 py-3 text-sm font-semibold border-b-2 transition-all duration-150 -mb-px ${
                isActive
                  ? `${activeClass} bg-transparent`
                  : `border-transparent ${isDarkMode ? 'text-gray-500 hover:text-gray-300' : 'text-gray-500 hover:text-gray-700'}`
              }`}
            >
              <span className={isActive ? '' : 'opacity-60'}>{tab.icon}</span>
              <span className="hidden sm:inline">{tab.label}</span>
              <span className="sm:hidden">{tab.shortLabel}</span>
            </button>
          );
        })}
      </div>

      {/* Tab panels — all kept mounted (CSS hidden) to preserve state */}
      <div className="flex-1 overflow-hidden">
        {/* Panel: Notebook Chat */}
        <div className={activeTab === 'chat' ? 'flex flex-col h-full' : 'hidden'}>
          <NotebookChat key={documentName} documentName={documentName} />
        </div>

        {/* Panel: Quiz Studio */}
        <div className={activeTab === 'quiz' ? 'h-full' : 'hidden'}>
          <QuizStudio {...quizProps} />
        </div>

        {/* Panel: Mindmap Visualizer — lazily mounted on first activation */}
        {mindmapMounted && (
          <div className={activeTab === 'mindmap' ? 'flex flex-col h-full' : 'hidden'}>
            <MindmapVisualizer key={documentName} />
          </div>
        )}
      </div>
    </div>
  );
};

// ── WorkspaceDashboard (root) ─────────────────────────────────────────────────

const WorkspaceDashboard = ({
  isDocumentLoaded,
  currentDocumentName,
  onUploadSuccess,
  onClearDocument,
  setView,
  setOriginalQuizData,
  setProcessedQuizData,
  setActiveSettings,
  setAnswers,
  setCurrentQuestion,
}) => {
  const [activeTab, setActiveTab] = useState('chat');
  const [mindmapMounted, setMindmapMounted] = useState(false);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    if (tab === 'mindmap') setMindmapMounted(true);
  };

  const quizProps = {
    setView,
    setOriginalQuizData,
    setProcessedQuizData,
    setActiveSettings,
    setAnswers,
    setCurrentQuestion,
  };

  if (!isDocumentLoaded) {
    return <UploadZone onUploadSuccess={onUploadSuccess} setView={setView} />;
  }

  return (
    <ActiveWorkspace
      documentName={currentDocumentName}
      onClearDocument={onClearDocument}
      setView={setView}
      activeTab={activeTab}
      onTabChange={handleTabChange}
      mindmapMounted={mindmapMounted}
      quizProps={quizProps}
    />
  );
};

export default WorkspaceDashboard;
