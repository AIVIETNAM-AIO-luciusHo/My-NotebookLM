import { useCallback, useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';
import { useTheme } from '../../contexts/useTheme';
import { BACKEND } from '../../lib/api';

mermaid.initialize({
  startOnLoad: false,
  theme: 'neutral',
  flowchart: { curve: 'basis', padding: 24 },
  securityLevel: 'loose',
});

const DEFAULT_TOPIC = 'Tổng quan toàn bộ tài liệu';

// ── Mermaid diagram renderer ──────────────────────────────────────────────────

const MermaidDiagram = ({ code, onRenderError }) => {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!code || !containerRef.current) return;
    let cancelled = false;

    const render = async () => {
      try {
        const id = 'mmd-' + Date.now();
        const { svg } = await mermaid.render(id, code);
        if (cancelled || !containerRef.current) return;
        containerRef.current.innerHTML = svg;
        const svgEl = containerRef.current.querySelector('svg');
        if (svgEl) {
          svgEl.removeAttribute('height');
          svgEl.setAttribute('width', '100%');
          svgEl.style.maxWidth = '100%';
        }
      } catch {
        if (!cancelled) onRenderError?.();
      }
    };
    render();
    return () => { cancelled = true; };
  }, [code, onRenderError]);

  return <div ref={containerRef} className="w-full" />;
};

// ── Loading skeleton ──────────────────────────────────────────────────────────

const LoadingSkeleton = ({ isDarkMode }) => (
  <div className={`rounded-2xl border p-8 ${isDarkMode ? 'border-gray-700 bg-gray-800/40' : 'border-gray-200 bg-white'}`}>
    <div className="flex items-center gap-3 mb-6">
      <div className={`w-5 h-5 border-2 border-t-transparent rounded-full animate-spin flex-shrink-0 ${isDarkMode ? 'border-emerald-400' : 'border-emerald-600'}`} />
      <p className={`text-sm font-medium ${isDarkMode ? 'text-emerald-300' : 'text-emerald-700'}`}>
        AI is analysing document structure and generating mindmap…
      </p>
    </div>
    <div className="space-y-3">
      {[72, 55, 80, 45, 63, 38].map((w, i) => (
        <div key={i} className={`h-3 rounded-full animate-pulse ${isDarkMode ? 'bg-gray-700' : 'bg-gray-200'}`} style={{ width: `${w}%` }} />
      ))}
    </div>
  </div>
);

// ── MindmapVisualizer ─────────────────────────────────────────────────────────

