import { useEffect, useRef, useState } from 'react';
import { useTheme } from '../../contexts/useTheme';
import NotebookChat from './NotebookChat';
import QuizStudio from './QuizStudio';
import MindmapVisualizer from './MindmapVisualizer';
import StatePanel from '../ui/StatePanel';
import ThemeToggle from '../ui/ThemeToggle';
import { IconDocument, IconUpload, IconChevronLeft } from '../ui/icons';
import { api } from '../../lib/api';
import { useHealth } from '../../hooks/useHealth';
import { useJobs } from '../../hooks/useJobs';
import { errorView, emptyWorkspaceView, filesUnknownView } from '../../utils/errorView';
import { canDelete, canResume, needsReupload, isWarmingUp, errorWarning, graphProgress, progressText, statusLabel, isUnfinished } from '../../utils/jobs';

// Màn hình notebook: Nguồn (tệp + upload + job) / Hội thoại / Studio (Quiz, Mindmap).
// Đây là màn duy nhất cho workspace; NotebookStudio cũ (không được route tới) đã bị xoá.

const Dot = ({ color }) => <span className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${color}`} />;

const TopBar = ({ setView, health, healthError, jobs }) => {
  const { isDarkMode, classes } = useTheme();
  const down = !!healthError || !health;
  const progress = graphProgress(jobs);
  let graph;
  if (down) graph = { dot: 'bg-gray-400', text: 'Đồ thị: không rõ' };
  else if (health.graph_ready === false) {
    graph = progress
      ? { dot: 'bg-yellow-500', text: `Đồ thị: đang dựng${progress.total ? ` ${progress.text}` : ''}` }
      : { dot: 'bg-yellow-500', text: 'Đồ thị: chưa đầy đủ (có tác vụ lỗi hoặc bị gián đoạn)' };
  } else graph = { dot: 'bg-green-500', text: 'Đồ thị: sẵn sàng' };

  return (
    <header className={`flex-shrink-0 flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2.5 border-b shadow-sm ${
      isDarkMode ? 'border-gray-700 bg-gray-900' : 'border-gray-200 bg-white'
    }`}>
      <button onClick={() => setView('home')} title="Về trang chủ" aria-label="Về trang chủ"
        className={`p-1.5 rounded-lg ${isDarkMode ? 'text-gray-400 hover:bg-gray-800' : 'text-gray-500 hover:bg-gray-100'}`}>
        <IconChevronLeft className="w-4 h-4" />
      </button>
      <h1 className={`text-sm font-semibold ${classes.textColor} flex-1 min-w-[6rem]`}>Notebook</h1>
      <span data-testid="backend-status" className={`inline-flex items-center gap-1.5 text-xs ${classes.mutedText}`}>
        <Dot color={down ? 'bg-red-500' : 'bg-green-500'} />
        {down ? 'Backend: tắt' : 'Backend: hoạt động'}
      </span>
      <span data-testid="graph-status" className={`inline-flex items-center gap-1.5 text-xs ${classes.mutedText}`}>
        <Dot color={graph.dot} />
        {graph.text}
      </span>
      <ThemeToggle compact />
    </header>
  );
};

// ── Cột Nguồn ────────────────────────────────────────────────────────────────

const JobRow = ({ job, onResume, onDelete }) => {
  const { isDarkMode, classes } = useTheme();
  const warn = errorWarning(job);
  const total = job.chunks_total ?? 0;
  const pct = job.status === 'done' ? 100 : total ? Math.round(((job.chunks_done ?? 0) / total) * 100) : 0;
  return (
    <li data-testid="job-row" data-status={job.status} className={`rounded-lg px-3 py-2 text-xs ${isDarkMode ? 'bg-gray-800' : 'bg-gray-50'}`}>
      <p className={`font-medium ${classes.textColor} truncate`} title={job.source}>{job.source}</p>
      <p className={classes.mutedText}>
        {statusLabel(job.status)}{progressText(job) ? ` · ${progressText(job)}` : ''}
      </p>
      {isUnfinished(job) && (
        <div className={`h-1 rounded mt-1.5 ${isDarkMode ? 'bg-gray-700' : 'bg-gray-200'}`}>
          <div className="h-1 rounded bg-indigo-500" style={{ width: `${pct}%` }} />
        </div>
      )}
      {isWarmingUp(job) && <p className={`mt-1 ${classes.mutedText}`}>Đang khởi động mô hình, lượt đầu có thể mất vài phút</p>}
      {warn && <p title={job.error} className={`mt-1 ${isDarkMode ? 'text-yellow-300' : 'text-yellow-700'}`}>{warn}</p>}
      {needsReupload(job) && <p className={`mt-1 ${classes.mutedText}`}>Hãy tải lại tệp.</p>}
      {canResume(job) && (
        <button onClick={() => onResume(job.job_id)}
          className="mt-1.5 font-medium px-2 py-1 rounded-md bg-indigo-600 text-white hover:bg-indigo-700">
          Tiếp tục
        </button>
      )}
      {canDelete(job) && (
        <button onClick={() => onDelete(job.job_id)} aria-label={`Xoá tác vụ ${job.source}`}
          className={`mt-1.5 ml-2 font-medium px-2 py-1 rounded-md ${isDarkMode ? 'bg-gray-700 text-gray-200 hover:bg-gray-600' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}>
          Xoá
        </button>
      )}
    </li>
  );
};

