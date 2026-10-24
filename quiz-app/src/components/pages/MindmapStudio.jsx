import { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';
import { useTheme } from '../../contexts/useTheme';
import Button from '../ui/Button';
import ErrorBanner from '../ui/ErrorBanner';
import { IconChevronLeft, IconUpload, IconDocument } from '../ui/icons';

mermaid.initialize({
  startOnLoad: false,
  theme: 'neutral',
  flowchart: { curve: 'basis', padding: 20 },
  securityLevel: 'loose',
});

import { BACKEND } from '../../lib/api';

// ── Upload phase ──────────────────────────────────────────────────────────────

const UploadPhase = ({ onUploaded, setView }) => {
  const { isDarkMode, classes } = useTheme();
  const [pdfFile, setPdfFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const fileRef = useRef(null);

  const handleUpload = async () => {
    if (!pdfFile) { setError('Please select a PDF file.'); return; }
    setUploading(true);
    setError('');
    try {
      const form = new FormData();
      form.append('file', pdfFile);
      const res = await fetch(`${BACKEND}/upload`, { method: 'POST', body: form });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? 'Upload failed.');
      }
      onUploaded(pdfFile.name);
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen p-4">
      <div className={`${classes.cardBg} rounded-2xl shadow-2xl p-8 max-w-md w-full animate-fadeInUp`}>
        <button
          onClick={() => setView('home')}
          className={`flex items-center gap-1.5 text-sm font-medium mb-6 transition-colors ${
            isDarkMode ? 'text-gray-400 hover:text-gray-200' : 'text-gray-500 hover:text-gray-800'
          }`}
        >
          <IconChevronLeft className="w-4 h-4" />
          Back to Home
        </button>

        <div className="text-center mb-8">
          <div className={`w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4 ${
            isDarkMode ? 'bg-emerald-900' : 'bg-emerald-100'
          }`}>
            <svg className={`w-9 h-9 ${isDarkMode ? 'text-emerald-400' : 'text-emerald-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
            </svg>
          </div>
          <p className={`text-xs font-bold uppercase tracking-widest mb-1 ${
            isDarkMode ? 'text-emerald-400' : 'text-emerald-600'
          }`}>Module C</p>
          <h1 className={`text-2xl font-bold ${classes.textColor} mb-1`}>Mindmap Studio</h1>
          <p className={`text-sm ${classes.mutedText}`}>
            Upload a PDF to start generating visual knowledge maps
          </p>
        </div>

        <label className="block mb-4 cursor-pointer">
          <div className={`border-2 border-dashed rounded-xl p-6 min-h-[160px] flex flex-col items-center justify-center text-center transition-colors ${
            pdfFile
              ? isDarkMode ? 'border-emerald-600 bg-emerald-900/20' : 'border-emerald-400 bg-emerald-50'
              : isDarkMode ? 'border-emerald-700 hover:border-emerald-500' : 'border-emerald-300 hover:border-emerald-500'
          }`}>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => { setPdfFile(e.target.files[0] ?? null); setError(''); }}
            />
            {pdfFile ? (
              <>
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-3 ${isDarkMode ? 'bg-emerald-800' : 'bg-emerald-100'}`}>
                  <IconDocument className={`w-7 h-7 ${isDarkMode ? 'text-emerald-400' : 'text-emerald-600'}`} />
                </div>
                <p className={`font-semibold ${classes.textColor} text-sm truncate max-w-[280px]`}>{pdfFile.name}</p>
                <p className={`text-xs ${classes.mutedText} mt-1`}>{(pdfFile.size / 1024).toFixed(0)} KB — click to change</p>
              </>
            ) : (
              <>
                <IconUpload className={`w-10 h-10 mb-2 ${isDarkMode ? 'text-emerald-400' : 'text-emerald-400'}`} />
                <p className={`font-medium ${classes.textColor}`}>Click to select a PDF</p>
                <p className={`text-xs ${classes.mutedText} mt-1`}>Supports text-based PDFs</p>
              </>
            )}
          </div>
        </label>

        {uploading && (
          <div className="flex items-center gap-2 mb-3 py-1">
            <div className={`w-4 h-4 border-2 border-t-transparent rounded-full animate-spin flex-shrink-0 ${
              isDarkMode ? 'border-emerald-400' : 'border-emerald-600'
            }`} />
            <p className={`text-sm font-medium ${isDarkMode ? 'text-emerald-300' : 'text-emerald-600'}`}>
              Indexing document…
            </p>
          </div>
        )}

        <ErrorBanner>{error}</ErrorBanner>

        <Button
          variant="emerald"
          onClick={handleUpload}
          disabled={uploading}
          className="w-full mt-4"
        >
          {uploading ? 'Indexing…' : 'Index Document'}
        </Button>
      </div>
    </div>
  );
};