const MindmapVisualizer = () => {
  const { isDarkMode, classes } = useTheme();

  const [topic, setTopic] = useState(DEFAULT_TOPIC);
  const [mermaidCode, setMermaidCode] = useState('');
  const [activeTopic, setActiveTopic] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [renderFailed, setRenderFailed] = useState(false);

  // Stable callback so MermaidDiagram's useEffect dep array stays clean
  const handleRenderError = useCallback(() => setRenderFailed(true), []);

  // Auto-fire on mount — immediately visualise the full document structure
  useEffect(() => {
    fetchMindmap(DEFAULT_TOPIC);
  }, []); // intentional: fire once on mount only

  const fetchMindmap = async (t) => {
    setLoading(true);
    setError('');
    setMermaidCode('');
    setRenderFailed(false);
    setActiveTopic(t);

    try {
      const res = await fetch(`${BACKEND}/generate-mindmap`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: t }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? 'Mindmap generation failed.');
      }
      const { mermaid_code } = await res.json();
      setMermaidCode(mermaid_code);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = () => {
    const t = topic.trim() || DEFAULT_TOPIC;
    fetchMindmap(t);
  };

  const isOverview = activeTopic === DEFAULT_TOPIC || activeTopic === '';

  return (
    <div className="h-full flex flex-col">
      {/* Controls bar */}
      <div className={`flex-shrink-0 border-b px-4 py-3 flex items-center gap-3 ${
        isDarkMode ? 'border-gray-700 bg-gray-800/50' : 'border-gray-200 bg-white'
      }`}>
        <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 ${isDarkMode ? 'bg-emerald-900' : 'bg-emerald-100'}`}>
          <svg className={`w-4 h-4 ${isDarkMode ? 'text-emerald-400' : 'text-emerald-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
          </svg>
        </div>
        <input
          type="text"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
          placeholder={DEFAULT_TOPIC}
          className={`flex-1 px-3 py-2 border rounded-lg text-sm focus:outline-none transition-colors ${
            isDarkMode
              ? 'bg-gray-700 border-gray-600 text-white placeholder-gray-500 focus:border-emerald-500'
              : 'bg-gray-50 border-gray-300 text-gray-800 placeholder-gray-400 focus:border-emerald-400'
          }`}
        />
        <button
          onClick={handleGenerate}
          disabled={loading}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold transition-all flex-shrink-0 ${
            loading
              ? isDarkMode ? 'bg-gray-700 text-gray-500 cursor-not-allowed' : 'bg-gray-200 text-gray-400 cursor-not-allowed'
              : 'bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm'
          }`}
        >
          {loading
            ? <span className="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
            : <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
          }
          {loading ? 'Generating…' : 'Regenerate'}
        </button>
      </div>

      {/* Content area */}
      <div className={`flex-1 overflow-y-auto p-4 md:p-6 ${isDarkMode ? 'bg-gray-900/20' : 'bg-gray-50/50'}`}>

        {/* Loading state */}
        {loading && <LoadingSkeleton isDarkMode={isDarkMode} />}

        {/* Error state */}
        {!loading && error && (
          <div className={`rounded-2xl p-6 border ${isDarkMode ? 'border-red-800 bg-red-900/30' : 'border-red-200 bg-red-50'}`}>
            <div className="flex items-start gap-3">
              <svg className={`w-5 h-5 flex-shrink-0 mt-0.5 ${isDarkMode ? 'text-red-400' : 'text-red-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <p className={`text-sm font-semibold mb-1 ${isDarkMode ? 'text-red-300' : 'text-red-700'}`}>Generation failed</p>
                <p className={`text-sm ${isDarkMode ? 'text-red-400' : 'text-red-600'}`}>{error}</p>
                <button
                  onClick={() => fetchMindmap(activeTopic || DEFAULT_TOPIC)}
                  className={`mt-3 text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors ${
                    isDarkMode ? 'bg-red-900 text-red-300 hover:bg-red-800' : 'bg-red-100 text-red-700 hover:bg-red-200'
                  }`}
                >
                  Try again
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Render error fallback */}
        {!loading && renderFailed && mermaidCode && (
          <div className={`mb-4 rounded-xl p-4 text-sm border ${isDarkMode ? 'border-yellow-800 bg-yellow-900/30 text-yellow-300' : 'border-yellow-200 bg-yellow-50 text-yellow-700'}`}>
            Diagram rendering failed — the AI may have produced invalid syntax. Showing raw Mermaid code below.
            <pre className={`mt-2 text-xs overflow-x-auto p-3 rounded-lg ${isDarkMode ? 'bg-gray-800' : 'bg-gray-100'}`}>{mermaidCode}</pre>
          </div>
        )}

        {/* Diagram card */}
        {!loading && !error && mermaidCode && !renderFailed && (
          <div className={`rounded-2xl border overflow-hidden shadow-sm ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
            {/* Card header */}
            <div className={`flex items-center justify-between px-4 py-3 border-b ${isDarkMode ? 'border-gray-700 bg-gray-800' : 'border-gray-200 bg-gray-50'}`}>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                <span className={`text-xs font-semibold ${classes.mutedText}`}>
                  {isOverview ? 'Document Overview' : `Topic: ${activeTopic}`}
                </span>
              </div>
              <button
                onClick={() => navigator.clipboard?.writeText(mermaidCode)}
                className={`flex items-center gap-1 text-xs font-medium transition-colors ${isDarkMode ? 'text-gray-400 hover:text-gray-200' : 'text-gray-500 hover:text-gray-700'}`}
                title="Copy Mermaid source"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
                Copy source
              </button>
            </div>
            {/* Diagram — always white background for legibility */}
            <div className="p-6 bg-white">
              <MermaidDiagram
                code={mermaidCode}
                onRenderError={handleRenderError}
              />
            </div>
          </div>
        )}

        {/* Empty state (no loading, no error, no code) — shouldn't normally appear */}
        {!loading && !error && !mermaidCode && (
          <div className={`rounded-2xl border-2 border-dashed p-12 text-center ${isDarkMode ? 'border-gray-700' : 'border-gray-300'}`}>
            <svg className={`w-10 h-10 mx-auto mb-3 ${isDarkMode ? 'text-gray-600' : 'text-gray-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
            </svg>
            <p className={`text-sm font-medium ${classes.textColor}`}>No diagram yet</p>
            <p className={`text-xs ${classes.mutedText} mt-1`}>Enter a topic above and click Regenerate</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default MindmapVisualizer;