const SourcesPane = ({ health, healthError, onRefreshHealth, jobsState }) => {
  const { isDarkMode, classes } = useTheme();
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef(null);
  const { jobs, notice, refresh, resume, remove } = jobsState;

  const pick = (f) => {
    if (!f) return;
    if (!f.name.toLowerCase().endsWith('.pdf')) {
      // Cùng khung với lỗi 400 của backend; bỏ tệp không hợp lệ khỏi lựa chọn.
      setFile(null);
      if (inputRef.current) inputRef.current.value = '';
      setUploadError({ kind: 'client', uploadReason: 'notpdf', message: 'Chỉ nhận tệp PDF.' });
      return;
    }
    setFile(f);
    setUploadError(null);
  };

  const upload = async () => {
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      await api.upload(file);
      setFile(null);
      if (inputRef.current) inputRef.current.value = '';
      await Promise.all([refresh(), onRefreshHealth()]);
    } catch (e) {
      setUploadError(e);
    } finally {
      setUploading(false);
    }
  };

  const files = health?.files ?? [];
  return (
    <aside aria-label="Nguồn" className={`min-w-0 p-4 space-y-4 md:overflow-y-auto border-b md:border-b-0 md:border-r ${
      isDarkMode ? 'border-gray-700' : 'border-gray-200'
    }`}>
      <h2 className={`text-xs font-bold uppercase tracking-wide ${classes.mutedText}`}>Nguồn</h2>

      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]); }}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-xl border-2 border-dashed p-4 text-center ${
          drag ? 'border-indigo-400 bg-indigo-500/10' : isDarkMode ? 'border-gray-600' : 'border-gray-300'
        }`}
      >
        <input ref={inputRef} type="file" accept=".pdf" className="hidden" data-testid="pdf-input"
          onChange={(e) => pick(e.target.files[0] ?? null)} />
        <IconUpload className={`w-6 h-6 mx-auto mb-1 ${classes.mutedText}`} />
        <p className={`text-xs ${classes.textColor} ${file ? 'truncate' : ''}`} title={file ? file.name : undefined}>
          {file ? file.name : 'Kéo thả hoặc bấm để chọn PDF'}
        </p>
      </div>
      <button onClick={upload} disabled={!file || uploading}
        className="w-full text-sm font-semibold py-2 rounded-lg bg-indigo-600 text-white disabled:opacity-50">
        {uploading ? 'Đang nạp…' : 'Nạp tài liệu'}
      </button>
      {uploadError && <StatePanel compact view={errorView(uploadError, 'upload')} onRetry={file ? upload : undefined} />}

      {healthError ? (
        <StatePanel compact view={errorView(healthError)} onRetry={onRefreshHealth} />
      ) : files.length === 0 ? (
        <StatePanel compact view={emptyWorkspaceView()} />
      ) : (
        <ul data-testid="file-list" className="space-y-1">
          {files.map((f) => (
            <li key={f} className={`flex items-center gap-2 text-xs ${classes.textColor}`}>
              <IconDocument className="w-4 h-4 flex-shrink-0" />
              <span className="truncate" title={f}>{f}</span>
            </li>
          ))}
        </ul>
      )}

      {jobs.length > 0 && (
        <div>
          <h3 className={`text-xs font-bold uppercase tracking-wide mb-1.5 ${classes.mutedText}`}>Tác vụ nền</h3>
          <ul className="space-y-1.5">
            {jobs.slice(0, 5).map((j) => <JobRow key={j.job_id} job={j} onResume={resume} onDelete={remove} />)}
          </ul>
          {notice && <p role="alert" className={`mt-2 text-xs ${isDarkMode ? 'text-red-300' : 'text-red-600'}`}>{notice}</p>}
        </div>
      )}
    </aside>
  );
};

// ── Cột Studio ───────────────────────────────────────────────────────────────

const StudioPane = ({ quizProps, hasFiles, backendDown }) => {
  const { isDarkMode, classes } = useTheme();
  const [tab, setTab] = useState('quiz');
  const [mindmapMounted, setMindmapMounted] = useState(false);
  const pickTab = (t) => { setTab(t); if (t === 'mindmap') setMindmapMounted(true); };

  return (
    <section aria-label="Studio" className={`min-w-0 flex flex-col md:col-span-2 lg:col-span-1 border-t lg:border-t-0 lg:border-l ${
      isDarkMode ? 'border-gray-700' : 'border-gray-200'
    }`}>
      <div className={`flex-shrink-0 flex border-b ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
        {[['quiz', 'Quiz'], ['mindmap', 'Mindmap']].map(([id, label]) => (
          <button key={id} onClick={() => pickTab(id)}
            className={`flex-1 py-2.5 text-sm font-semibold border-b-2 -mb-px ${
              tab === id ? 'text-indigo-500 border-indigo-500' : `border-transparent ${classes.mutedText}`
            }`}>
            {label}
          </button>
        ))}
      </div>
      {!hasFiles ? (
        <div className="p-4"><StatePanel compact view={backendDown ? filesUnknownView() : emptyWorkspaceView()} /></div>
      ) : (
        <div className="relative h-[34rem] lg:h-auto lg:flex-1 lg:min-h-0 overflow-hidden">
          <div className={tab === 'quiz' ? 'h-full overflow-y-auto' : 'hidden'}><QuizStudio {...quizProps} /></div>
          {mindmapMounted && (
            <div className={tab === 'mindmap' ? 'h-full flex flex-col overflow-auto' : 'hidden'}><MindmapVisualizer /></div>
          )}
        </div>
      )}
    </section>
  );
};

