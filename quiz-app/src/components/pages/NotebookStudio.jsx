import { useEffect, useRef, useState } from 'react';
import { useTheme } from '../../contexts/useTheme';
import Button from '../ui/Button';
import ErrorBanner from '../ui/ErrorBanner';
import { IconUpload, IconChevronLeft, IconDocument } from '../ui/icons';

// ── Source panel ─────────────────────────────────────────────────────────────

const SourcesPanel = ({ sources }) => {
  const { isDarkMode, classes } = useTheme();
  const [open, setOpen] = useState(false);

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-1 text-xs font-medium transition-colors ${
          isDarkMode ? 'text-indigo-400 hover:text-indigo-300' : 'text-indigo-600 hover:text-indigo-700'
        }`}
      >
        <svg
          className={`w-3 h-3 transition-transform duration-200 ${open ? 'rotate-90' : ''}`}
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        {sources.length} source{sources.length !== 1 ? 's' : ''} cited
      </button>

      {open && (
        <div className="mt-2 space-y-1.5">
          {sources.map((src, i) => (
            <div
              key={i}
              className={`flex items-start gap-2.5 px-3 py-2.5 rounded-lg ${
                isDarkMode ? 'bg-gray-900/60' : 'bg-gray-50'
              }`}
            >
              <span className={`flex-shrink-0 text-xs font-mono font-bold px-1.5 py-0.5 rounded-md ${
                src.cosine_score >= 0.85
                  ? isDarkMode ? 'bg-green-900 text-green-300' : 'bg-green-100 text-green-700'
                  : src.cosine_score >= 0.70
                    ? isDarkMode ? 'bg-yellow-900 text-yellow-300' : 'bg-yellow-100 text-yellow-700'
                    : isDarkMode ? 'bg-gray-700 text-gray-400' : 'bg-gray-200 text-gray-600'
              }`}>
                {src.cosine_score.toFixed(3)}
              </span>
              <p className={`text-xs ${classes.mutedText} leading-relaxed`}
                style={{ display: '-webkit-box', WebkitLineClamp: 4, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
              >
                {src.text}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ── Audio replay button ───────────────────────────────────────────────────────

const AudioButton = ({ audioSrc }) => {
  const { isDarkMode } = useTheme();
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef(null);

  const handlePlay = () => {
    if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; }
    const a = new Audio(audioSrc);
    audioRef.current = a;
    setPlaying(true);
    a.play().catch(() => setPlaying(false));
    a.onended = () => setPlaying(false);
  };

  return (
    <button
      onClick={handlePlay}
      disabled={playing}
      className={`mt-1.5 flex items-center gap-1.5 text-xs font-medium transition-colors disabled:opacity-50 ${
        isDarkMode ? 'text-indigo-400 hover:text-indigo-300' : 'text-indigo-600 hover:text-indigo-700'
      }`}
    >
      {playing ? (
        <>
          <span className="flex items-end gap-0.5 h-3">
            {[0, 150, 300].map((delay) => (
              <span
                key={delay}
                className={`w-0.5 rounded-full animate-bounce ${isDarkMode ? 'bg-indigo-400' : 'bg-indigo-600'}`}
                style={{ height: '10px', animationDelay: `${delay}ms` }}
              />
            ))}
          </span>
          Playing…
        </>
      ) : (
        <>
          <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z" />
          </svg>
          Replay audio
        </>
      )}
    </button>
  );
};

// ── Message bubble ────────────────────────────────────────────────────────────

const Message = ({ msg }) => {
  const { isDarkMode, classes } = useTheme();
  const isUser = msg.role === 'user';

  if (isUser) {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-[80%] px-4 py-3 rounded-2xl rounded-tr-sm bg-indigo-600 text-white shadow-sm">
          <p className="text-sm leading-relaxed">{msg.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start mb-4">
      <div className="max-w-[85%] space-y-1">
        {/* AI icon dot */}
        <div className="flex items-center gap-1.5 mb-1.5">
          <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 ${
            isDarkMode ? 'bg-indigo-900' : 'bg-indigo-100'
          }`}>
            <svg className={`w-3.5 h-3.5 ${isDarkMode ? 'text-indigo-400' : 'text-indigo-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <span className={`text-xs font-medium ${classes.mutedText}`}>AI Assistant</span>
        </div>

        {/* Answer bubble */}
        <div className={`px-4 py-3 rounded-2xl rounded-tl-sm shadow-sm ${
          isDarkMode ? 'bg-gray-700 text-gray-200' : 'bg-white text-gray-800'
        }`}>
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
        </div>

        {msg.sources?.length > 0 && <SourcesPanel sources={msg.sources} />}
        {msg.audioSrc && <AudioButton audioSrc={msg.audioSrc} />}
      </div>
    </div>
  );
};

// ── Typing indicator ─────────────────────────────────────────────────────────

const TypingIndicator = () => {
  const { isDarkMode } = useTheme();
  return (
    <div className="flex justify-start mb-4">
      <div className={`px-4 py-3 rounded-2xl rounded-tl-sm shadow-sm ${isDarkMode ? 'bg-gray-700' : 'bg-white'}`}>
        <span className="flex items-end gap-1 h-4">
          {[0, 200, 400].map((delay) => (
            <span
              key={delay}
              className={`w-1.5 h-1.5 rounded-full animate-bounce ${isDarkMode ? 'bg-gray-400' : 'bg-gray-400'}`}
              style={{ animationDelay: `${delay}ms` }}
            />
          ))}
        </span>
      </div>
    </div>
  );
};

// ── Main component ────────────────────────────────────────────────────────────

import { BACKEND } from '../../lib/api';

const NotebookStudio = ({ setView }) => {
  const { isDarkMode, classes } = useTheme();

  // 'upload' → PDF picker phase; 'chat' → conversation phase
  const [stage, setStage] = useState('upload');
  const [pdfFile, setPdfFile] = useState(null);
  const [pdfName, setPdfName] = useState('');
  const [uploadStage, setUploadStage] = useState(''); // '' | 'uploading'
  const [uploadError, setUploadError] = useState('');

  const [messages, setMessages] = useState([]);
  const [query, setQuery] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [chatError, setChatError] = useState('');

  const fileRef = useRef(null);
  const messagesEndRef = useRef(null);
  const activeAudioRef = useRef(null);

  // Auto-scroll to newest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isSending]);

  // ── Upload ──────────────────────────────────────────────────────────────────

  const handleUpload = async () => {
    if (!pdfFile) { setUploadError('Please select a PDF file.'); return; }

    setUploadStage('uploading');
    setUploadError('');
    try {
      const form = new FormData();
      form.append('file', pdfFile);
      const res = await fetch(`${BACKEND}/upload`, { method: 'POST', body: form });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? 'Upload failed.');
      }
      // Greet the user on enter
      setMessages([{
        id: Date.now(),
        role: 'assistant',
        content: `Document "${pdfFile.name}" indexed successfully. Ask me anything about it!`,
        sources: [],
        audioSrc: '',
      }]);
      setPdfName(pdfFile.name);
      setStage('chat');
    } catch (e) {
      setUploadError(e.message);
    } finally {
      setUploadStage('');
    }
  };

  // ── Chat ────────────────────────────────────────────────────────────────────

  const handleSend = async () => {
    const text = query.trim();
    if (!text || isSending) return;

    const userMsg = { id: Date.now(), role: 'user', content: text, sources: [], audioSrc: '' };
    setMessages((prev) => [...prev, userMsg]);
    setQuery('');
    setIsSending(true);
    setChatError('');

    try {
      const res = await fetch(`${BACKEND}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? 'Chat request failed.');
      }

      const { answer, audio_base64, sources } = await res.json();

      const assistantMsg = {
        id: Date.now() + 1,
        role: 'assistant',
        content: answer,
        sources: sources ?? [],
        audioSrc: audio_base64 ?? '',
      };
      setMessages((prev) => [...prev, assistantMsg]);

      // Auto-play TTS — safe because user just pressed Send (counts as interaction)
      if (audio_base64) {
        try {
          if (activeAudioRef.current) activeAudioRef.current.pause();
          const a = new Audio(audio_base64);
          activeAudioRef.current = a;
          await a.play();
        } catch {
          // Browser blocked auto-play — user can still replay manually
        }
      }
    } catch (e) {
      setChatError(e.message);
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  // ── Render: Upload phase ────────────────────────────────────────────────────

  if (stage === 'upload') {
    return (
      <div className="flex items-center justify-center min-h-screen p-4">
        <div className={`${classes.cardBg} rounded-2xl shadow-2xl p-8 max-w-md w-full animate-fadeInUp`}>
          {/* Back */}
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
              isDarkMode ? 'bg-indigo-900' : 'bg-indigo-100'
            }`}>
              <svg className={`w-9 h-9 ${isDarkMode ? 'text-indigo-400' : 'text-indigo-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <h1 className={`text-2xl font-bold ${classes.textColor} mb-1`}>Notebook Studio</h1>
            <p className={`${classes.mutedText} text-sm`}>Upload a PDF to start chatting with your document</p>
          </div>

          {/* PDF picker */}
          <label className={`block mb-4 cursor-pointer`}>
            <div className={`border-2 border-dashed rounded-xl p-6 min-h-[160px] flex flex-col items-center justify-center text-center transition-colors ${
              pdfFile
                ? isDarkMode ? 'border-green-600 bg-green-900/20' : 'border-green-400 bg-green-50'
                : isDarkMode ? 'border-indigo-600 hover:border-indigo-400' : 'border-indigo-300 hover:border-indigo-500'
            }`}>
              <input
                ref={fileRef}
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={(e) => { setPdfFile(e.target.files[0] ?? null); setUploadError(''); }}
              />
              {pdfFile ? (
                <>
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-3 ${isDarkMode ? 'bg-green-800' : 'bg-green-100'}`}>
                    <IconDocument className={`w-7 h-7 ${isDarkMode ? 'text-green-400' : 'text-green-600'}`} />
                  </div>
                  <p className={`font-semibold ${classes.textColor} text-sm truncate max-w-[280px]`}>{pdfFile.name}</p>
                  <p className={`text-xs ${classes.mutedText} mt-1`}>{(pdfFile.size / 1024).toFixed(0)} KB — click to change</p>
                </>
              ) : (
                <>
                  <IconUpload className={`w-10 h-10 mb-2 ${isDarkMode ? 'text-indigo-400' : 'text-indigo-400'}`} />
                  <p className={`font-medium ${classes.textColor}`}>Click to select a PDF</p>
                  <p className={`text-xs ${classes.mutedText} mt-1`}>Supports text-based PDFs</p>
                </>
              )}
            </div>
          </label>

          {/* Loading stage indicator */}
          {uploadStage && (
            <div className="flex items-center gap-2 mb-3 py-1">
              <div className={`w-4 h-4 border-2 border-t-transparent rounded-full animate-spin flex-shrink-0 ${
                isDarkMode ? 'border-indigo-400' : 'border-indigo-600'
              }`} />
              <p className={`text-sm font-medium ${isDarkMode ? 'text-indigo-300' : 'text-indigo-600'}`}>
                Indexing document…
              </p>
            </div>
          )}

          <ErrorBanner>{uploadError}</ErrorBanner>

          <Button
            onClick={handleUpload}
            disabled={!!uploadStage}
            className="w-full mt-4"
          >
            {uploadStage ? 'Indexing…' : 'Analyze Document'}
          </Button>
        </div>
      </div>
    );
  }

  // ── Render: Chat phase ──────────────────────────────────────────────────────

  return (
    <div className="flex flex-col text-left" style={{ height: 'calc(100vh - 4rem)' }}>

      {/* Header bar */}
      <div className={`flex-shrink-0 flex items-center gap-3 px-4 py-3 border-b ${
        isDarkMode ? 'border-gray-700 bg-gray-800' : 'border-gray-200 bg-white'
      } shadow-sm`}>
        <button
          onClick={() => {
            if (activeAudioRef.current) activeAudioRef.current.pause();
            setView('home');
          }}
          className={`p-1.5 rounded-lg transition-colors ${
            isDarkMode ? 'text-gray-400 hover:text-gray-200 hover:bg-gray-700' : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
          }`}
          title="Back to Home"
        >
          <IconChevronLeft className="w-5 h-5" />
        </button>

        <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
          isDarkMode ? 'bg-indigo-900' : 'bg-indigo-100'
        }`}>
          <IconDocument className={`w-5 h-5 ${isDarkMode ? 'text-indigo-400' : 'text-indigo-600'}`} />
        </div>

        <div className="flex-1 min-w-0">
          <p className={`text-sm font-semibold ${classes.textColor} truncate`}>{pdfName}</p>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-green-500 flex-shrink-0" />
            <p className={`text-xs ${classes.mutedText}`}>Document indexed · ready to chat</p>
          </div>
        </div>

        <button
          onClick={() => {
            if (activeAudioRef.current) activeAudioRef.current.pause();
            setStage('upload');
            setMessages([]);
            setPdfFile(null);
            if (fileRef.current) fileRef.current.value = '';
          }}
          className={`flex-shrink-0 text-xs font-medium px-3 py-1.5 rounded-lg border transition-colors ${
            isDarkMode
              ? 'border-gray-600 text-gray-400 hover:text-gray-200 hover:border-gray-500'
              : 'border-gray-300 text-gray-500 hover:text-gray-700 hover:border-gray-400'
          }`}
        >
          New document
        </button>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-5 space-y-0">
        {messages.map((msg) => <Message key={msg.id} msg={msg} />)}
        {isSending && <TypingIndicator />}
        {chatError && (
          <div className="flex justify-center mb-4">
            <p className={`text-xs px-3 py-1.5 rounded-full ${isDarkMode ? 'bg-red-900/60 text-red-300' : 'bg-red-50 text-red-600'}`}>
              {chatError}
            </p>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input bar */}
      <div className={`flex-shrink-0 border-t px-4 py-3 ${
        isDarkMode ? 'border-gray-700 bg-gray-800' : 'border-gray-200 bg-white'
      }`}>
        <div className={`flex items-end gap-2 px-3 py-2 rounded-xl border-2 transition-colors ${
          isDarkMode ? 'bg-gray-700 border-gray-600 focus-within:border-indigo-500' : 'bg-gray-50 border-gray-300 focus-within:border-indigo-400'
        }`}>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about your document… (Enter to send)"
            rows={1}
            disabled={isSending}
            className={`flex-1 resize-none bg-transparent text-sm outline-none min-h-[24px] max-h-[120px] leading-relaxed ${
              isDarkMode ? 'text-gray-200 placeholder-gray-500' : 'text-gray-800 placeholder-gray-400'
            } disabled:opacity-50`}
            style={{ overflowY: 'auto' }}
          />
          <button
            onClick={handleSend}
            disabled={!query.trim() || isSending}
            className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-all ${
              query.trim() && !isSending
                ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                : isDarkMode ? 'bg-gray-600 text-gray-500' : 'bg-gray-200 text-gray-400'
            }`}
            title="Send message"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
        <p className={`text-xs ${classes.mutedText} mt-1.5 text-center`}>
          Shift+Enter for new line · answers grounded in your document
        </p>
      </div>
    </div>
  );
};

export default NotebookStudio;