// ── Mermaid renderer ──────────────────────────────────────────────────────────

const MermaidDiagram = ({ code }) => {
  const { isDarkMode } = useTheme();
  const containerRef = useRef(null);
  const [renderError, setRenderError] = useState('');

  useEffect(() => {
    if (!code || !containerRef.current) return;

    let cancelled = false;
    setRenderError('');

    const render = async () => {
      try {
        const id = 'mmd-' + Date.now();
        const { svg } = await mermaid.render(id, code);
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
          // Make the SVG responsive
          const svgEl = containerRef.current.querySelector('svg');
          if (svgEl) {
            svgEl.removeAttribute('height');
            svgEl.setAttribute('width', '100%');
            svgEl.style.maxWidth = '100%';
          }
        }
      } catch {
        if (!cancelled) setRenderError('Could not render the diagram. The AI may have produced invalid syntax.');
      }
    };

    render();
    return () => { cancelled = true; };
  }, [code]);

  if (renderError) {
    return (
      <div className={`rounded-xl p-4 ${isDarkMode ? 'bg-red-900/40 text-red-300' : 'bg-red-50 text-red-600'} text-sm`}>
        {renderError}
      </div>
    );
  }

  return <div ref={containerRef} className="w-full overflow-auto" />;
};

// ── Main component ────────────────────────────────────────────────────────────