// ── Root ─────────────────────────────────────────────────────────────────────

const WorkspaceDashboard = ({
  setView,
  setOriginalQuizData,
  setProcessedQuizData,
  setActiveSettings,
  setAnswers,
  setCurrentQuestion,
}) => {
  const { classes } = useTheme();
  const { health, error: healthError, refresh: refreshHealth } = useHealth();
  const jobsState = useJobs();
  // Khi một job vừa xong, /health (graph_ready, files) cần cập nhật ngay.
  const finishedKey = jobsState.jobs.map((j) => `${j.job_id}:${j.status}`).join(',');
  useEffect(() => { refreshHealth(); }, [finishedKey, refreshHealth]);

  const quizProps = { setView, setOriginalQuizData, setProcessedQuizData, setActiveSettings, setAnswers, setCurrentQuestion };
  const hasFiles = (health?.files?.length ?? 0) > 0;
  const backendDown = !!healthError;

  return (
    <div className={`flex flex-col min-h-screen lg:h-screen overflow-x-hidden ${classes.textColor}`}>
      <TopBar setView={setView} health={health} healthError={healthError} jobs={jobsState.jobs} />
      <main className="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-[13rem_minmax(25rem,1fr)] lg:grid-cols-[15rem_minmax(0,1fr)_minmax(0,20rem)] xl:grid-cols-[18rem_minmax(0,1fr)_minmax(0,26rem)]">
        <SourcesPane health={health} healthError={healthError} onRefreshHealth={refreshHealth} jobsState={jobsState} />
        <section aria-label="Hội thoại" className="min-w-0 h-[32rem] lg:h-auto lg:min-h-0 flex flex-col">
          <NotebookChat hasFiles={hasFiles} backendDown={backendDown} onRetryBackend={refreshHealth} />
        </section>
        <StudioPane quizProps={quizProps} hasFiles={hasFiles} backendDown={backendDown} />
      </main>
    </div>
  );
};

export default WorkspaceDashboard;
