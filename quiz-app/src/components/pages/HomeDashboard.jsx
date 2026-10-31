import { useTheme } from '../../contexts/useTheme';

const FeaturePill = ({ icon, label }) => {
  const { isDarkMode } = useTheme();
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${
      isDarkMode ? 'bg-gray-800 text-gray-300 border border-gray-700' : 'bg-white text-gray-600 border border-gray-200 shadow-sm'
    }`}>
      {icon}
      {label}
    </span>
  );
};

const HomeDashboard = ({ setView }) => {
  const { isDarkMode, classes } = useTheme();

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-2xl text-center animate-fadeInUp">

        {/* Logo */}
        <div className={`w-20 h-20 mx-auto mb-6 rounded-3xl flex items-center justify-center shadow-xl ${
          isDarkMode
            ? 'bg-gradient-to-br from-indigo-500 to-violet-600'
            : 'bg-gradient-to-br from-indigo-500 to-violet-600'
        }`}>
          <svg className="w-11 h-11 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.6}
              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
        </div>

        {/* Headline */}
        <h1 className={`text-5xl font-bold tracking-tight mb-3 ${classes.textColor}`}>
          Phòng học AI
        </h1>
        <p className={`text-lg ${classes.mutedText} mb-10 max-w-md mx-auto leading-relaxed`}>
          Nạp một tệp PDF bất kỳ để hỏi đáp với AI, tạo quiz và vẽ sơ đồ tư duy.
        </p>

        {/* Feature pills */}
        <div className="flex flex-wrap justify-center gap-2 mb-10">
          <FeaturePill
            icon={<svg className="w-3.5 h-3.5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>}
            label="Hỏi đáp tài liệu"
          />
          <FeaturePill
            icon={<svg className="w-3.5 h-3.5 text-violet-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>}
            label="Tạo quiz"
          />
          <FeaturePill
            icon={<svg className="w-3.5 h-3.5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" /></svg>}
            label="Sơ đồ tư duy"
          />
          <FeaturePill
            icon={<svg className="w-3.5 h-3.5 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072M12 18.364A8 8 0 1112 5.636m0 12.728A8 8 0 0112 5.636" /></svg>}
            label="Giọng đọc tiếng Việt"
          />
          <FeaturePill
            icon={<svg className="w-3.5 h-3.5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>}
            label="RAG suy luận từng bước"
          />
        </div>

        {/* Primary CTA */}
        <button
          onClick={() => setView('workspace')}
          className="w-full sm:w-auto inline-flex items-center justify-center gap-3 px-10 py-4 rounded-2xl text-base font-semibold text-white shadow-lg hover:shadow-xl transition-all duration-200 hover:-translate-y-0.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          Bắt đầu phiên học
        </button>

        {/* Divider */}
        <div className="flex items-center gap-4 my-8 max-w-xs mx-auto">
          <div className={`flex-1 h-px ${isDarkMode ? 'bg-gray-700' : 'bg-gray-200'}`} />
          <span className={`text-xs font-medium ${classes.mutedText}`}>hoặc</span>
          <div className={`flex-1 h-px ${isDarkMode ? 'bg-gray-700' : 'bg-gray-200'}`} />
        </div>

        {/* Secondary CTA */}
        <button
          onClick={() => setView('upload')}
          className={`inline-flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold border-2 transition-all duration-200 ${
            isDarkMode
              ? 'border-gray-700 text-gray-300 hover:border-indigo-500 hover:text-indigo-400'
              : 'border-gray-300 text-gray-600 hover:border-indigo-400 hover:text-indigo-600'
          }`}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          Mở thư viện quiz
        </button>

        {/* Footer note */}
        <p className={`text-xs ${classes.mutedText} mt-8`}>
          Chạy cục bộ với Ollama · llama3.2 · Vietnamese SBERT · ChromaDB
        </p>
      </div>
    </div>
  );
};

export default HomeDashboard;