const MindmapStudio = ({ setView }) => {
  const { isDarkMode, classes } = useTheme();

  const [stage, setStage] = useState('upload'); // 'upload' | 'studio'
  const [pdfName, setPdfName] = useState('');

  const [topic, setTopic] = useState('');
  const [mermaidCode, setMermaidCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [hasGenerated, setHasGenerated] = useState(false);

  const handleUploaded = (name) => {
    setPdfName(name);
    setStage('studio');
  };

  const handleGenerate = async () => {
    const t = topic.trim();
    if (!t) { setError('Please enter a topic.'); return; }
    setLoading(true);
    setError('');
    setMermaidCode('');
    setHasGenerated(false);

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
      setHasGenerated(true);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  if (stage === 'upload') {
    return <UploadPhase onUploaded={handleUploaded} setView={setView} />;
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <div className={`flex-shrink-0 flex items-center gap-3 px-4 py-3 border-b shadow-sm ${
        isDarkMode ? 'border-gray-700 bg-gray-800' : 'border-gray-200 bg-white'
      }`}>
        <button
          onClick={() => setView('home')}
          className={`p-1.5 rounded-lg transition-colors ${
            isDarkMode ? 'text-gray-400 hover:text-gray-200 hover:bg-gray-700' : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
          }`}
          title="Back to Home"
        >
          <IconChevronLeft className="w-5 h-5" />
        </button>

        <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
          isDarkMode ? 'bg-emerald-900' : 'bg-emerald-100'
        }`}>
          <svg className={`w-5 h-5 ${isDarkMode ? 'text-emerald-400' : 'text-emerald-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
          </svg>
        </div>

        <div className="flex-1 min-w-0">
          <p className={`text-sm font-semibold ${classes.textColor} truncate`}>{pdfName}</p>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0" />
            <p className={`text-xs ${classes.mutedText}`}>Mindmap Studio · ready</p>
          </div>
        </div>

        <button
          onClick={() => { setStage('upload'); setMermaidCode(''); setHasGenerated(false); setError(''); }}
          className={`flex-shrink-0 text-xs font-medium px-3 py-1.5 rounded-lg border transition-colors ${
            isDarkMode
              ? 'border-gray-600 text-gray-400 hover:text-gray-200 hover:border-gray-500'
              : 'border-gray-300 text-gray-500 hover:text-gray-700 hover:border-gray-400'
          }`}
        >
          New document
        </button>
      </div>

      {/* Studio body */}
      <div className="flex-1 p-4 md:p-6 max-w-5xl w-full mx-auto">

        {/* Topic input + generate */}
        <div className={`flex flex-col sm:flex-row gap-3 mb-6 p-4 rounded-2xl border ${
          isDarkMode ? 'border-gray-700 bg-gray-800/50' : 'border-gray-200 bg-white'
        } shadow-sm`}>
          <input
            type="text"
            value={topic}
            onChange={(e) => { setTopic(e.target.value); setError(''); }}
            onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
            placeholder="Enter a topic from your document… e.g. Neural Networks, WWII Causes"
            className={`flex-1 px-4 py-2.5 border-2 rounded-xl text-sm focus:outline-none transition-colors ${
              isDarkMode
                ? 'bg-gray-700 border-gray-600 text-white placeholder-gray-500 focus:border-emerald-500'
                : 'bg-gray-50 border-gray-300 text-gray-800 placeholder-gray-400 focus:border-emerald-400'
            }`}
          />
          <button
            onClick={handleGenerate}
            disabled={loading || !topic.trim()}
            className={`flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all flex-shrink-0 ${
              loading || !topic.trim()
                ? isDarkMode ? 'bg-gray-700 text-gray-500 cursor-not-allowed' : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                : 'bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm hover:shadow-md'
            }`}
          >
            {loading ? (
              <>
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Generating…
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                </svg>
                Generate Mindmap
              </>
            )}
          </button>
        </div>

        <ErrorBanner>{error}</ErrorBanner>

        {/* Loading skeleton */}
        {loading && (
          <div className={`rounded-2xl p-8 border animate-pulse ${
            isDarkMode ? 'border-gray-700 bg-gray-800/50' : 'border-gray-200 bg-white'
          }`}>
            <div className="flex items-center gap-3 mb-6">
              <div className={`w-5 h-5 border-2 border-t-transparent rounded-full animate-spin flex-shrink-0 ${
                isDarkMode ? 'border-emerald-400' : 'border-emerald-600'
              }`} />
              <p className={`text-sm font-medium ${isDarkMode ? 'text-emerald-300' : 'text-emerald-700'}`}>
                AI is building your knowledge map…
              </p>
            </div>
            <div className="space-y-3">
              {[80, 60, 75, 50, 65].map((w, i) => (
                <div key={i} className={`h-3 rounded-full ${isDarkMode ? 'bg-gray-700' : 'bg-gray-200'}`} style={{ width: `${w}%` }} />
              ))}
            </div>
          </div>
        )}

        {/* Rendered diagram */}
        {!loading && hasGenerated && mermaidCode && (
          <div className={`rounded-2xl border overflow-hidden ${
            isDarkMode ? 'border-gray-700 bg-white' : 'border-gray-200 bg-white'
          } shadow-sm`}>
            <div className={`flex items-center justify-between px-4 py-3 border-b ${
              isDarkMode ? 'border-gray-200 bg-gray-50' : 'border-gray-200 bg-gray-50'
            }`}>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                <span className="text-xs font-semibold text-gray-600">Mindmap: {topic}</span>
              </div>
              <button
                onClick={() => {
                  navigator.clipboard?.writeText(mermaidCode);
                }}
                className="text-xs font-medium text-gray-500 hover:text-gray-700 transition-colors flex items-center gap-1"
                title="Copy Mermaid source"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
                Copy source
              </button>
            </div>
            <div className="p-6">
              <MermaidDiagram code={mermaidCode} />
            </div>
          </div>
        )}

        {/* Empty state */}
        {!loading && !hasGenerated && !error && (
          <div className={`rounded-2xl border-2 border-dashed p-12 text-center ${
            isDarkMode ? 'border-gray-700' : 'border-gray-200'
          }`}>
            <div className={`w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4 ${
              isDarkMode ? 'bg-emerald-900/50' : 'bg-emerald-50'
            }`}>
              <svg className={`w-8 h-8 ${isDarkMode ? 'text-emerald-500' : 'text-emerald-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
              </svg>
            </div>
            <p className={`text-sm font-medium ${classes.textColor} mb-1`}>No mindmap yet</p>
            <p className={`text-xs ${classes.mutedText}`}>
              Enter a topic above and click Generate Mindmap to visualise your document
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default MindmapStudio;
