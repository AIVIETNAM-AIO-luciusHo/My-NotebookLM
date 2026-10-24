import { useEffect, useRef, useState } from 'react';
import { useTheme } from '../../contexts/useTheme';
import { BACKEND } from '../../lib/api';

// ── Source panel ──────────────────────────────────────────────────────────────

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
        <svg className={`w-3 h-3 transition-transform duration-200 ${open ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        {sources.length} source{sources.length !== 1 ? 's' : ''} cited
      </button>

      {open && (
        <div className="mt-2 space-y-1.5">
          {sources.map((src, i) => (
            <div key={i} className={`flex items-start gap-2.5 px-3 py-2.5 rounded-lg ${isDarkMode ? 'bg-gray-900/60' : 'bg-gray-50'}`}>
              <span className={`flex-shrink-0 text-xs font-mono font-bold px-1.5 py-0.5 rounded-md ${
                src.cosine_score >= 0.85
                  ? isDarkMode ? 'bg-green-900 text-green-300' : 'bg-green-100 text-green-700'
                  : src.cosine_score >= 0.70
                    ? isDarkMode ? 'bg-yellow-900 text-yellow-300' : 'bg-yellow-100 text-yellow-700'
                    : isDarkMode ? 'bg-gray-700 text-gray-400' : 'bg-gray-200 text-gray-600'
              }`}>
                {src.cosine_score.toFixed(3)}
              </span>
              <p
                className={`text-xs ${classes.mutedText} leading-relaxed`}
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
            {[0, 150, 300].map((d) => (
              <span key={d} className={`w-0.5 rounded-full animate-bounce ${isDarkMode ? 'bg-indigo-400' : 'bg-indigo-600'}`}
                style={{ height: '10px', animationDelay: `${d}ms` }} />
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
        <div className="flex items-center gap-1.5 mb-1.5">
          <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 ${isDarkMode ? 'bg-indigo-900' : 'bg-indigo-100'}`}>
            <svg className={`w-3.5 h-3.5 ${isDarkMode ? 'text-indigo-400' : 'text-indigo-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <span className={`text-xs font-medium ${classes.mutedText}`}>AI Assistant</span>
        </div>
        <div className={`px-4 py-3 rounded-2xl rounded-tl-sm shadow-sm ${isDarkMode ? 'bg-gray-700 text-gray-200' : 'bg-white text-gray-800'}`}>
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
        </div>
        {msg.sources?.length > 0 && <SourcesPanel sources={msg.sources} />}
        {msg.audioSrc && <AudioButton audioSrc={msg.audioSrc} />}
      </div>
    </div>
  );
};

// ── Typing indicator ──────────────────────────────────────────────────────────

const TypingIndicator = () => {
  const { isDarkMode } = useTheme();
  return (
    <div className="flex justify-start mb-4">
      <div className={`px-4 py-3 rounded-2xl rounded-tl-sm shadow-sm ${isDarkMode ? 'bg-gray-700' : 'bg-white'}`}>
        <span className="flex items-end gap-1 h-4">
          {[0, 200, 400].map((d) => (
            <span key={d} className={`w-1.5 h-1.5 rounded-full animate-bounce ${isDarkMode ? 'bg-gray-400' : 'bg-gray-400'}`}
              style={{ animationDelay: `${d}ms` }} />
          ))}
        </span>
      </div>
    </div>
  );
};

// ── NotebookChat ──────────────────────────────────────────────────────────────

const NotebookChat = ({ documentName }) => {
  const { isDarkMode } = useTheme();

  const [messages, setMessages] = useState(() => [{
    id: 0,
    role: 'assistant',
    content: `Document "${documentName}" is ready. Ask me anything — I'll cite my sources.`,
    sources: [],
    audioSrc: '',
  }]);
  const [query, setQuery] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [chatError, setChatError] = useState('');

  const messagesEndRef = useRef(null);
  const activeAudioRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isSending]);

  const handleSend = async () => {
    const text = query.trim();
    if (!text || isSending) return;

    setMessages((prev) => [...prev, { id: Date.now(), role: 'user', content: text, sources: [], audioSrc: '' }]);
    setQuery('');
    setIsSending(true);
    setChatError('');
    // Reset textarea height
    if (textareaRef.current) textareaRef.current.style.height = 'auto';

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

      setMessages((prev) => [...prev, {
        id: Date.now() + 1,
        role: 'assistant',
        content: answer,
        sources: sources ?? [],
        audioSrc: audio_base64 ?? '',
      }]);

      if (audio_base64) {
        try {
          if (activeAudioRef.current) activeAudioRef.current.pause();
          const a = new Audio(audio_base64);
          activeAudioRef.current = a;
          await a.play();
        } catch { /* auto-play blocked */ }
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

  // Auto-grow textarea
  const handleInput = (e) => {
    setQuery(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className={`flex-1 overflow-y-auto px-4 py-5 ${isDarkMode ? 'bg-gray-900/20' : 'bg-gray-50/50'}`}>
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
      <div className={`flex-shrink-0 border-t px-4 pt-3 pb-4 ${isDarkMode ? 'border-gray-700 bg-gray-800' : 'border-gray-200 bg-white'}`}>
        {/* Text + send */}
        <div className={`flex items-end gap-2 px-3 py-2 rounded-xl border-2 transition-colors ${
          isDarkMode
            ? 'bg-gray-700 border-gray-600 focus-within:border-indigo-500'
            : 'bg-gray-50 border-gray-300 focus-within:border-indigo-400'
        }`}>
          <textarea
            ref={textareaRef}
            value={query}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question… (Enter to send, Shift+Enter for new line)"
            rows={1}
            disabled={isSending}
            className={`flex-1 resize-none bg-transparent text-sm outline-none min-h-[24px] leading-relaxed ${
              isDarkMode ? 'text-gray-200 placeholder-gray-500' : 'text-gray-800 placeholder-gray-400'
            } disabled:opacity-50`}
            style={{ overflowY: 'hidden' }}
          />
          <button
            onClick={handleSend}
            disabled={!query.trim() || isSending}
            className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-all ${
              query.trim() && !isSending
                ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                : isDarkMode ? 'bg-gray-600 text-gray-500' : 'bg-gray-200 text-gray-400'
            }`}
            title="Send"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};

export default NotebookChat;
